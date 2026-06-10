from __future__ import annotations

import logging
import re
import string
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator, Union, cast, overload
from urllib.parse import urlparse

from nuclia_models.worker.proto import (
    ApplyTo,
    DataAugmentation,
    Filter,
    MemoryOperation,
    Operation,
)
from nuclia_models.worker.tasks import ApplyOptions, TaskName
from nucliadb_models import (
    augment,
    filters,
    graph,
)
from nucliadb_models.common import FieldTypeName
from nucliadb_models.conversation import (
    Conversation,
    InputMessage,
    InputMessageContent,
    Message,
    MessageFormat,
    MessageType,
)
from nucliadb_models.link import LinkField
from nucliadb_models.resource import Resource, ResourceField
from nucliadb_models.search import (
    AskRequest,
    CatalogRequest,
    CatalogResponse,
    ChatContextMessage,
    CitationsType,
    FindOptions,
    FindRequest,
    KnowledgeboxFindResults,
    PredictReranker,
    ResourceProperties,
    SyncAskResponse,
)
from nucliadb_models.text import TextField, TextFormat
from nucliadb_sdk.v2.exceptions import ConflictError, NotFoundError, UnprocessableEntity
from pydantic import BaseModel

from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.task import NucliaTask
from nuclia.sdk.upload import NucliaUpload

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

MEMORY_FIELD_PREFIX = "__memory__"
FACTS_FIELD_PREFIX = f"da-facts-{MEMORY_FIELD_PREFIX}"
GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX = "memory-global-annotations"


# ─── Exceptions ─────────────────────────────────────────────────────────────


class TopicAlreadyExistsError(Exception):
    """Raised when attempting to create a new topic with a slug that already exists."""

    pass


class TopicNotFoundError(Exception):
    """Raised when an topic with the specified ID or slug cannot be found."""

    pass


class AnnotationAlreadyExistsError(Exception):
    """Raised when attempting to create a new annotation with an ID that already exists for the topic and user."""

    pass


# ─── Data models ─────────────────────────────────────────────────────────────


class Topic(BaseModel):
    """A discrete unit of memory stored in the memory.
    Corresponds to a single resource in a Nuclia Knowledge Box.
    """

    id: str
    slug: str
    title: str
    summary: str | None = None
    status: str


class TopicPage(BaseModel):
    """A paginated listing of topics."""

    items: list[Topic]
    total: int
    has_more: bool


class ContextBlock(BaseModel):
    id: str
    text: str


class RelevantContextBlock(ContextBlock):
    score: float


class RecallResult(BaseModel):
    """Result of a generative `recall()` call."""

    answer: str
    citations: dict[str, RelevantContextBlock]


class AnnotationContextMessage(BaseModel):
    """A context message attached to an annotation."""

    author: str
    text: str


class AnnotationContent(BaseModel):
    """The content of the annotation with separate fields for the text, reasoning, and context."""

    text: str
    reasoning: str | None = None
    context: list[AnnotationContextMessage] | None = None
    metadata: dict[str, Any] | None = None


class Annotation(BaseModel):
    """A single annotation message attached to an topic."""

    id: str
    timestamp: datetime
    content: AnnotationContent

    @classmethod
    def from_conversation_message(cls, message: Message) -> "Annotation":
        content = AnnotationContent.model_validate_json(message.content.text or "")
        assert message.ident is not None
        assert message.timestamp is not None
        return cls(
            id=message.ident,
            timestamp=message.timestamp,
            content=content,
        )


class FactContent(BaseModel):
    """
    The content of a fact extracted from an annotation, including the fact text and a list of
    related annotation IDs that were used as evidence for the fact.
    """

    text: str
    related_annotation_ids: list[str] = []


class Fact(BaseModel):
    """A single fact extracted from an annotation"""

    id: str
    timestamp: datetime
    content: FactContent

    @classmethod
    def from_conversation_message(cls, message: Message) -> "Fact":
        content = FactContent.model_validate_json(message.content.text or "")
        assert message.ident is not None
        assert message.timestamp is not None
        return cls(
            id=message.ident,
            timestamp=message.timestamp,
            content=content,
        )


class GraphNode(BaseModel):
    """A single node in the graph."""

    type: str
    value: str
    group: str | None = None


class GraphRelation(BaseModel):
    """A single relation in the graph."""

    label: str
    type: str


class GraphEdgeMetadata(BaseModel):
    context_block_id: str | None = None


class GraphEdge(BaseModel):
    """A single edge in the graph."""

    source: GraphNode
    relation: GraphRelation
    destination: GraphNode
    metadata: GraphEdgeMetadata | None = None


# ─── Sync Memory ─────────────────────────────────────────────────────────────


class NucliaMemory:
    def __init__(self):
        self.kb = NucliaKB()
        self.upload = NucliaUpload()
        self.tasks = NucliaTask()

    # ── initialize ───────────────────────────────────────────────────────

    @kb
    def initialize(self, **kwargs) -> None:
        """Ensure the memory task is configured for this knowledge box.

        This method should be called once before using the memory to make sure
        the required background task is set up in the KB.
        """
        kb_tasks = self.tasks.list()
        if not any(task.task.name == TaskName.MEMORY for task in kb_tasks.configs):
            self.tasks.start(
                task_name=TaskName.MEMORY,
                apply=ApplyOptions.EXISTING,
                parameters=DataAugmentation(
                    name="memory",
                    on=ApplyTo.FIELD,
                    filter=Filter(
                        field_types=[FieldTypeName.CONVERSATION.abbreviation()],
                        apply_to_agent_generated_fields=False,
                    ),
                    operations=[
                        Operation(
                            memory=MemoryOperation(
                                ident="memory",
                            )
                        )
                    ],
                ),
            )

    # ── store ────────────────────────────────────────────────────────────

    @overload
    def store(
        self,
        text: str | None = None,
        *,
        title: str | None = None,
        slug: str | None = None,
        path: str | None = None,
        url: str | None = None,
        summary: str | None = None,
        **kwargs,
    ) -> None:
        """Create a new topic from text, file, or URL.

        Parameters
        ----------
        text:
            The text content to store. Optional if providing a file or URL.
        title:
            Optional resource title. If not provided, a default title will be inferred from the content.
        slug:
            Optional resource slug. If not provided, a slug will be generated from the title.
        url:
            Optional resource URL. Use to ingest content from the web into the topic.
        path:
            Path to a local file to upload as topic content. Use to ingest file content into the topic.
        summary:
            Optional resource summary.
        """
        ...

    @overload
    def store(
        self,
        text: str | None = None,
        *,
        topic: str,
        path: str | None = None,
        url: str | None = None,
        **kwargs,
    ) -> None:
        """Append content to an existing topic.

        Parameters
        ----------
        text:
            The text content to append. Optional if providing a file or URL.
        topic:
            Existing topic ID or slug to append to.
        url:
            Optional resource URL. Use to ingest content from the web into the topic.
        path:
            Path to a local file to upload as topic content. Use to ingest file content into the topic.
        """
        ...

    @kb
    def store(
        self,
        text: str | None = None,
        *,
        topic: str | None = None,
        title: str | None = None,
        slug: str | None = None,
        path: str | None = None,
        url: str | None = None,
        summary: str | None = None,
        **kwargs,
    ) -> None:
        if topic:
            try:
                self._store_to_existing_topic(
                    topic=topic,
                    text=text,
                    url=url,
                    path=path,
                )
            except NotFoundError:
                raise TopicNotFoundError(f"topic '{topic}' not found.")
        else:
            try:
                self._store_to_new_topic(
                    slug=slug,
                    title=title,
                    summary=summary,
                    text=text,
                    url=url,
                    path=path,
                )
            except ConflictError:
                raise TopicAlreadyExistsError(
                    f"topic with slug '{slug}' already exists."
                )

    def _store_to_existing_topic(
        self,
        topic: str,
        text: str | None = None,
        url: str | None = None,
        path: str | None = None,
    ) -> None:
        if not text and not path and not url:
            raise ValueError("At least one of text, path, or url must be provided.")
        base_args: dict[str, Any] = {}
        ruuid, rslug = _uuid_or_slug(topic)
        if ruuid:
            base_args["rid"] = ruuid
        else:
            assert rslug is not None
            base_args["slug"] = rslug
        update_resource_args = base_args.copy()
        field_id = uuid.uuid4().hex
        if text or url:
            if text:
                update_resource_args["texts"] = {
                    field_id: TextField(
                        body=text,
                        format=TextFormat.PLAIN,
                    )
                }
            if url:
                update_resource_args["links"] = {
                    field_id: LinkField(
                        uri=url,
                    )
                }
            self.kb.resource.update(**update_resource_args)
        if path:
            self.upload.file(
                path=path,
                field_id=field_id,
                **base_args,
            )

    def _store_to_new_topic(
        self,
        slug: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        text: str | None = None,
        url: str | None = None,
        path: str | None = None,
    ) -> None:
        if not text and not path and not url:
            raise ValueError("At least one of text, path, or url must be provided.")
        if title is None:
            title = _infer_title(slug=slug, text=text, path=path, url=url)
        if slug is None:
            slug = _slugify(title)
        create_args: dict[str, Any] = {
            "title": title,
            "slug": slug,
        }
        if summary is not None:
            create_args["summary"] = summary
        if text is not None:
            create_args["texts"] = {
                slug: TextField(
                    body=text,
                    format=TextFormat.PLAIN,
                )
            }
        if url is not None:
            create_args["links"] = {
                slug: LinkField(
                    uri=url,
                )
            }
        resource_id = self.kb.resource.create(**create_args)
        if path is not None:
            self.upload.file(
                path=path,
                rid=resource_id,
                field=slug,
            )

    # ── annotate ─────────────────────────────────────────────────────────────

    @overload
    def annotate(
        self,
        text: str,
        *,
        topic: str,
        user_id: str,
        context: list[AnnotationContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        annotation_id: str = ...,
        **kwargs,
    ) -> str:
        """Add an annotation to a specific topic.

        Parameters
        ----------
        text:
            The annotation text.
        topic:
            Topic ID or slug to annotate.
        user_id:
            An identifier for the user creating the annotation.
        context:
            Optional list of context messages to attach to the annotation.
        reasoning:
            Optional reasoning attached to the annotation.
        metadata:
            Optional metadata dictionary to attach to the annotation.
        annotation_id:
            Optional custom annotation ID. A random ID is generated if not provided.
        """
        ...

    @overload
    def annotate(
        self,
        text: str,
        *,
        user_id: str,
        context: list[AnnotationContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        annotation_id: str = ...,
        **kwargs,
    ) -> str:
        """Add a global annotation (not tied to any specific topic).

        Parameters
        ----------
        text:
            The annotation text.
        user_id:
            An identifier for the user creating the annotation. Each user gets their own dedicated resource for global annotations.
        context:
            Optional list of context messages to attach to the annotation.
        reasoning:
            Optional reasoning attached to the annotation.
        metadata:
            Optional metadata dictionary to attach to the annotation.
        annotation_id:
            Optional custom annotation ID. A random ID is generated if not provided.
        """
        ...

    @kb
    def annotate(
        self,
        text: str,
        *,
        topic: str | None = None,
        user_id: str,
        context: list[AnnotationContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        annotation_id: str = uuid.uuid4().hex,
        **kwargs,
    ) -> str:
        validate_annotation_id(annotation_id)
        validate_user_id(user_id)
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _ensure_global_annotations_resource(ndb, user_id)
        annotation_content = AnnotationContent(
            text=text,
            reasoning=reasoning,
            context=context,
            metadata=metadata,
        )
        message = InputMessage(
            timestamp=datetime.now(tz=timezone.utc),
            ident=annotation_id,
            type=MessageType.UNSET,
            content=InputMessageContent(
                text=annotation_content.model_dump_json(indent=2, exclude_none=True),
                format=MessageFormat.JSON,
                attachments=[],
                attachments_fields=[],
            ),
        )
        try:
            _add_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_annotation_field_id(user_id),
                message=message,
            )
        except UnprocessableEntity as e:
            if "Message identifiers must be unique field" in e.message:
                raise AnnotationAlreadyExistsError(
                    f"Annotation with ID '{annotation_id}' already exists."
                )
        return annotation_id

    # ── (fake) fact extraction ──────────────────────────────────────────────

    @kb
    def _extract_facts(
        self,
        annotation_id: str,
        *,
        topic: str,
        user_id: str,
        text: str,
        **kwargs,
    ) -> None:
        """
        XXX For demo purposes: in practice, this will not be needed as the facts
        will be extracted automatically by the processing engine.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _uuid_or_slug(topic)
        message = InputMessage(
            timestamp=datetime.now(tz=timezone.utc),
            ident=uuid.uuid4().hex,
            type=MessageType.UNSET,
            content=InputMessageContent(
                text=FactContent(
                    text=text,
                    related_annotation_ids=[annotation_id],
                ).model_dump_json(indent=2, exclude_none=True),
                format=MessageFormat.JSON,
                attachments=[],
                attachments_fields=[],
            ),
        )
        _add_conversation_message(
            ndb=ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_facts_field_id(user_id),
            message=message,
        )

    # ── context ─────────────────────────────────────────────────────────────

    @kb
    def context(
        self,
        *,
        topic: str,
        user_id: str,
        include_annotations: bool = False,
        **kwargs,
    ) -> list[ContextBlock]:
        """
        Return all context for a specific topic and user.
        This includes all the text fields of the topic as well as any annotations and facts created by the user for that topic.

        Parameters
        ----------
        topic:
            topic ID or slug to retrieve context for.
        user_id:
            An identifier for the user requesting the context. Used to include that user's annotations and facts in the context.
        include_annotations:
            Whether to include the user's annotations in the context. Defaults to False to reduce noise, but can be set to True to include them.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _uuid_or_slug(topic)
        resource = _get_resource_basic(
            ndb=ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
        )
        if ruuid is None:
            ruuid = resource.id
        user_resource_fields = _get_user_resource_fields(
            resource, user_id, include_annotations
        )
        augment_response: augment.AugmentResponse = ndb.ndb.augment(
            kbid=ndb.kbid,
            content=augment.AugmentRequest(
                fields=[
                    augment.AugmentFields(
                        given=user_resource_fields,
                        text=True,
                        full_conversation=True,
                    )
                ]
            ),
        )
        return [
            ContextBlock(id=field_id, text=augmented_field.text)
            for field_id, augmented_field in augment_response.fields.items()
            if augmented_field.text is not None
        ]

    # ── retrieve ─────────────────────────────────────────────────────────────

    @kb
    def retrieve(
        self,
        question: str,
        *,
        topic: str,
        user_id: str,
        top_k: int = 20,
        facts_only: bool = False,
        **kwargs,
    ) -> list[RelevantContextBlock]:
        """
        Retrieve relevant context blocks from the memory for a given question, scoped to a specific topic and user.

        Parameters
        ----------
        question:
            Natural-language question to retrieve context for.
        topic:
            Scope the retrieval to a single topic (ID or slug).
        user_id:
            An identifier for the user asking the question. Used to personalize retrieval results by including that user's annotations and facts.
        top_k:
            Maximum number of relevant context blocks to retrieve.
        facts_only:
            Whether to restrict the retrieval to only use facts extracted from the user's annotations, excluding all other content. Defaults to False.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        find_request = FindRequest(
            query=question,
            features=[
                FindOptions.SEMANTIC,
                FindOptions.KEYWORD,
            ],
            filter_expression=filters.FilterExpression(
                field=_build_field_filter_expression(
                    topic=topic, user_id=user_id, facts_only=facts_only
                )
            ),
            top_k=top_k,
            rephrase=True,
            reranker=PredictReranker(window=min(top_k * 5, 200)),
        )
        find_response: KnowledgeboxFindResults = ndb.ndb.find(
            kbid=ndb.kbid, content=find_request
        )
        return _parse_retrieve_result(find_response)

    # ── recall ───────────────────────────────────────────────────────────────

    @kb
    def recall(
        self,
        query: str,
        *,
        topic: str,
        user_id: str,
        context: list[ChatContextMessage] | None = None,
        facts_only: bool = False,
        **kwargs,
    ) -> RecallResult:
        """Ask a question and get a generative answer grounded in stored topics.

        Parameters
        ----------
        query:
            Natural-language question.
        topic:
            Scope the answer to a single topic (ID or slug).
        user_id:
            An identifier for the user asking the question. Used for personalization of the answer by including that user's annotations and facts as context.
        context:
            Optional list of past messages to include as additional context for the recall. Messages should be ordered from oldest to most recent.
        facts_only:
            Whether to restrict the recall to only use facts extracted from the user's annotations, excluding all other content. Defaults to False.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        top_k = 5
        user_global_facts = self._get_user_global_facts(ndb, user_id)
        ask_request = AskRequest(
            query=query,
            top_k=5,
            citations=CitationsType.LLM_FOOTNOTES,
            rephrase=True,
            reranker=PredictReranker(window=min(top_k * 5, 200)),
            prefer_markdown=True,
            filter_expression=filters.FilterExpression(
                field=_build_field_filter_expression(
                    topic=topic, user_id=user_id, facts_only=facts_only
                )
            ),
            chat_history=context,
            extra_context=user_global_facts,
        )
        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=kbid, content=ask_request)
        return _parse_recall_result(ask_response)

    # ── annotations ─────────────────────────────────────────────────────────

    def _get_user_global_facts(self, ndb: NucliaDBClient, user_id: str) -> list[str]:
        resource_slug = _global_annotations_slug(user_id)
        try:
            resource = _get_resource_basic(
                ndb, kbid=ndb.kbid, rid=None, slug=resource_slug
            )
            resource_id = resource.id
        except NotFoundError:
            return []
        facts_field_id = _facts_field_id(user_id)
        augment_request = augment.AugmentRequest(
            resources=[
                augment.AugmentResources(
                    given=[resource_id],
                    fields=[
                        augment.AugmentResourceFields(
                            text=True,
                            filters=[
                                filters.Field(
                                    type=FieldTypeName.CONVERSATION,
                                    name=facts_field_id,
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        augment_response: augment.AugmentResponse = ndb.ndb.augment(
            kbid=ndb.kbid, content=augment_request
        )
        if facts_field_id not in augment_response.fields:
            return []
        global_facts = []
        augmented_field = augment_response.fields[facts_field_id]
        for message in augmented_field.messages or []:
            try:
                fact = Fact.from_conversation_message(message)
            except Exception as e:
                logger.warning(f"Failed to parse fact from conversation message: {e}")
                continue
            global_facts.append(fact.content.text)
        return global_facts

    @overload
    def annotations(
        self,
        *,
        topic: str,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Annotation]:
        """Get all annotations created by a user for a specific topic.

        Parameters
        ----------
        topic:
            Topic ID or slug to retrieve annotations for.
        user_id:
            An identifier for the user whose annotations to retrieve.
        recent_first:
            Whether to return the annotations ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @overload
    def annotations(
        self,
        *,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Annotation]:
        """Get all global annotations created by a user (not tied to any specific topic).

        Parameters
        ----------
        user_id:
            An identifier for the user whose global annotations to retrieve.
        recent_first:
            Whether to return the annotations ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @kb
    def annotations(
        self,
        *,
        topic: str | None = None,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Annotation]:
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _global_annotations_slug(user_id)
        for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_annotation_field_id(user_id),
            recent_first=recent_first,
        ):
            yield Annotation.from_conversation_message(message)

    # ── facts ───────────────────────────────────────────────────────────────

    @kb
    def facts(
        self,
        *,
        topic: str,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Fact]:
        """Get all extracted facts from annotations of a user for a specific topic (from most recent to oldest).

        Parameters
        ----------
        topic:
            topic ID or slug to retrieve annotations for.
        user_id:
            An identifier for the user whose annotations to retrieve.
        recent_first:
            Whether to return the facts ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _uuid_or_slug(topic)
        for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_facts_field_id(user_id),
            recent_first=recent_first,
        ):
            yield Fact.from_conversation_message(message)

    # ── graph ───────────────────────────────────────────────────────────────

    @kb
    def graph(
        self,
        *,
        topic: str,
        user_id: str,
        facts_only: bool = False,
        **kwargs,
    ) -> list[GraphEdge]:
        """Get the topic graph including all extracted entities and relations from the topic content and the annotations of the specified user.

        Parameters
        ----------
        topic:
            topic ID or slug to retrieve graph for.
        user_id:
            An identifier for the user whose annotations to include in the graph.
        facts_only:
            Whether to restrict the graph to only include entities and relations extracted from the facts, excluding those extracted from all other content. Defaults to False.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        graph_request = graph.requests.GraphSearchRequest(
            top_k=500,
            filter_expression=graph.requests.GraphFilterExpression(
                field=_build_field_filter_expression(
                    topic=topic, user_id=user_id, facts_only=facts_only
                )
            ),
            # Ignore all paths that start or end at the resource: we are interested in entity to entity paths.
            query=graph.requests.And(
                operands=[
                    graph.requests.AnyNode(
                        type=graph.requests.RelationNodeType.ENTITY,
                    ),
                    graph.requests.Not(
                        operand=graph.requests.AnyNode(
                            type=graph.requests.RelationNodeType.RESOURCE,
                        )
                    ),
                ]
            ),
        )
        graph_response: graph.responses.GraphSearchResponse = ndb.ndb.graph_search(
            kbid=ndb.kbid,
            content=graph_request,
        )
        return _parse_graph_result(graph_response)

    # ── forget ──────────────────────────────────────────────────────────────

    @overload
    def forget(
        self,
        *,
        topic: str,
        user_id: str,
        annotation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Delete a specific annotation from a topic or all the annotations created by the user.

        Parameters
        ----------
        topic:
            topic ID or slug to target.
        user_id:
            An identifier for the user requesting the deletion. Used to ensure users can only delete their own annotations.
        annotation_id:
            Optional identifier of the specific annotation to delete. If not provided, all annotations created by the user for the topic will be deleted.
        """
        ...

    @overload
    def forget(
        self,
        *,
        user_id: str,
        annotation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Delete a specific global annotation or all global annotations created by the user.

        Parameters
        ----------
        user_id:
            An identifier for the user requesting the deletion.
        annotation_id:
            Optional identifier of the specific global annotation to delete. If not provided, all global annotations created by the user will be deleted.
        """
        ...

    @overload
    def forget(
        self,
        *,
        topic: str,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """Deletes a topic from the memory. This action is irreversible, so the confirm flag must be set to True to proceed with deletion.

        Parameters
        ----------
        topic:
            topic ID or slug to target.
        confirm:
            When set to True, confirms the deletion of the topic.
        """
        ...

    @kb
    def forget(
        self,
        *,
        topic: str | None = None,
        user_id: str | None = None,
        annotation_id: str | None = None,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        ndb: NucliaDBClient = kwargs["ndb"]
        if user_id is not None:
            if topic is not None:
                ruuid, rslug = _uuid_or_slug(topic)
            else:
                ruuid = None
                rslug = _global_annotations_slug(user_id)
            if annotation_id is not None:
                # Delete a specific annotation for that user on that topic (or global)
                try:
                    _delete_conversation_message(
                        ndb=ndb,
                        kbid=ndb.kbid,
                        rid=ruuid,
                        slug=rslug,
                        field_id=_annotation_field_id(user_id),
                        message_id=annotation_id,
                    )
                except NotFoundError:
                    pass
            else:
                # Delete all annotations for that user on that topic (or global)
                try:
                    _delete_resource_field(
                        ndb=ndb,
                        kbid=ndb.kbid,
                        rid=ruuid,
                        slug=rslug,
                        field_type=FieldTypeName.CONVERSATION,
                        field_id=_annotation_field_id(user_id),
                    )
                except NotFoundError:
                    pass
        else:
            # Delete entire topic
            assert topic is not None, "Either user_id or topic must be provided."
            ruuid, rslug = _uuid_or_slug(topic)
            if not confirm:
                raise ValueError(
                    "Deleting an entire topic is irreversible. To confirm, set confirm=True."
                )
            try:
                self.kb.resource.delete(rid=ruuid, slug=rslug)
            except NotFoundError:
                raise TopicNotFoundError(f"topic '{topic}' not found.")

    # ── get ─────────────────────────────────────────────────────────────────

    @kb
    def get(
        self,
        *,
        topic: str,
        **kwargs,
    ) -> Topic:
        """Retrieve an topic by ID or slug."""
        ruuid, rslug = _uuid_or_slug(topic)
        try:
            resource: Resource = self.kb.resource.get(
                rid=ruuid,
                slug=rslug,
                show=[ResourceProperties.BASIC.value, ResourceProperties.ERRORS.value],
            )
        except NotFoundError:
            raise TopicNotFoundError(f"topic '{topic}' not found.")
        return Topic(
            id=resource.id,
            slug=resource.slug or "",
            title=resource.title or "",
            summary=resource.summary,
            status=_get_topic_status(resource),
        )

    # ── list ─────────────────────────────────────────────────────────────────

    @kb
    def list(
        self,
        *,
        query: str = "",
        page: int = 0,
        size: int = 20,
        **kwargs,
    ) -> TopicPage:
        """List topics in this memory.

        Parameters
        ----------
        query:
            Filter by title (uses ``/catalog`` endpoint).
        page:
            Zero-based page index.
        size:
            Page size.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        catalog_request = CatalogRequest(
            query=query,
            page_number=page,
            page_size=size,
            show=[
                ResourceProperties.BASIC,
            ],
        )
        catalog_response: CatalogResponse = ndb.ndb.catalog(
            kbid=ndb.kbid, content=catalog_request
        )
        topic_page = TopicPage(
            items=[
                Topic(
                    id=resource.id,
                    slug=resource.slug or "",
                    title=resource.title or "",
                    summary=resource.summary,
                    status=_get_topic_status(resource),
                )
                for resource in catalog_response.resources.values()
            ],
            total=catalog_response.fulltext.total if catalog_response.fulltext else 0,
            has_more=catalog_response.fulltext.next_page
            if catalog_response.fulltext
            else False,
        )
        return topic_page


# ─── Async Memory (TODO) ─────────────────────────────────────────────────────────────


# ─── Utils ─────────────────────────────────────────────────────────────


def _build_field_filter_expression(
    topic: str,
    user_id: str,
    facts_only: bool = False,
) -> filters.FieldFilterExpression:
    """
    Build a filter expression to scope recall or retrieve to a specific topic and include user annotations and facts while
    excluding other users' annotations and facts.
    """
    ruuid, rslug = _uuid_or_slug(topic)
    if facts_only:
        return filters.And(
            operands=[
                filters.Or(
                    operands=[
                        filters.Resource(id=ruuid, slug=rslug),
                        filters.Resource(slug=_global_annotations_slug(user_id)),
                    ]
                ),
                filters.Field(
                    type=FieldTypeName.CONVERSATION,
                    name=_facts_field_id(user_id),
                ),
            ]
        )
    else:
        return filters.And(
            operands=[
                filters.Or(
                    operands=[
                        filters.Resource(id=ruuid, slug=rslug),
                        filters.Resource(slug=_global_annotations_slug(user_id)),
                    ]
                ),
                filters.Or(
                    operands=[
                        filters.Not(
                            operand=filters.ResourceFieldPrefix(
                                resource_id=ruuid,
                                resource_slug=rslug,
                                field_type=FieldTypeName.CONVERSATION,
                                field_name_prefix=MEMORY_FIELD_PREFIX,
                            )
                        ),
                        filters.Field(
                            type=FieldTypeName.CONVERSATION,
                            name=_annotation_field_id(user_id),
                        ),
                        filters.Field(
                            type=FieldTypeName.CONVERSATION,
                            name=_facts_field_id(user_id),
                        ),
                    ]
                ),
            ]
        )


def _uuid_or_slug(topic_uuid_or_slug: str) -> Union[tuple[str, None], tuple[None, str]]:
    """Helper to determine if topic identifier is a UUID or slug."""
    try:
        # If this succeeds, topic is a uuid
        return str(uuid.UUID(topic_uuid_or_slug)), None
    except ValueError:
        # Otherwise, treat it as a slug
        return None, topic_uuid_or_slug


def _slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    Slugs cannot contain special characters or spaces, and are typically lowercase with words separated by hyphens.

    Examples:
    - "My Vacation Policy" -> "my-vacation-policy"
    - "Project Plan v2.0!" -> "project-plan-v20"
    - "café au lait" -> "cafe-au-lait"
    """
    # Normalize unicode (e.g. "café" -> "cafe")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    allowed_characters = string.ascii_letters + string.digits + " " + "-"
    cleaned_text = "".join(c if c in allowed_characters else " " for c in text)
    slug = cleaned_text.lower().replace(" ", "-")
    # Strip leading/trailing ones
    slug = slug.strip("-")
    return slug or "untitled"


def _infer_title(
    *,
    slug: str | None = None,
    text: str | None = None,
    path: str | None = None,
    url: str | None = None,
) -> str:
    if slug:
        return slug.replace("-", " ").title()
    elif text:
        # Use first non-empty line, truncated at a word boundary
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()), ""
        )
        truncated = first_line[:50]
        # Avoid cutting mid-word
        if len(first_line) > 50 and " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return truncated.title() or "Untitled Topic"
    elif path:
        filename = path.split("/")[-1]
        return filename.replace("-", " ").replace("_", " ").title()
    elif url:
        parsed = urlparse(url)
        # Use last non-empty path segment, strip query/fragment
        segments = [s for s in parsed.path.split("/") if s]
        name = segments[-1] if segments else parsed.netloc
        return name.replace("-", " ").replace("_", " ").title() or "Untitled Topic"
    else:
        return "Untitled Topic"


def _parse_recall_result(
    ask_response: SyncAskResponse,
) -> RecallResult:
    """Parse an LLM footnotes answer into clean text and citations mapping."""
    parts = ask_response.answer.rsplit("\n\n", 1)
    answer_text = parts[0]
    citations: dict[str, RelevantContextBlock] = {}
    if len(parts) > 1:
        retrieved_paragraphs = {
            paragraph.id: paragraph
            for resource in ask_response.retrieval_results.resources.values()
            for field in resource.fields.values()
            for paragraph in field.paragraphs.values()
        }
        for match in re.finditer(r"\[(\d+)\]:\s*(\S+)", parts[1]):
            footnote_id = match.group(1)
            block_id = match.group(2)
            chunk_id = ask_response.citation_footnote_to_context.get(block_id)
            if chunk_id and chunk_id in retrieved_paragraphs:
                citations[footnote_id] = RelevantContextBlock(
                    id=chunk_id,
                    text=retrieved_paragraphs[chunk_id].text,
                    score=retrieved_paragraphs[chunk_id].score,
                )
    return RecallResult(answer=answer_text, citations=citations)


def _parse_retrieve_result(
    find_response: KnowledgeboxFindResults,
) -> list[RelevantContextBlock]:
    relevant_paragraphs = {
        pid: paragraph
        for resource in find_response.resources.values()
        for field in resource.fields.values()
        for pid, paragraph in field.paragraphs.items()
    }
    return [
        RelevantContextBlock(
            id=pid,
            text=par.text,
            score=par.score,
        )
        for pid in find_response.best_matches
        if (par := relevant_paragraphs.get(pid)) is not None
    ]


def _parse_graph_result(
    graph_response: graph.responses.GraphSearchResponse,
) -> list[GraphEdge]:
    edges = []
    for path in graph_response.paths:
        context_block_id = (
            path.metadata.paragraph_id if path.metadata is not None else None
        )
        edges.append(
            GraphEdge(
                source=GraphNode(
                    type=path.source.type.value,
                    value=path.source.value,
                    group=path.source.group,
                ),
                relation=GraphRelation(
                    type=path.relation.type.value, label=path.relation.label
                ),
                destination=GraphNode(
                    type=path.destination.type.value,
                    value=path.destination.value,
                    group=path.destination.group,
                ),
                metadata=GraphEdgeMetadata(context_block_id=context_block_id),
            )
        )
    return edges


def _get_topic_status(resource: Resource) -> str:
    """
    We check for title field status as a proxy for the overall resource processing
    status, since the title is a required field that is processed in the first steps
    of resource creation. If the title field has an error or is still being processed,
    we can infer that the entire resource is not fully processed yet.
    """
    try:
        assert resource.data is not None
        assert resource.data.generics is not None
        assert resource.data.generics["title"].status is not None
        status = resource.data.generics["title"].status.lower()
    except (AssertionError, KeyError, ValueError):
        status = "unknown"
    return status


def _delete_resource_field(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
) -> None:
    """
    Deletes a field of a resource.
    """
    delete_field_args = {
        "kbid": kbid,
        "field_type": field_type.value,
        "field_id": field_id,
    }
    if rid:
        delete_field_args["rid"] = rid
        delete_field = ndb.ndb.delete_field_by_id
    else:
        assert slug is not None
        delete_field_args["slug"] = slug
        delete_field = ndb.ndb.delete_field_by_slug
    delete_field(**delete_field_args)


def _delete_conversation_message(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message_id: str,
) -> None:
    """
    Deletes a conversation message from a resource conversation field.
    """
    delete_conversation_message_args = {
        "kbid": kbid,
        "field_id": field_id,
        "message_id": message_id,
    }
    if rid:
        delete_conversation_message_args["rid"] = rid
        delete_conversation_message = ndb.ndb.delete_conversation_message
    else:
        assert slug is not None
        delete_conversation_message_args["slug"] = slug
        delete_conversation_message = ndb.ndb.delete_conversation_message_by_slug
    delete_conversation_message(**delete_conversation_message_args)


def _add_conversation_message(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message: InputMessage,
) -> None:
    add_conversation_args = {
        "kbid": kbid,
        "field_id": field_id,
        "content": [message],
    }
    if rid:
        add_conversation_args["rid"] = rid
        add_conversation_message = ndb.ndb.add_conversation_message
    else:
        assert slug is not None
        add_conversation_args["slug"] = slug
        add_conversation_message = ndb.ndb.add_conversation_message_by_slug
    add_conversation_message(**add_conversation_args)


def _iter_conversation_messages(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    recent_first: bool = True,
) -> Iterator[Message]:
    try:
        field = _get_resource_field(
            ndb=ndb,
            kbid=kbid,
            rid=rid,
            slug=slug,
            field_type=FieldTypeName.CONVERSATION,
            field_id=field_id,
        )
        if field.value is None:
            return
    except NotFoundError:
        return
    conv = cast(Conversation, field.value)

    if recent_first:
        current_page = conv.pages
    else:
        current_page = 1

    while True:
        if conv.total == 0:
            break
        if (recent_first and current_page <= 0) or (
            not recent_first and current_page > conv.total
        ):
            # No more pages to fetch
            break
        page = _get_page_of_conversation_messages(
            kbid=kbid,
            rid=rid,
            slug=slug,
            field_id=field_id,
            ndb=ndb,
            page=str(current_page),
        )
        if recent_first:
            for message in reversed(page):
                yield message
            current_page -= 1
        else:
            for message in page:
                yield message
            current_page += 1


def _get_page_of_conversation_messages(
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    ndb: NucliaDBClient,
    page: str,
) -> list[Message]:
    kbid = ndb.kbid
    field: ResourceField = _get_resource_field(
        ndb=ndb,
        kbid=kbid,
        rid=rid,
        slug=slug,
        field_type=FieldTypeName.CONVERSATION,
        field_id=field_id,
        page=page,
    )
    if field.value is None:
        return []
    conversation = cast(Conversation, field.value)
    return [
        message
        for message in conversation.messages or []
        if message.content.text  # Skip deleted messages
    ]


def _get_resource_basic(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> Resource:
    get_resource_args = {
        "kbid": kbid,
        "query_params": {
            "show": [
                ResourceProperties.BASIC.value,
                ResourceProperties.ERRORS.value,
            ],
        },
    }
    if rid:
        get_resource_args["rid"] = rid
        get_resource = ndb.ndb.get_resource_by_id
    else:
        assert slug is not None
        get_resource_args["slug"] = slug
        get_resource = ndb.ndb.get_resource_by_slug
    resource: Resource = get_resource(**get_resource_args)
    return resource


def _get_resource_field(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
    page: str | None = None,
) -> ResourceField:
    get_field_args: dict[str, Any] = {
        "kbid": kbid,
        "field_type": field_type.value,
        "field_id": field_id,
    }
    if page is not None:
        get_field_args["query_params"] = {"page": page}
    if rid:
        get_field_args["rid"] = rid
        get_field = ndb.ndb.get_resource_field
    else:
        assert slug is not None
        get_field_args["slug"] = slug
        get_field = ndb.ndb.get_resource_field_by_slug
    field: ResourceField = get_field(**get_field_args)
    return field


def _is_memory_field(field_type: FieldTypeName, field_id: str) -> bool:
    return field_type == FieldTypeName.CONVERSATION and (
        field_id.startswith(MEMORY_FIELD_PREFIX)
        or field_id.startswith(FACTS_FIELD_PREFIX)
    )


def _get_user_resource_fields(
    resource: Resource, user_id: str, include_annotations: bool
) -> list[str]:
    fields: list[tuple[FieldTypeName, str]] = []
    if resource.data is None:
        return []
    fields.extend(
        (FieldTypeName.GENERIC, field_id)
        for field_id in (resource.data.generics or {}).keys()
    )
    fields.extend(
        (FieldTypeName.TEXT, field_id)
        for field_id in (resource.data.texts or {}).keys()
    )
    fields.extend(
        (FieldTypeName.LINK, field_id)
        for field_id in (resource.data.links or {}).keys()
    )
    fields.extend(
        (FieldTypeName.FILE, field_id)
        for field_id in (resource.data.files or {}).keys()
    )
    fields.extend(
        (FieldTypeName.CONVERSATION, field_id)
        for field_id in (resource.data.conversations or {}).keys()
        if not _is_memory_field(FieldTypeName.CONVERSATION, field_id)
        or (field_id == _annotation_field_id(user_id) and include_annotations)
        or field_id == _facts_field_id(user_id)
    )
    return [
        _to_field_id_string(resource.id, field_type, field_id)
        for field_type, field_id in fields
    ]


def _to_field_id_string(rid: str, field_type: FieldTypeName, field_id: str) -> str:
    return f"{rid}/{field_type.abbreviation()}/{field_id}"


def _annotation_field_id(user_id: str) -> str:
    return f"{MEMORY_FIELD_PREFIX}{user_id}"


def _facts_field_id(user_id: str) -> str:
    return f"{FACTS_FIELD_PREFIX}{user_id}"


def _global_annotations_slug(user_id: str) -> str:
    """Return the predictable slug for the per-user global-annotations resource."""
    return f"{GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX}-{user_id}"


def _ensure_global_annotations_resource(ndb: NucliaDBClient, user_id: str) -> str:
    """
    Ensure the per-user global-annotations resource exists, creating it if necessary.
    Returns the resource slug.
    """
    slug = _global_annotations_slug(user_id)
    if not ndb.ndb.exists_resource_by_slug(kbid=ndb.kbid, slug=slug):
        ndb.ndb.create_resource(
            kbid=ndb.kbid,
            content={"title": f"Memory global annotations - {user_id}", "slug": slug},
        )
    return slug


def validate_user_id(user_id: str) -> None:
    field_id_pattern = r"^[a-zA-Z0-9:_-]+$"
    if not re.match(field_id_pattern, user_id):
        raise ValueError(
            f"Invalid User ID '{user_id}'. User IDs can only contain letters, numbers, underscores, colons, and hyphens."
        )


def validate_annotation_id(annotation_id: str) -> None:
    """
    Conditions:
    - Up to 128 characters
    - Can only contain letters, numbers, underscores, colons, and hyphens
    - Cannot be "0"
    - Cannot contain "/"
    """
    if len(annotation_id) > 128:
        raise ValueError(
            f"Invalid annotation ID '{annotation_id}'. Annotation IDs must be at most 128 characters."
        )
    if annotation_id == "0":
        raise ValueError('Annotation ID cannot be "0"')
    if "/" in annotation_id:
        raise ValueError('Annotation ID cannot contain "/"')
    id_pattern = r"^[a-zA-Z0-9:_-]+$"
    if not re.match(id_pattern, annotation_id):
        raise ValueError(
            f"Invalid annotation ID '{annotation_id}'. Annotation IDs can only contain letters, numbers, underscores, colons, and hyphens."
        )
