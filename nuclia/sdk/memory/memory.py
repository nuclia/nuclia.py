from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator, Iterator, cast, overload

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
from nucliadb_models.link import LinkField
from nucliadb_models.resource import Resource as NDBResource
from nucliadb_models.search import (
    CatalogQuery,
    ChatContextMessage,
    CustomPrompt,
    ResourceProperties,
)
from nucliadb_models.text import TextField, TextFormat
from nucliadb_sdk.v2.exceptions import ConflictError, NotFoundError, UnprocessableEntity

from nuclia.decorators import kb
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.kb import AsyncNucliaKB, NucliaKB
from nuclia.sdk.memory.exceptions import (
    EntryAlreadyExistsError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
)
from nuclia.sdk.memory.models import (
    AskResult,
    Entry,
    EntryContent,
    EntryContextMessage,
    Fact,
    FactContent,
    RelevantContextBlock,
    Resource,
    ResourcePage,
)
from nuclia.sdk.memory.utils import (
    _add_conversation_message,
    _build_ask_request,
    _build_entry_message,
    _build_graph_search_request,
    _build_list_resources_catalog_request,
    _build_recall_find_request,
    _delete_conversation_message,
    _delete_resource_field,
    _ensure_global_entries_resource,
    _entries_field_id,
    _facts_field_id,
    _get_global_sessions,
    _get_resource_basic,
    _get_resource_sessions,
    _get_resource_status,
    _global_entries_slug,
    _hydrate_with_facts_and_entries,
    _hydrate_with_facts_and_entries_async,
    _iter_conversation_messages,
    _parse_ask_result,
    _parse_catalog_response_to_resource_page,
    _parse_recall_result,
    _resolve_resource_location,
    _slugify,
    _uuid_or_slug,
    validate_entry_id,
    validate_session_id,
)
from nuclia.sdk.task import AsyncNucliaTask, NucliaTask
from nuclia.sdk.upload import AsyncNucliaUpload, NucliaUpload

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


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

    # ── resource management ────────────────────────────────────────────────────────────

    @kb
    def get_resource(
        self,
        *,
        resource: str,
        **kwargs,
    ) -> Resource:
        """Retrieve an resource by ID or slug."""
        ruuid, rslug = _uuid_or_slug(resource)
        try:
            ndbresource: NDBResource = self.kb.resource.get(
                rid=ruuid,
                slug=rslug,
                show=[ResourceProperties.BASIC.value, ResourceProperties.ERRORS.value],
            )
        except NotFoundError:
            raise ResourceNotFoundError(f"resource '{resource}' not found.")
        return Resource(
            id=ndbresource.id,
            slug=ndbresource.slug or "",
            title=ndbresource.title or "",
            summary=ndbresource.summary,
            status=_get_resource_status(ndbresource),
        )

    @kb
    def list_resources(
        self,
        *,
        query: str | CatalogQuery = "",
        page: int = 0,
        size: int = 20,
        **kwargs,
    ) -> ResourcePage:
        """List resources in this memory.

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
        global_sessions = _get_global_sessions(ndb)
        catalog_request = _build_list_resources_catalog_request(
            query, page, size, global_sessions
        )
        catalog_response = ndb.ndb.catalog(kbid=ndb.kbid, content=catalog_request)
        return _parse_catalog_response_to_resource_page(catalog_response)

    @kb
    def create_resource(
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
        Create a new resource.

        Returns the ID of the newly created resource.

        Parameters
        ----------
        title:
            The title of the resource.
        slug:
            Optional slug for the resource. If not provided, a slug will be generated from the title.
        summary:
            Optional summary for the resource.
        texts:
            Optional new text content for the resource. A dictionary mapping field IDs to text content.
        urls:
            Optional new URLs for the resource. A dictionary mapping field IDs to URLs.
        file_paths:
            Optional new file paths for the resource. A dictionary mapping field IDs to file paths.
        """
        try:
            return self._create_new_resource(
                title=title,
                slug=slug,
                summary=summary,
                texts=texts,
                urls=urls,
                file_paths=file_paths,
                **kwargs,
            )
        except ConflictError:
            raise ResourceAlreadyExistsError(
                f"resource with slug '{slug}' already exists."
            )

    @kb
    def update_resource(
        self,
        resource: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        """
        Update an existing resource.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to update.
        title:
            Optional new title for the resource.
        slug:
            Optional new slug for the resource.
        summary:
            Optional new summary for the resource.
        texts:
            Optional new text content for the resource. A dictionary mapping field IDs to text content.
        urls:
            Optional new URLs for the resource. A dictionary mapping field IDs to URLs.
        file_paths:
            Optional new file paths for the resource. A dictionary mapping field IDs to file paths.
        """
        try:
            self._update_resource(
                resource=resource,
                title=title,
                summary=summary,
                texts=texts,
                urls=urls,
                file_paths=file_paths,
                **kwargs,
            )
        except NotFoundError:
            raise ResourceNotFoundError(f"resource '{resource}' not found.")

    @kb
    def delete_resource(
        self,
        resource: str,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """
        Delete an existing resource.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to delete.
        """
        # Delete entire resource
        assert resource is not None, "Either session_id or resource must be provided."
        ruuid, rslug = _uuid_or_slug(resource)
        if not confirm:
            raise ValueError(
                "Deleting an entire resource is irreversible. To confirm, set confirm=True."
            )
        try:
            self.kb.resource.delete(rid=ruuid, slug=rslug)
        except NotFoundError:
            raise ResourceNotFoundError(f"resource '{resource}' not found.")

    def _update_resource(
        self,
        resource: str,
        title: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        base_args: dict[str, Any] = {}
        ruuid, rslug = _uuid_or_slug(resource)
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
                ndbresource = self.kb.resource.get(slug=rslug)
                ruuid = ndbresource.id
            for fid, path in file_paths.items():
                self.upload.file(
                    path=path,
                    rid=ruuid,
                    field_id=fid,
                    **base_args,
                )

    def _create_new_resource(
        self,
        title: str,
        slug: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
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
        resource: str,
        session_id: str,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str | None = None,
        **kwargs,
    ) -> str:
        """Add a memory entry to a specific resource.

        Parameters
        ----------
        text:
            The memory entry text.
        resource:
            Resource ID or slug to remember.
        session_id:
            An identifier for the session creating the memory entry.
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
        session_id: str,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str | None = None,
        **kwargs,
    ) -> str:
        """Add a global memory entry (not tied to any specific resource).

        Parameters
        ----------
        text:
            The memory entry text.
        session_id:
            An identifier for the session creating the memory entry. Each session gets their own dedicated resource for global memory entries.
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
        session_id: str,
        resource: str | None = None,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str | None = None,
        **kwargs,
    ) -> str:
        entry_id = entry_id or str(uuid.uuid4())
        validate_entry_id(entry_id)
        validate_session_id(session_id)
        ndb: NucliaDBClient = kwargs["ndb"]
        if resource is not None:
            ruuid, rslug = _uuid_or_slug(resource)
        else:
            ruuid = None
            rslug = _ensure_global_entries_resource(ndb, session_id)
        entry_content = EntryContent(
            text=text,
            reasoning=reasoning,
            context=context,
            metadata=metadata,
        )
        message = _build_entry_message(entry_id, entry_content)
        try:
            _add_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_entries_field_id(session_id),
                message=message,
            )
        except UnprocessableEntity as e:
            if "Message identifiers must be unique field" in e.message:
                raise EntryAlreadyExistsError(
                    f"Entry with ID '{entry_id}' already exists."
                )
        return entry_id

    # ── list sessions ──────────────────────────────────────────────────────────

    @overload
    def list_sessions(
        self,
        *,
        resource: str,
        **kwargs,
    ) -> list[str]:
        """Return the list of session IDs that have entries in the given resource.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to inspect.
        """
        ...

    @overload
    def list_sessions(
        self,
        **kwargs,
    ) -> list[str]:
        """Return the list of all session IDs that have global entries (not tied to any specific resource).

        Global entries live in per-session resources whose slugs begin with
        ``memory-global-entries-``. This overload lists all sessions that have
        created at least one global entry.
        """
        ...

    @kb
    def list_sessions(
        self,
        *,
        resource: str | None = None,
        **kwargs,
    ) -> list[str]:
        """Return the list of session IDs that have entries in the given resource, or all sessions with global entries when no resource is given.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to inspect. When omitted, returns all
            sessions with global (resource-less) entries.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if resource is not None:
            ruuid, rslug = _uuid_or_slug(resource)
            try:
                return _get_resource_sessions(ndb, ndb.kbid, ruuid, rslug)
            except NotFoundError:
                raise ResourceNotFoundError(f"resource '{resource}' not found.")
        else:
            return _get_global_sessions(ndb)

    # ── recall ─────────────────────────────────────────────────────────────

    @kb
    def recall(
        self,
        question: str,
        *,
        resource: str,
        session_id: str,
        top_k: int = 20,
        find_request_overrides: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[RelevantContextBlock]:
        """
        Retrieve relevant context blocks from the memory for a given question, scoped to a specific resource and session.

        Parameters
        ----------
        question:
            Natural-language question to retrieve context for.
        resource:
            Scope the retrieval to a single resource (ID or slug).
        session_id:
            An identifier for the session asking the question. Used to personalize retrieval results by including that session's entries and facts.
        top_k:
            Maximum number of relevant context blocks to retrieve.
        find_request_overrides:
            Optional dictionary of field overrides applied to the internal ``FindRequest`` before sending it.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        find_request = _build_recall_find_request(
            self.task_ident,
            question,
            resource,
            session_id,
            top_k,
            find_request_overrides,
        )
        find_response = ndb.ndb.find(kbid=ndb.kbid, content=find_request)
        recall_results = _parse_recall_result(find_response)
        _hydrate_with_facts_and_entries(ndb, ndb.kbid, recall_results)
        return recall_results

    # ── ask ───────────────────────────────────────────────────────────────

    @kb
    def ask(
        self,
        query: str,
        *,
        resource: str,
        session_id: str | None = None,
        context: list[ChatContextMessage] | None = None,
        include_global_facts: bool = False,
        extra_context: list[str] | None = None,
        custom_prompt: CustomPrompt | None = None,
        ask_request_overrides: dict[str, Any] | None = None,
        **kwargs,
    ) -> AskResult:
        """Ask a question and get a generative answer grounded in stored resources.

        Parameters
        ----------
        query:
            Natural-language question.
        resource:
            Scope the answer to a single resource (ID or slug).
        session_id:
            An identifier for the session asking the question. Used for personalization of the answer by including that session's entries and facts as context.
        context:
            Optional list of past messages to include as additional context for the recall. Messages should be ordered from oldest to most recent.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid

        global_facts: list[str] = []
        global_facts_rid = None
        resource_facts: list[str] = []
        if session_id:
            if include_global_facts:
                global_facts_rid, global_facts = self._get_session_global_facts(
                    ndb, session_id
                )
            resource_facts = [
                fact.content.text
                for fact in self.facts(resource=resource, session_id=session_id)
            ]

        ask_request = _build_ask_request(
            self.task_ident,
            query,
            resource,
            session_id,
            include_global_facts,
            global_facts_rid,
            extra_context,
            global_facts,
            resource_facts,
            context,
            custom_prompt,
            ask_request_overrides,
        )
        ask_response = ndb.ndb.ask(kbid=kbid, content=ask_request)
        result = _parse_ask_result(ask_response)
        # Hydrate citations with facts and entries
        if result.citations:
            _hydrate_with_facts_and_entries(
                ndb, ndb.kbid, list(result.citations.values())
            )
        return result

    # ── entries ─────────────────────────────────────────────────────────

    def _get_session_global_facts(
        self, ndb: NucliaDBClient, session_id: str
    ) -> tuple[str | None, list[str]]:
        resource_slug = _global_entries_slug(session_id)
        try:
            resource = _get_resource_basic(
                ndb, kbid=ndb.kbid, rid=None, slug=resource_slug
            )
            resource_id = resource.id
        except NotFoundError:
            return None, []
        facts_field_id = _facts_field_id(session_id, self.task_ident)
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
        session_id: str,
        resource: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Entry]:
        """Get all entries created by a session for a specific resource.

        Parameters
        ----------
        session_id:
            An identifier for the session whose entries to retrieve.
        resource:
            Resource ID or slug to retrieve entries for.
        recent_first:
            Whether to return the entries ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @overload
    def entries(
        self,
        *,
        session_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Entry]:
        """Get all global entries created by a session (not tied to any specific resource).

        Parameters
        ----------
        session_id:
            An identifier for the session whose global entries to retrieve.
        recent_first:
            Whether to return the entries ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @kb
    def entries(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Entry]:
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_entries_field_id(session_id),
            recent_first=recent_first,
        ):
            yield Entry.from_conversation_message(message)

    # ── facts ───────────────────────────────────────────────────────────────

    @overload
    def facts(
        self,
        *,
        session_id: str,
        resource: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Fact]:
        """Get all extracted facts from entries of a session for a specific resource (from most recent to oldest).

        Parameters
        ----------
        session_id:
            An identifier for the session whose entries to retrieve.
        resource:
            resource ID or slug to retrieve entries for.
        recent_first:
            Whether to return the facts ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @overload
    def facts(
        self,
        *,
        session_id: str,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Fact]:
        """Get all extracted facts from global entries of a session (not tied to any specific resource).

        Parameters
        ----------
        session_id:
            An identifier for the session whose global entries to retrieve.
        recent_first:
            Whether to return the facts ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ...

    @kb
    def facts(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        recent_first: bool = True,
        **kwargs,
    ) -> Iterator[Fact]:
        """Get all extracted facts from entries of a session for a specific resource (from most recent to oldest).

        Parameters
        ----------
        session_id:
            An identifier for the session whose entries to retrieve.
        resource:
            resource ID or slug to retrieve entries for.
        recent_first:
            Whether to return the facts ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_facts_field_id(session_id, self.task_ident),
            recent_first=recent_first,
        ):
            yield Fact.from_conversation_message(message)

    # ── graph ───────────────────────────────────────────────────────────────

    @kb
    def graph(
        self,
        *,
        resource: str,
        session_id: str,
        **kwargs,
    ) -> list[graph.responses.GraphPath]:
        """Get the resource graph including all extracted entities and relations from the resource content and the entries of the specified session.

        Parameters
        ----------
        resource:
            resource ID or slug to retrieve graph for.
        session_id:
            An identifier for the session whose entries facts to include in the graph.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        graph_request = _build_graph_search_request(
            self.task_ident, resource, session_id
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
        session_id: str,
        entry_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete a specific entry from a resource or from the global entries resource created by the session.

        Any fact derived solely from this entry is also deleted.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        # Delete a specific entry for that session on that resource (or global)
        try:
            _delete_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_entries_field_id(session_id),
                message_id=entry_id,
            )
        except NotFoundError:
            pass
        else:
            for fact in self.facts(resource=resource, session_id=session_id):
                if fact.content.related_entry_ids == [entry_id]:
                    self.forget_fact(
                        session_id=session_id,
                        fact_id=fact.id,
                        resource=resource,
                        **kwargs,
                    )

    @kb
    def forget_entries(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete all entries from a resource for the specified session or from the global entries resource created by the session.

        This operation also deletes the corresponding facts for that session and scope.
        """
        if resource is None:
            # Delete all entries and facts for that session
            try:
                self.kb.resource.delete(slug=_global_entries_slug(session_id))
            except NotFoundError:
                pass
            return

        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        try:
            _delete_resource_field(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_type=FieldTypeName.CONVERSATION,
                field_id=_entries_field_id(session_id),
            )
        except NotFoundError:
            pass
        else:
            self.forget_facts(session_id=session_id, resource=resource, **kwargs)

    @kb
    def forget_fact(
        self,
        *,
        session_id: str,
        fact_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete a specific fact from a resource for the specified session entries on a resource or from the global entries resource created by the session.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        try:
            _delete_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_facts_field_id(session_id, self.task_ident),
                message_id=fact_id,
            )
        except NotFoundError:
            pass

    @kb
    def forget_facts(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete all facts from a resource for the specified session entries on a resource or from the global entries resource created by the session.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if resource is None:
            # Delete all global facts for that session
            try:
                _delete_resource_field(
                    ndb=ndb,
                    kbid=ndb.kbid,
                    rid=None,
                    slug=_global_entries_slug(session_id),
                    field_type=FieldTypeName.CONVERSATION,
                    field_id=_facts_field_id(session_id, self.task_ident),
                )
            except NotFoundError:
                pass
            return

        ruuid, rslug = _resolve_resource_location(resource, session_id)
        try:
            _delete_resource_field(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_type=FieldTypeName.CONVERSATION,
                field_id=_facts_field_id(session_id, self.task_ident),
            )
        except NotFoundError:
            pass


# ─── Async Memory ─────────────────────────────────────────────────────────────


class AsyncNucliaMemory:
    task_ident = "memory"

    def __init__(self):
        self.kb = AsyncNucliaKB()
        self.upload = AsyncNucliaUpload()
        self.tasks = AsyncNucliaTask()

    # ── initialize ───────────────────────────────────────────────────────

    @kb
    async def initialize(
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
        kb_tasks = await self.tasks.list()
        existing_task = next(
            (task for task in kb_tasks.configs if task.task.name == TaskName.MEMORY),
            None,
        )
        if existing_task is None:
            # Configure the memory task for the first time
            await self.tasks.start(
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
                    await self.tasks.update(
                        task_id=existing_task.id,
                        task_name=TaskName.MEMORY,
                        parameters=new_params,
                    )

    # ── resource management ────────────────────────────────────────────────────────────

    @kb
    async def get_resource(
        self,
        *,
        resource: str,
        **kwargs,
    ) -> Resource:
        """Retrieve an resource by ID or slug."""
        ruuid, rslug = _uuid_or_slug(resource)
        try:
            ndbresource: NDBResource = await self.kb.resource.get(
                rid=ruuid,
                slug=rslug,
                show=[ResourceProperties.BASIC.value, ResourceProperties.ERRORS.value],
            )
        except NotFoundError:
            raise ResourceNotFoundError(f"resource '{resource}' not found.")
        return Resource(
            id=ndbresource.id,
            slug=ndbresource.slug or "",
            title=ndbresource.title or "",
            summary=ndbresource.summary,
            status=_get_resource_status(ndbresource),
        )

    @kb
    async def list_resources(
        self,
        *,
        query: str = "",
        page: int = 0,
        size: int = 20,
        **kwargs,
    ) -> ResourcePage:
        """List resources in this memory.

        Parameters
        ----------
        query:
            Filter by title (uses ``/catalog`` endpoint).
        page:
            Zero-based page index.
        size:
            Page size.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        global_sessions = await _get_global_sessions(ndb)
        catalog_request = _build_list_resources_catalog_request(
            query, page, size, global_sessions
        )
        catalog_response = await ndb.ndb.catalog(kbid=ndb.kbid, content=catalog_request)
        return _parse_catalog_response_to_resource_page(catalog_response)

    @kb
    async def create_resource(
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
        Create a new resource.

        Returns the ID of the newly created resource.

        Parameters
        ----------
        title:
            The title of the resource.
        slug:
            Optional slug for the resource. If not provided, a slug will be generated from the title.
        summary:
            Optional summary for the resource.
        texts:
            Optional new text content for the resource. A dictionary mapping field IDs to text content.
        urls:
            Optional new URLs for the resource. A dictionary mapping field IDs to URLs.
        file_paths:
            Optional new file paths for the resource. A dictionary mapping field IDs to file paths.
        """
        try:
            return await self._create_new_resource(
                title=title,
                slug=slug,
                summary=summary,
                texts=texts,
                urls=urls,
                file_paths=file_paths,
                **kwargs,
            )
        except ConflictError:
            raise ResourceAlreadyExistsError(
                f"resource with slug '{slug}' already exists."
            )

    @kb
    async def update_resource(
        self,
        resource: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        """
        Update an existing resource.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to update.
        title:
            Optional new title for the resource.
        slug:
            Optional new slug for the resource.
        summary:
            Optional new summary for the resource.
        texts:
            Optional new text content for the resource. A dictionary mapping field IDs to text content.
        urls:
            Optional new URLs for the resource. A dictionary mapping field IDs to URLs.
        file_paths:
            Optional new file paths for the resource. A dictionary mapping field IDs to file paths.
        """
        try:
            await self._update_resource(
                resource=resource,
                title=title,
                summary=summary,
                texts=texts,
                urls=urls,
                file_paths=file_paths,
                **kwargs,
            )
        except NotFoundError:
            raise ResourceNotFoundError(f"resource '{resource}' not found.")

    @kb
    async def delete_resource(
        self,
        resource: str,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """
        Delete an existing resource.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to delete.
        """
        assert resource is not None, "Either session_id or resource must be provided."
        ruuid, rslug = _uuid_or_slug(resource)
        if not confirm:
            raise ValueError(
                "Deleting an entire resource is irreversible. To confirm, set confirm=True."
            )
        try:
            await self.kb.resource.delete(rid=ruuid, slug=rslug)
        except NotFoundError:
            raise ResourceNotFoundError(f"resource '{resource}' not found.")

    async def _update_resource(
        self,
        resource: str,
        title: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        base_args: dict[str, Any] = {}
        ruuid, rslug = _uuid_or_slug(resource)
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
            await self.kb.resource.update(**update_resource_args)
        if file_paths:
            if ruuid is None:
                ndbresource = await self.kb.resource.get(slug=rslug)
                ruuid = ndbresource.id
            for fid, path in file_paths.items():
                await self.upload.file(
                    path=path,
                    rid=ruuid,
                    field_id=fid,
                    **base_args,
                )

    async def _create_new_resource(
        self,
        title: str,
        slug: str | None = None,
        summary: str | None = None,
        texts: dict[str, str] | None = None,
        urls: dict[str, str] | None = None,
        file_paths: dict[str, str] | None = None,
        **kwargs,
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
        resource_id = await self.kb.resource.create(**create_args)
        if file_paths is not None:
            for fid, path in file_paths.items():
                await self.upload.file(
                    path=path,
                    rid=resource_id,
                    field=fid,
                )
        return resource_id

    # ── remember ─────────────────────────────────────────────────────────────

    @kb
    async def remember(
        self,
        text: str,
        *,
        session_id: str,
        resource: str | None = None,
        context: list[EntryContextMessage] | None = None,
        reasoning: str | None = None,
        metadata: dict | None = None,
        entry_id: str | None = None,
        **kwargs,
    ) -> str:
        entry_id = entry_id or str(uuid.uuid4())
        validate_entry_id(entry_id)
        validate_session_id(session_id)
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if resource is not None:
            ruuid, rslug = _uuid_or_slug(resource)
        else:
            ruuid = None
            rslug = await _ensure_global_entries_resource(ndb, session_id)
        entry_content = EntryContent(
            text=text,
            reasoning=reasoning,
            context=context,
            metadata=metadata,
        )
        message = _build_entry_message(entry_id, entry_content)
        try:
            await _add_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_entries_field_id(session_id),
                message=message,
            )
        except UnprocessableEntity as e:
            if "Message identifiers must be unique field" in e.message:
                raise EntryAlreadyExistsError(
                    f"Entry with ID '{entry_id}' already exists."
                )
        return entry_id

    # ── list sessions ──────────────────────────────────────────────────────────

    @overload
    async def list_sessions(
        self,
        *,
        resource: str,
        **kwargs,
    ) -> list[str]:
        """Return the list of session IDs that have entries in the given resource.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to inspect.
        """
        ...

    @overload
    async def list_sessions(
        self,
        **kwargs,
    ) -> list[str]:
        """Return the list of all session IDs that have global entries (not tied to any specific resource).

        Global entries live in per-session resources whose slugs begin with
        ``memory-global-entries-``. This overload lists all sessions that have
        created at least one global entry.
        """
        ...

    @kb
    async def list_sessions(
        self,
        *,
        resource: str | None = None,
        **kwargs,
    ) -> list[str]:
        """Return the list of session IDs that have entries in the given resource, or all sessions with global entries when no resource is given.

        Parameters
        ----------
        resource:
            The ID or slug of the resource to inspect. When omitted, returns all
            sessions with global (resource-less) entries.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if resource is not None:
            ruuid, rslug = _uuid_or_slug(resource)
            try:
                return await _get_resource_sessions(ndb, ndb.kbid, ruuid, rslug)
            except NotFoundError:
                raise ResourceNotFoundError(f"resource '{resource}' not found.")
        else:
            return await _get_global_sessions(ndb)

    # ── recall ─────────────────────────────────────────────────────────────

    @kb
    async def recall(
        self,
        question: str,
        *,
        resource: str,
        session_id: str,
        top_k: int = 20,
        find_request_overrides: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[RelevantContextBlock]:
        """
        Retrieve relevant context blocks from the memory for a given question, scoped to a specific resource and session.

        Parameters
        ----------
        question:
            Natural-language question to retrieve context for.
        resource:
            Scope the retrieval to a single resource (ID or slug).
        session_id:
            An identifier for the session asking the question. Used to personalize retrieval results by including that session's entries and facts.
        top_k:
            Maximum number of relevant context blocks to retrieve.
        find_request_overrides:
            Optional dictionary of field overrides applied to the internal ``FindRequest`` before sending it.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        find_request = _build_recall_find_request(
            self.task_ident,
            question,
            resource,
            session_id,
            top_k,
            find_request_overrides,
        )
        find_response = await ndb.ndb.find(kbid=ndb.kbid, content=find_request)
        recall_results = _parse_recall_result(find_response)
        await _hydrate_with_facts_and_entries_async(ndb, ndb.kbid, recall_results)
        return recall_results

    # ── ask ───────────────────────────────────────────────────────────────

    @kb
    async def ask(
        self,
        query: str,
        *,
        resource: str,
        session_id: str | None = None,
        context: list[ChatContextMessage] | None = None,
        include_global_facts: bool = False,
        extra_context: list[str] | None = None,
        custom_prompt: CustomPrompt | None = None,
        ask_request_overrides: dict[str, Any] | None = None,
        **kwargs,
    ) -> AskResult:
        """Ask a question and get a generative answer grounded in stored resources.

        Parameters
        ----------
        query:
            Natural-language question.
        resource:
            Scope the answer to a single resource (ID or slug).
        session_id:
            An identifier for the session asking the question. Used for personalization of the answer by including that session's entries and facts as context.
        context:
            Optional list of past messages to include as additional context for the recall. Messages should be ordered from oldest to most recent.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid

        global_facts: list[str] = []
        global_facts_rid = None
        resource_facts: list[str] = []
        if session_id:
            if include_global_facts:
                global_facts_rid, global_facts = await self._get_session_global_facts(
                    ndb, session_id
                )
            resource_facts = [
                fact.content.text
                async for fact in self.facts(
                    resource=resource, session_id=session_id, **kwargs
                )
            ]

        ask_request = _build_ask_request(
            self.task_ident,
            query,
            resource,
            session_id,
            include_global_facts,
            global_facts_rid,
            extra_context,
            global_facts,
            resource_facts,
            context,
            custom_prompt,
            ask_request_overrides,
        )
        ask_response = await ndb.ndb.ask(kbid=kbid, content=ask_request)
        result = _parse_ask_result(ask_response)
        # Hydrate citations with facts and entries
        if result.citations:
            await _hydrate_with_facts_and_entries_async(
                ndb, ndb.kbid, list(result.citations.values())
            )
        return result

    # ── entries ─────────────────────────────────────────────────────────

    async def _get_session_global_facts(
        self, ndb: AsyncNucliaDBClient, session_id: str
    ) -> tuple[str | None, list[str]]:
        resource_slug = _global_entries_slug(session_id)
        try:
            resource = await _get_resource_basic(
                ndb, kbid=ndb.kbid, rid=None, slug=resource_slug
            )
            resource_id = resource.id
        except NotFoundError:
            return None, []
        facts_field_id = _facts_field_id(session_id, self.task_ident)
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
        augment_response: augment.AugmentResponse = await ndb.ndb.augment(
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

    @kb
    async def entries(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        recent_first: bool = True,
        **kwargs,
    ) -> AsyncIterator[Entry]:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        async for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_entries_field_id(session_id),
            recent_first=recent_first,
        ):
            yield Entry.from_conversation_message(message)

    # ── facts ───────────────────────────────────────────────────────────────

    @kb
    async def facts(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        recent_first: bool = True,
        **kwargs,
    ) -> AsyncIterator[Fact]:
        """Get all extracted facts from entries of a session for a specific resource (from most recent to oldest).

        Parameters
        ----------
        session_id:
            An identifier for the session whose entries to retrieve.
        resource:
            resource ID or slug to retrieve entries for.
        recent_first:
            Whether to return the facts ordered from most recent to oldest (True) or from oldest to most recent (False). Defaults to True.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        async for message in _iter_conversation_messages(
            ndb,
            kbid=ndb.kbid,
            rid=ruuid,
            slug=rslug,
            field_id=_facts_field_id(session_id, self.task_ident),
            recent_first=recent_first,
        ):
            yield Fact.from_conversation_message(message)

    # ── graph ───────────────────────────────────────────────────────────────

    @kb
    async def graph(
        self,
        *,
        resource: str,
        session_id: str,
        **kwargs,
    ) -> list[graph.responses.GraphPath]:
        """Get the resource graph including all extracted entities and relations from the resource content and the entries of the specified session.

        Parameters
        ----------
        resource:
            resource ID or slug to retrieve graph for.
        session_id:
            An identifier for the session whose entries facts to include in the graph.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        graph_request = _build_graph_search_request(
            self.task_ident, resource, session_id
        )
        graph_response: graph.responses.GraphSearchResponse = (
            await ndb.ndb.graph_search(
                kbid=ndb.kbid,
                content=graph_request,
            )
        )
        return graph_response.paths

    # ── forget ──────────────────────────────────────────────────────────────

    @kb
    async def forget_entry(
        self,
        *,
        session_id: str,
        entry_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete a specific entry from a resource or from the global entries resource created by the session.

        Any fact derived solely from this entry is also deleted.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        # Delete a specific entry for that session on that resource (or global)
        try:
            await _delete_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_entries_field_id(session_id),
                message_id=entry_id,
            )
        except NotFoundError:
            pass
        else:
            async for fact in self.facts(
                resource=resource, session_id=session_id, **kwargs
            ):
                if fact.content.related_entry_ids == [entry_id]:
                    await self.forget_fact(
                        session_id=session_id,
                        fact_id=fact.id,
                        resource=resource,
                        **kwargs,
                    )

    @kb
    async def forget_entries(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete all entries from a resource for the specified session or from the global entries resource created by the session.

        This operation also deletes the corresponding facts for that session and scope.
        """
        if resource is None:
            # Delete all global entries and facts for that session
            try:
                await self.kb.resource.delete(slug=_global_entries_slug(session_id))
            except NotFoundError:
                pass
            return

        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        try:
            await _delete_resource_field(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_type=FieldTypeName.CONVERSATION,
                field_id=_entries_field_id(session_id),
            )
        except NotFoundError:
            pass
        else:
            await self.forget_facts(session_id=session_id, resource=resource, **kwargs)

    @kb
    async def forget_fact(
        self,
        *,
        session_id: str,
        fact_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete a specific fact from a resource for the specified session entries on a resource or from the global entries resource created by the session.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        ruuid, rslug = _resolve_resource_location(resource, session_id)
        try:
            await _delete_conversation_message(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_id=_facts_field_id(session_id, self.task_ident),
                message_id=fact_id,
            )
        except NotFoundError:
            pass

    @kb
    async def forget_facts(
        self,
        *,
        session_id: str,
        resource: str | None = None,
        **kwargs,
    ) -> None:
        """
        Delete all facts from a resource for the specified session entries on a resource or from the global entries resource created by the session.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if resource is None:
            # Delete all global facts for that session
            try:
                await _delete_resource_field(
                    ndb=ndb,
                    kbid=ndb.kbid,
                    rid=None,
                    slug=_global_entries_slug(session_id),
                    field_type=FieldTypeName.CONVERSATION,
                    field_id=_facts_field_id(session_id, self.task_ident),
                )
            except NotFoundError:
                pass
            return

        ruuid, rslug = _resolve_resource_location(resource, session_id)
        try:
            await _delete_resource_field(
                ndb=ndb,
                kbid=ndb.kbid,
                rid=ruuid,
                slug=rslug,
                field_type=FieldTypeName.CONVERSATION,
                field_id=_facts_field_id(session_id, self.task_ident),
            )
        except NotFoundError:
            pass
