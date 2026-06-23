from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator, cast, overload

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
    InputMessage,
    InputMessageContent,
    MessageFormat,
    MessageType,
)
from nucliadb_models.link import LinkField
from nucliadb_models.resource import Resource
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

from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.memory.exceptions import (
    EntryAlreadyExistsError,
    TopicAlreadyExistsError,
    TopicNotFoundError,
)
from nuclia.sdk.memory.models import (
    AskResult,
    Entry,
    EntryContent,
    EntryContextMessage,
    Fact,
    FactContent,
    RelevantContextBlock,
    Topic,
    TopicPage,
)
from nuclia.sdk.memory.utils import (
    _add_conversation_message,
    _build_field_filter_expression,
    _delete_conversation_message,
    _delete_resource_field,
    _ensure_global_entries_resource,
    _entries_field_id,
    _facts_field_id,
    _get_resource_basic,
    _get_topic_status,
    _global_entries_slug,
    _iter_conversation_messages,
    _parse_ask_result,
    _parse_recall_result,
    _slugify,
    _uuid_or_slug,
    validate_entry_id,
    validate_user_id,
)
from nuclia.sdk.task import NucliaTask
from nuclia.sdk.upload import NucliaUpload

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


GRAPH_EXTRACTION_TEMPLATE = "memory-graph-{task_ident}"

__all__ = [
    "NucliaMemory",
    "AsyncNucliaMemory",
]

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
    ) -> AskResult:
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
                    self.forget_fact(
                        user_id=user_id, fact_id=fact.id, topic=topic, **kwargs
                    )

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
        else:
            self.forget_facts(user_id=user_id, topic=topic, **kwargs)

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


# ─── Async Memory ─────────────────────────────────────────────────────────────


class AsyncNucliaMemory:
    task_ident = "memory"
