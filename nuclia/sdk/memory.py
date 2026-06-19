from __future__ import annotations

import logging
import re
import string
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator, Union, cast, overload

from nuclia_models.worker.proto import (
    ApplyTo,
    DataAugmentation,
    EntityDefinition,
    Filter,
    GraphExtractionExample,
    LLMConfig,
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
    CustomPrompt,
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
FACTS_FIELD_PREFIX = "da-facts-"
GRAPH_EXTRACTION_TEMPLATE = "memory-graph-{task_ident}"
GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX = "memory-global-entries"


# ─── Exceptions ─────────────────────────────────────────────────────────────


class TopicAlreadyExistsError(Exception):
    """Raised when attempting to create a new topic with a slug that already exists."""

    pass


class TopicNotFoundError(Exception):
    """Raised when an topic with the specified ID or slug cannot be found."""

    pass


class EntryAlreadyExistsError(Exception):
    """Raised when attempting to create a new entry with an ID that already exists for the topic and user."""

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


class EntryContextMessage(BaseModel):
    """A context message attached to an entry."""

    author: str
    text: str


class EntryContent(BaseModel):
    """The content of the entry with separate fields for the text, reasoning, and context."""

    text: str
    reasoning: str | None = None
    context: list[EntryContextMessage] | None = None
    metadata: dict[str, Any] | None = None


class Entry(BaseModel):
    """A single entry message attached to an topic."""

    id: str
    timestamp: datetime
    content: EntryContent

    @classmethod
    def from_conversation_message(cls, message: Message) -> "Entry":
        content = EntryContent.model_validate_json(message.content.text or "")
        assert message.ident is not None
        assert message.timestamp is not None
        return cls(
            id=message.ident,
            timestamp=message.timestamp,
            content=content,
        )


class FactContent(BaseModel):
    """
    The content of a fact extracted from an entry, including the fact text and a list of
    related entry IDs that were used as evidence for the fact.
    """

    text: str
    reasoning: str | None = None
    related_entry_ids: list[str] = []


class Fact(BaseModel):
    """A single fact extracted from an entry"""

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


# ─── Sync Memory ─────────────────────────────────────────────────────────────


class NucliaMemory:
    task_ident = "memory"

    def __init__(self):
        self.kb = NucliaKB()
        self.upload = NucliaUpload()
        self.tasks = NucliaTask()

    # ── initialize ───────────────────────────────────────────────────────

    @kb
    def initialize(
        self,
        llm_config: LLMConfig | None = None,
        rules: list[str] | None = None,
        graph_extraction: bool | None = None,
        entity_defs: list[EntityDefinition] | None = None,
        examples: list[GraphExtractionExample] | None = None,
        overwrite: bool = False,
        **kwargs,
    ) -> None:
        """Ensure the memory task is configured for this knowledge box.

        This method should be called once before using the memory to make sure
        the required background task is set up in the KB.
        """
        kb_tasks = self.tasks.list()
        existing_task = next(
            (task for task in kb_tasks.configs if task.task.name == TaskName.MEMORY),
            None,
        )
        if existing_task is None:
            # Configure the memory task for the first time
            self.tasks.start(
                task_name=TaskName.MEMORY,
                apply=ApplyOptions.NEW,
                parameters=DataAugmentation(
                    name=self.task_ident,
                    on=ApplyTo.FIELD,
                    filter=Filter(
                        field_types=[FieldTypeName.CONVERSATION.abbreviation()],
                        apply_to_agent_generated_fields=False,
                    ),
                    operations=[
                        Operation(
                            memory=MemoryOperation(
                                ident=self.task_ident,
                                rules=rules or [],
                                graph_extraction=graph_extraction
                                if graph_extraction is not None
                                else True,
                                entity_defs=entity_defs or [],
                                examples=examples or [],
                            )
                        )
                    ],
                    llm=llm_config or LLMConfig(),
                ),
            )
        else:
            op_changes = (
                rules is not None
                or graph_extraction is not None
                or entity_defs is not None
                or examples is not None
            )
            llm_changes = llm_config is not None
            if not op_changes and not llm_changes:
                # Nothing to update, so we can skip the update
                return
            # Check if the existing task has the same parameters
            op = Operation(
                memory=MemoryOperation(
                    ident=self.task_ident,
                    rules=rules or [],
                    graph_extraction=graph_extraction
                    if graph_extraction is not None
                    else True,
                    entity_defs=entity_defs or [],
                    examples=examples or [],
                )
            )
            llm = llm_config or LLMConfig()
            existing_params = existing_task.parameters
            assert (
                existing_params is not None and len(existing_params.operations) == 1
            ), "Existing memory task has no operations configured."
            if (
                op_changes
                and existing_params.operations[0] != op
                or llm_changes
                and existing_params.llm != llm
            ):
                if not overwrite:
                    raise ValueError(
                        "Memory task is already configured with different parameters. "
                        "Use overwrite=True to replace the existing configuration."
                    )
                else:
                    new_params = existing_params.model_copy()
                    if op_changes:
                        new_params.operations = [op]
                    if llm_changes:
                        new_params.llm = llm
                    self.tasks.update(
                        task_id=existing_task.id,
                        task_name=TaskName.MEMORY,
                        parameters=new_params,
                    )

    # ── topic management ────────────────────────────────────────────────────────────

    @kb
    def get_topic(
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

    @kb
    def list_topics(
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

    @kb
    def create_topic(
        self,
        *,
        title: str,
        slug: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
    ) -> str:
        """
        Create a new topic.

        Returns the ID of the newly created topic.

        Parameters
        ----------
        title:
            The title of the topic.
        slug:
            Optional slug for the topic. If not provided, a slug will be generated from the title.
        summary:
            Optional summary for the topic.
        texts:
            Optional new text content for the topic. A dictionary mapping field IDs to text content.
        urls:
            Optional new URLs for the topic. A dictionary mapping field IDs to URLs.
        file_paths:
            Optional new file paths for the topic. A dictionary mapping field IDs to file paths.
        """
        try:
            return self._create_new_topic(
                title=title,
                slug=slug,
                summary=summary,
                texts=texts,
                urls=urls,
                file_paths=file_paths,
            )
        except ConflictError:
            raise TopicAlreadyExistsError(f"topic with slug '{slug}' already exists.")

    @kb
    def update_topic(
        self,
        topic: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
    ) -> None:
        """
        Update an existing topic.

        Parameters
        ----------
        topic:
            The ID or slug of the topic to update.
        title:
            Optional new title for the topic.
        slug:
            Optional new slug for the topic.
        summary:
            Optional new summary for the topic.
        texts:
            Optional new text content for the topic. A dictionary mapping field IDs to text content.
        urls:
            Optional new URLs for the topic. A dictionary mapping field IDs to URLs.
        file_paths:
            Optional new file paths for the topic. A dictionary mapping field IDs to file paths.
        """
        try:
            self._update_topic(
                topic=topic,
                title=title,
                summary=summary,
                texts=texts,
                urls=urls,
                file_paths=file_paths,
            )
        except NotFoundError:
            raise TopicNotFoundError(f"topic '{topic}' not found.")

    @kb
    def delete_topic(
        self,
        topic: str,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """
        Delete an existing topic.

        Parameters
        ----------
        topic:
            The ID or slug of the topic to delete.
        """
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

    def _update_topic(
        self,
        topic: str,
        title: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
    ) -> None:
        base_args: dict[str, Any] = {}
        ruuid, rslug = _uuid_or_slug(topic)
        if ruuid:
            base_args["rid"] = ruuid
        else:
            assert rslug is not None
            base_args["slug"] = rslug
        update_resource_args = base_args.copy()
        if title:
            update_resource_args["title"] = title
        if summary:
            update_resource_args["summary"] = summary
        if texts or urls:
            if texts:
                update_resource_args["texts"] = {
                    fid: TextField(
                        body=text,
                        format=TextFormat.PLAIN,
                    )
                    for fid, text in texts.items()
                }
            if urls:
                update_resource_args["links"] = {
                    fid: LinkField(
                        uri=url,
                    )
                    for fid, url in urls.items()
                }
            self.kb.resource.update(**update_resource_args)
        if file_paths:
            if ruuid is None:
                resource = self.kb.resource.get(slug=rslug)
                ruuid = resource.id
            for fid, path in file_paths.items():
                self.upload.file(
                    path=path,
                    rid=ruuid,
                    field_id=fid,
                    **base_args,
                )

    def _create_new_topic(
        self,
        title: str,
        slug: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
    ) -> str:
        if slug is None:
            slug = _slugify(title)
        create_args: dict[str, Any] = {
            "title": title,
            "slug": slug,
        }
        if summary is not None:
            create_args["summary"] = summary
        if texts is not None:
            create_args["texts"] = {
                fid: TextField(
                    body=text,
                    format=TextFormat.PLAIN,
                )
                for fid, text in texts.items()
            }
        if urls is not None:
            create_args["links"] = {
                fid: LinkField(
                    uri=url,
                )
                for fid, url in urls.items()
            }
        resource_id = self.kb.resource.create(**create_args)
        if file_paths is not None:
            for fid, path in file_paths.items():
                self.upload.file(
                    path=path,
                    rid=resource_id,
                    field=fid,
                )
        return resource_id

    # ── remember ─────────────────────────────────────────────────────────────

    @overload
    def remember(
        self,
        text: str,
        *,
        topic: str,
        user_id: str,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str = ...,
        **kwargs,
    ) -> str:
        """Add a memory entry to a specific topic.

        Parameters
        ----------
        text:
            The memory entry text.
        topic:
            Topic ID or slug to remember.
        user_id:
            An identifier for the user creating the memory entry.
        context:
            Optional list of context messages to attach to the memory entry.
        reasoning:
            Optional reasoning attached to the memory entry.
        metadata:
            Optional metadata dictionary to attach to the memory entry.
        entry_id:
            Optional custom entry ID. A random ID is generated if not provided.
        """
        ...

    @overload
    def remember(
        self,
        text: str,
        *,
        user_id: str,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str = ...,
        **kwargs,
    ) -> str:
        """Add a global memory entry (not tied to any specific topic).

        Parameters
        ----------
        text:
            The memory entry text.
        user_id:
            An identifier for the user creating the memory entry. Each user gets their own dedicated resource for global memory entries.
        context:
            Optional list of context messages to attach to the memory entry.
        reasoning:
            Optional reasoning attached to the memory entry.
        metadata:
            Optional metadata dictionary to attach to the memory entry.
        entry_id:
            Optional custom entry ID. A random ID is generated if not provided.
        """
        ...

    @kb
    def remember(
        self,
        text: str,
        *,
        topic: str | None = None,
        user_id: str,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str = uuid.uuid4().hex,
        **kwargs,
    ) -> str:
        validate_entry_id(entry_id)
        validate_user_id(user_id)
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _ensure_global_entries_resource(ndb, user_id)
        entry_content = EntryContent(
            text=text,
            reasoning=reasoning,
            context=context,
            metadata=metadata,
        )
        message = InputMessage(
            timestamp=datetime.now(tz=timezone.utc),
            ident=entry_id,
            type=MessageType.UNSET,
            content=InputMessageContent(
                text=entry_content.model_dump_json(indent=2, exclude_none=True),
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
                field_id=_entries_field_id(user_id),
                message=message,
            )
        except UnprocessableEntity as e:
            if "Message identifiers must be unique field" in e.message:
                raise EntryAlreadyExistsError(
                    f"Entry with ID '{entry_id}' already exists."
                )
        return entry_id

    # ── recall ─────────────────────────────────────────────────────────────

    @kb
    def recall(
        self,
        question: str,
        *,
        topic: str,
        user_id: str,
        top_k: int = 20,
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
            An identifier for the user asking the question. Used to personalize retrieval results by including that user's entries and facts.
        top_k:
            Maximum number of relevant context blocks to retrieve.
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
                    self.task_ident,
                    topic=topic,
                    user_id=user_id,
                )
            ),
            top_k=top_k,
            rephrase=True,
            reranker=PredictReranker(window=min(top_k * 5, 200)),
        )
        find_response: KnowledgeboxFindResults = ndb.ndb.find(
            kbid=ndb.kbid, content=find_request
        )
        return _parse_recall_result(find_response)

    # ── ask ───────────────────────────────────────────────────────────────

    @kb
    def ask(
        self,
        query: str,
        *,
        topic: str,
        user_id: str | None = None,
        context: list[ChatContextMessage] | None = None,
        include_global_facts: bool = False,
        extra_context: list[str] | None = None,
        custom_prompt: CustomPrompt | None = None,
        ask_request_overrides: dict[str, Any] | None = None,
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
            An identifier for the user asking the question. Used for personalization of the answer by including that user's entries and facts as context.
        context:
            Optional list of past messages to include as additional context for the recall. Messages should be ordered from oldest to most recent.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        top_k = 5

        global_facts: list[str] = []
        global_facts_rid = None
        topic_facts: list[str] = []
        if user_id:
            if include_global_facts:
                global_facts_rid, global_facts = self._get_user_global_facts(
                    ndb, user_id
                )
            topic_facts = [
                fact.content.text for fact in self.facts(topic=topic, user_id=user_id)
            ]

        ask_request = AskRequest(
            query=query,
            top_k=5,
            citations=CitationsType.LLM_FOOTNOTES,
            rephrase=False,
            reranker=PredictReranker(window=min(top_k * 5, 200)),
            prompt=custom_prompt,
            filter_expression=filters.FilterExpression(
                field=_build_field_filter_expression(
                    self.task_ident,
                    topic=topic,
                    user_id=user_id,
                    include_global_facts=include_global_facts,
                    user_global_facts_resource_id=global_facts_rid,
                )
            ),
            chat_history=context,
            extra_context=(extra_context or []) + global_facts + topic_facts,
        )
        if ask_request_overrides:
            for key, value in ask_request_overrides.items():
                if hasattr(ask_request, key):
                    setattr(ask_request, key, value)
                else:
                    logger.warning(f"Unknown AskRequest field: {key}")

        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=kbid, content=ask_request)
        return _parse_ask_result(ask_response)

    # ── entries ─────────────────────────────────────────────────────────

    def _get_user_global_facts(
        self, ndb: NucliaDBClient, user_id: str
    ) -> tuple[str | None, list[str]]:
        resource_slug = _global_entries_slug(user_id)
        try:
            resource = _get_resource_basic(
                ndb, kbid=ndb.kbid, rid=None, slug=resource_slug
            )
            resource_id = resource.id
        except NotFoundError:
            return None, []
        facts_field_id = _facts_field_id(user_id, self.task_ident)
        augment_request = augment.AugmentRequest(
            resources=[
                augment.AugmentResources(
                    given=[resource_id],
                    fields=augment.AugmentResourceFields(
                        text=True,
                        filters=[
                            filters.Field(
                                type=FieldTypeName.CONVERSATION,
                                name=facts_field_id,
                            )
                        ],
                    ),
                )
            ],
        )
        augment_response: augment.AugmentResponse = ndb.ndb.augment(
            kbid=ndb.kbid, content=augment_request
        )
        if facts_field_id not in augment_response.fields:
            return None, []
        global_facts = []
        augmented_field = cast(
            augment.AugmentedConversationField, augment_response.fields[facts_field_id]
        )
        for message in augmented_field.messages or []:
            try:
                fact = FactContent.model_validate_json(message.text or "")
            except Exception as e:
                logger.warning(f"Failed to parse fact from conversation message: {e}")
                continue
            global_facts.append(fact.text)
        return resource_id, global_facts

    @overload
    def entries(
        self,
        *,
        topic: str,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Entry]:
        """Get all entries created by a user for a specific topic.

        Parameters
        ----------
        topic:
            Topic ID or slug to retrieve entries for.
        user_id:
            An identifier for the user whose entries to retrieve.
        recent_first:
            Whether to return the entries ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @overload
    def entries(
        self,
        *,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Entry]:
        """Get all global entries created by a user (not tied to any specific topic).

        Parameters
        ----------
        user_id:
            An identifier for the user whose global entries to retrieve.
        recent_first:
            Whether to return the entries ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @kb
    def entries(
        self,
        *,
        topic: str | None = None,
        user_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Entry]:
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _global_entries_slug(user_id)
        for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_entries_field_id(user_id),
            recent_first=recent_first,
        ):
            yield Entry.from_conversation_message(message)

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
        """Get all extracted facts from entries of a user for a specific topic (from most recent to oldest).

        Parameters
        ----------
        topic:
            topic ID or slug to retrieve entries for.
        user_id:
            An identifier for the user whose entries to retrieve.
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
            field_id=_facts_field_id(user_id, self.task_ident),
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
        **kwargs,
    ) -> list[graph.responses.GraphPath]:
        """Get the topic graph including all extracted entities and relations from the topic content and the entries of the specified user.

        Parameters
        ----------
        topic:
            topic ID or slug to retrieve graph for.
        user_id:
            An identifier for the user whose entries facts to include in the graph.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        graph_request = graph.requests.GraphSearchRequest(
            top_k=500,
            filter_expression=graph.requests.GraphFilterExpression(
                field=_build_field_filter_expression(
                    self.task_ident,
                    topic=topic,
                    user_id=user_id,
                    include_global_facts=False,
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
                    graph.requests.Generated(
                        by=graph.requests.Generator.DATA_AUGMENTATION,
                        da_task=GRAPH_EXTRACTION_TEMPLATE.format(
                            task_ident=self.task_ident
                        ),
                    ),
                ],
            ),
        )
        graph_response: graph.responses.GraphSearchResponse = ndb.ndb.graph_search(
            kbid=ndb.kbid,
            content=graph_request,
        )
        return graph_response.paths

    # ── forget ──────────────────────────────────────────────────────────────

    @kb
    def forget_entry(
        self,
        *,
        user_id: str,
        entry_id: str,
        topic: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete a specific entry from a topic or from the global entries topic created by the user.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _global_entries_slug(user_id)
        # Delete a specific entry for that user on that topic (or global)
        try:
            _delete_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_entries_field_id(user_id),
                message_id=entry_id,
            )
        except NotFoundError:
            pass
        else:
            for fact in self.facts(topic=topic, user_id=user_id):
                if fact.content.related_entry_ids == [entry_id]:
                    try:
                        _delete_conversation_message(
                            ndb=ndb,
                            kbid=ndb.kbid,
                            rid=ruuid,
                            slug=rslug,
                            field_id=_facts_field_id(user_id, self.task_ident),
                            message_id=fact.id,
                        )
                    except NotFoundError:
                        pass

    @kb
    def forget_entries(
        self,
        *,
        user_id: str,
        topic: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete all entries from a topic for the specified user or from the global entries topic created by the user.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _global_entries_slug(user_id)
        try:
            _delete_resource_field(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_type=FieldTypeName.CONVERSATION,
                field_id=_entries_field_id(user_id),
            )
        except NotFoundError:
            pass

    @kb
    def forget_fact(
        self,
        *,
        user_id: str,
        fact_id: str,
        topic: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete a specific fact from a topic for the specified user entries on a topic or from the global entries topic created by the user.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _global_entries_slug(user_id)
        try:
            _delete_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_facts_field_id(user_id, self.task_ident),
                message_id=fact_id,
            )
        except NotFoundError:
            pass

    @kb
    def forget_facts(
        self,
        *,
        user_id: str,
        topic: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete all facts from a topic for the specified user entries on a topic or from the global entries topic created by the user.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if topic is not None:
            ruuid, rslug = _uuid_or_slug(topic)
        else:
            ruuid = None
            rslug = _global_entries_slug(user_id)
        try:
            _delete_resource_field(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_type=FieldTypeName.CONVERSATION,
                field_id=_facts_field_id(user_id, self.task_ident),
            )
        except NotFoundError:
            pass


# ─── Async Memory (TODO) ─────────────────────────────────────────────────────────────


# ─── Utils ─────────────────────────────────────────────────────────────


def _build_field_filter_expression(
    task_ident: str,
    topic: str,
    user_id: str | None,
    include_content: bool = True,
    include_facts: bool = True,
    include_entries: bool = False,
    include_global_facts: bool = False,
    user_global_facts_resource_id: str | None = None,
) -> filters.FieldFilterExpression:
    """
    Build a filter expression to scope recall or retrieve to a specific topic and include user entries and facts while
    excluding other users' entries and facts.

    Parameters
    ----------
    topic:
        topic ID or slug to scope the retrieval to.
    user_id:
        An identifier for the user whose entries and facts to include in the retrieval results.
    """
    ruuid, rslug = _uuid_or_slug(topic)

    # First off, make sure any retrieval is scoped to the specified topic
    # Include the global entries resource if the flag is set, to allow retrieval of global facts.
    resource_filter: filters.FieldFilterExpression = filters.Or(
        operands=[
            filters.Resource(id=ruuid, slug=rslug),
            filters.Resource(id=user_global_facts_resource_id),
        ]
        if include_global_facts and user_global_facts_resource_id is not None
        else [filters.Resource(id=ruuid, slug=rslug)]
    )

    fields_filter_ops: list[filters.FieldFilterExpression] = []
    if include_content:
        # Any other resource field that is not memory entries or facts
        fields_filter_ops.append(
            filters.And(
                operands=[
                    filters.Not(
                        operand=filters.ResourceFieldPrefix(
                            resource_id=ruuid,
                            resource_slug=rslug,
                            field_type=FieldTypeName.CONVERSATION,
                            field_name_prefix=MEMORY_FIELD_PREFIX,
                        )
                    ),
                    filters.Not(
                        operand=filters.ResourceFieldPrefix(
                            resource_id=ruuid,
                            resource_slug=rslug,
                            field_type=FieldTypeName.CONVERSATION,
                            field_name_prefix=FACTS_FIELD_PREFIX,
                        )
                    ),
                ]
            )
        )
    if include_entries and user_id:
        fields_filter_ops.append(
            filters.Field(
                type=FieldTypeName.CONVERSATION,
                name=_entries_field_id(user_id),
            )
        )
    if include_facts and user_id:
        fields_filter_ops.append(
            filters.Field(
                type=FieldTypeName.CONVERSATION,
                name=_facts_field_id(user_id, task_ident),
            )
        )
    assert len(fields_filter_ops) > 0, (
        "At least one of content, entries, or facts must be included."
    )
    # Combine the resource filter with the fields filters (if any)
    if len(fields_filter_ops) == 1:
        return filters.And(operands=[resource_filter, fields_filter_ops[0]])
    else:
        return filters.And(
            operands=[resource_filter, filters.Or(operands=fields_filter_ops)]
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


def _parse_ask_result(
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


def _parse_recall_result(
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


def _entries_field_id(user_id: str) -> str:
    # __memory__bob123
    return f"{MEMORY_FIELD_PREFIX}{user_id}"


def _facts_field_id(user_id: str, ident: str) -> str:
    # da-facts-memory-c-__memory__-bob123
    return f"{FACTS_FIELD_PREFIX}{ident}-c-{MEMORY_FIELD_PREFIX}{user_id}"


def _global_entries_slug(user_id: str) -> str:
    """Return the predictable slug for the per-user global-entries resource."""
    return f"{GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX}-{user_id}"


def _ensure_global_entries_resource(ndb: NucliaDBClient, user_id: str) -> str:
    """
    Ensure the per-user global-entries resource exists, creating it if necessary.
    Returns the resource slug.
    """
    slug = _global_entries_slug(user_id)
    if not ndb.ndb.exists_resource_by_slug(kbid=ndb.kbid, slug=slug):
        ndb.ndb.create_resource(
            kbid=ndb.kbid,
            content={"title": f"Memory global entries - {user_id}", "slug": slug},
        )
    return slug


def _get_global_entries_resource_id(ndb: NucliaDBClient, user_id: str) -> str | None:
    """
    Get the resource ID of the per-user global-entries resource, creating the resource if it doesn't exist.
    """
    slug = _ensure_global_entries_resource(ndb, user_id)
    try:
        resource = ndb.ndb.get_resource_by_slug(
            kbid=ndb.kbid,
            slug=slug,
            query_params={"show": [ResourceProperties.BASIC.value]},
        )
        return resource.id
    except NotFoundError:
        return None


def validate_user_id(user_id: str) -> None:
    field_id_pattern = r"^[a-zA-Z0-9:_-]+$"
    if not re.match(field_id_pattern, user_id):
        raise ValueError(
            f"Invalid User ID '{user_id}'. User IDs can only contain letters, numbers, underscores, colons, and hyphens."
        )


def validate_entry_id(entry_id: str) -> None:
    """
    Conditions:
    - Up to 128 characters
    - Can only contain letters, numbers, underscores, colons, and hyphens
    - Cannot be "0"
    - Cannot contain "/"
    """
    if len(entry_id) > 128:
        raise ValueError(
            f"Invalid entry ID '{entry_id}'. Entry IDs must be at most 128 characters."
        )
    if entry_id == "0":
        raise ValueError('Entry ID cannot be "0"')
    if "/" in entry_id:
        raise ValueError('Entry ID cannot contain "/"')
    id_pattern = r"^[a-zA-Z0-9:_-]+$"
    if not re.match(id_pattern, entry_id):
        raise ValueError(
            f"Invalid entry ID '{entry_id}'. Entry IDs can only contain letters, numbers, underscores, colons, and hyphens."
        )
