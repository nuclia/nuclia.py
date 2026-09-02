from __future__ import annotations

import inspect
import logging
import re
import string
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Awaitable, Iterator, Union, cast, overload

from nucliadb_models import (
    CreateResourcePayload,
    filters,
    graph,
)
from nucliadb_models.augment import (
    AugmentedConversationField,
    AugmentedConversationMessage,
    AugmentFields,
    AugmentRequest,
    AugmentResponse,
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
from nucliadb_models.resource import ConversationFieldData, ResourceField
from nucliadb_models.resource import Resource as NDBResource
from nucliadb_models.search import (
    AskRequest,
    CatalogQuery,
    CatalogQueryField,
    CatalogQueryMatch,
    CatalogRequest,
    CatalogResponse,
    ChatContextMessage,
    CitationsType,
    CustomPrompt,
    FindOptions,
    FindRequest,
    KnowledgeboxFindResults,
    PredictReranker,
    RerankerName,
    ResourceProperties,
    SyncAskResponse,
)
from nucliadb_sdk.v2.exceptions import NotFoundError
from pydantic import ValidationError

from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.memory.models import (
    AskResult,
    Entry,
    EntryContent,
    Fact,
    FactContent,
    RelevantContextBlock,
    Resource,
    ResourcePage,
)

logger = logging.getLogger(__name__)

MEMORY_FIELD_PREFIX = "__memory__"
FACTS_FIELD_PREFIX = "da-facts-"
GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX = "memory-global-entries"
GRAPH_EXTRACTION_TEMPLATE = "memory-graph-{task_ident}"


def _build_field_filter_expression(
    task_ident: str,
    resource: str,
    session_id: str | None,
    include_content: bool = True,
    include_facts: bool = True,
    include_entries: bool = False,
    include_global_facts: bool = False,
    session_global_facts_resource_id: str | None = None,
) -> filters.FieldFilterExpression:
    """
    Build a filter expression to scope recall or retrieve to a specific resource and include session entries and facts while
    excluding other sessions' entries and facts.

    Parameters
    ----------
    resource:
        resource ID or slug to scope the retrieval to.
    session_id:
        An identifier for the session whose entries and facts to include in the retrieval results.
    """
    ruuid, rslug = _uuid_or_slug(resource)

    # First off, make sure any retrieval is scoped to the specified resource
    # Include the global entries resource if the flag is set, to allow retrieval of global facts.
    resource_filter: filters.FieldFilterExpression = filters.Or(
        operands=[
            filters.Resource(id=ruuid, slug=rslug),
            filters.Resource(id=session_global_facts_resource_id),
        ]
        if include_global_facts and session_global_facts_resource_id is not None
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
    if include_entries and session_id:
        fields_filter_ops.append(
            filters.Field(
                type=FieldTypeName.CONVERSATION,
                name=_entries_field_id(session_id),
            )
        )
    if include_facts and session_id:
        fields_filter_ops.append(
            filters.Field(
                type=FieldTypeName.CONVERSATION,
                name=_facts_field_id(session_id, task_ident),
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


def _uuid_or_slug(
    resource_uuid_or_slug: str,
) -> Union[tuple[str, None], tuple[None, str]]:
    """Helper to determine if resource identifier is a UUID's hex or slug."""
    try:
        # If this succeeds, resource is a uuid
        return uuid.UUID(resource_uuid_or_slug).hex, None
    except ValueError:
        # Otherwise, treat it as a slug
        return None, resource_uuid_or_slug


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
) -> AskResult:
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
    return AskResult(answer=answer_text, citations=citations)


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


def _hydrate_context_blocks(
    context_blocks: list[RelevantContextBlock],
    augment_response: AugmentResponse,
) -> None:
    """
    Hydrate context blocks with facts and entries from augment response.
    Works with both recall results and ask result citations.
    """
    # Build a lookup map: message_id_prefix -> Message
    message_lookup: dict[str, AugmentedConversationMessage] = {}
    for field_id, field_augmentations in augment_response.fields.items():
        field_aug = cast(AugmentedConversationField, field_augmentations)
        for message in field_aug.messages or []:
            if message.format == MessageFormat.JSON and message.text is not None:
                # Store by the prefix that would appear in context_block.id
                key = f"{field_id}/{message.ident}"
                message_lookup[key] = message

    # Hydrate each context block with a single lookup
    for context_block in context_blocks:
        # Find matching message by checking which lookup key is a prefix
        for msg_key, message in message_lookup.items():
            if not context_block.id.startswith(msg_key) or not message.text:
                continue

            # Determine if this is a fact or entry based on the context_block.id
            if FACTS_FIELD_PREFIX in context_block.id:
                try:
                    context_block.fact = Fact(
                        id=message.ident,
                        timestamp=message.timestamp or datetime.now(timezone.utc),
                        content=FactContent.model_validate_json(message.text),
                    )
                    break
                except ValidationError as e:
                    logger.warning(
                        f"Failed to parse fact content for message {message.ident}: {e}"
                    )
            elif MEMORY_FIELD_PREFIX in context_block.id:
                try:
                    context_block.entry = Entry(
                        id=message.ident,
                        timestamp=message.timestamp or datetime.now(timezone.utc),
                        content=EntryContent.model_validate_json(message.text),
                    )
                    break
                except ValidationError as e:
                    logger.warning(
                        f"Failed to parse entry content for message {message.ident}: {e}"
                    )


def _hydrate_with_facts_and_entries(
    ndb: NucliaDBClient,
    kbid: str,
    context_blocks: list[RelevantContextBlock],
) -> None:
    """Hydrate context blocks (recall results or citations) with facts and entries."""
    to_augment = _get_message_ids_to_augment(context_blocks)
    if to_augment:
        augment_resp: AugmentResponse = ndb.ndb.augment(
            kbid=kbid,
            content=AugmentRequest(
                fields=[
                    AugmentFields(
                        given=to_augment,
                        conversation_message_content_text=True,
                    )
                ]
            ),
        )
        _hydrate_context_blocks(context_blocks, augment_resp)


def _get_message_ids_to_augment(
    context_blocks: list[RelevantContextBlock],
) -> list[str]:
    """Extract message IDs that need augmentation from context blocks (facts/entries only)."""

    def _get_message_split_id(pid: str) -> str:
        return "/".join(pid.split("/")[:4])

    return list(
        {
            _get_message_split_id(cb.id)
            for cb in context_blocks
            if FACTS_FIELD_PREFIX in cb.id or MEMORY_FIELD_PREFIX in cb.id
        }
    )


async def _hydrate_with_facts_and_entries_async(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    context_blocks: list[RelevantContextBlock],
) -> None:
    """Async version: hydrate context blocks (recall results or citations) with facts and entries."""
    to_augment = _get_message_ids_to_augment(context_blocks)
    if to_augment:
        augment_resp: AugmentResponse = await ndb.ndb.augment(
            kbid=kbid,
            content=AugmentRequest(
                fields=[
                    AugmentFields(
                        given=list(to_augment),
                        conversation_message_content_text=True,
                    )
                ]
            ),
        )
        _hydrate_context_blocks(context_blocks, augment_resp)


def _get_resource_status(resource: NDBResource) -> str:
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


@overload
def _delete_resource_field(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
) -> None: ...


@overload
def _delete_resource_field(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
) -> Awaitable[None]: ...


def _delete_resource_field(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
) -> None | Awaitable[None]:
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
        fn = ndb.ndb.delete_field_by_id
    else:
        assert slug is not None
        delete_field_args["slug"] = slug
        fn = ndb.ndb.delete_field_by_slug
    if inspect.iscoroutinefunction(fn):
        return fn(**delete_field_args)
    fn(**delete_field_args)
    return None


@overload
def _delete_conversation_message(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message_id: str,
) -> None: ...


@overload
def _delete_conversation_message(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message_id: str,
) -> Awaitable[None]: ...


def _delete_conversation_message(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message_id: str,
) -> None | Awaitable[None]:
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
        fn = ndb.ndb.delete_conversation_message
    else:
        assert slug is not None
        delete_conversation_message_args["slug"] = slug
        fn = ndb.ndb.delete_conversation_message_by_slug
    if inspect.iscoroutinefunction(fn):
        return fn(**delete_conversation_message_args)
    fn(**delete_conversation_message_args)
    return None


@overload
def _add_conversation_message(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message: InputMessage,
) -> None: ...


@overload
def _add_conversation_message(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message: InputMessage,
) -> Awaitable[None]: ...


def _add_conversation_message(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    message: InputMessage,
) -> None | Awaitable[None]:
    add_conversation_args = {
        "kbid": kbid,
        "field_id": field_id,
        "content": [message],
    }
    if rid:
        add_conversation_args["rid"] = rid
        fn = ndb.ndb.add_conversation_message
    else:
        assert slug is not None
        add_conversation_args["slug"] = slug
        fn = ndb.ndb.add_conversation_message_by_slug
    if inspect.iscoroutinefunction(fn):
        return fn(**add_conversation_args)
    fn(**add_conversation_args)
    return None


@overload
def _iter_conversation_messages(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    recent_first: bool = True,
) -> Iterator[Message]: ...


@overload
def _iter_conversation_messages(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    recent_first: bool = True,
) -> AsyncGenerator[Message, None]: ...


def _iter_conversation_messages(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    recent_first: bool = True,
) -> Iterator[Message] | AsyncGenerator[Message, None]:
    if isinstance(ndb, AsyncNucliaDBClient):
        return _iter_conversation_messages_async(
            ndb=ndb,
            kbid=kbid,
            rid=rid,
            slug=slug,
            field_id=field_id,
            recent_first=recent_first,
        )
    return _iter_conversation_messages_sync(
        ndb=ndb,
        kbid=kbid,
        rid=rid,
        slug=slug,
        field_id=field_id,
        recent_first=recent_first,
    )


def _iter_conversation_messages_sync(
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


async def _iter_conversation_messages_async(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    recent_first: bool = True,
) -> AsyncGenerator[Message, None]:
    try:
        field = await _get_resource_field(
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
            break
        page = await _get_page_of_conversation_messages(
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


@overload
def _get_page_of_conversation_messages(
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    ndb: NucliaDBClient,
    page: str,
) -> list[Message]: ...


@overload
def _get_page_of_conversation_messages(
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    ndb: AsyncNucliaDBClient,
    page: str,
) -> Awaitable[list[Message]]: ...


def _get_page_of_conversation_messages(
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    page: str,
) -> list[Message] | Awaitable[list[Message]]:
    kbid = ndb.kbid
    if isinstance(ndb, AsyncNucliaDBClient):
        return _get_page_of_conversation_messages_async(
            kbid=kbid, rid=rid, slug=slug, field_id=field_id, ndb=ndb, page=page
        )
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


async def _get_page_of_conversation_messages_async(
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_id: str,
    ndb: AsyncNucliaDBClient,
    page: str,
) -> list[Message]:
    kbid = ndb.kbid
    field: ResourceField = await _get_resource_field(
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


@overload
def _get_resource_basic(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> NDBResource: ...


@overload
def _get_resource_basic(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> Awaitable[NDBResource]: ...


def _get_resource_basic(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> NDBResource | Awaitable[NDBResource]:
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
        fn = ndb.ndb.get_resource_by_id
    else:
        assert slug is not None
        get_resource_args["slug"] = slug
        fn = ndb.ndb.get_resource_by_slug
    if inspect.iscoroutinefunction(fn):
        return fn(**get_resource_args)
    return fn(**get_resource_args)


@overload
def _get_resource_field(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
    page: str | None = None,
) -> ResourceField: ...


@overload
def _get_resource_field(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
    page: str | None = None,
) -> Awaitable[ResourceField]: ...


def _get_resource_field(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
    field_type: FieldTypeName,
    field_id: str,
    page: str | None = None,
) -> ResourceField | Awaitable[ResourceField]:
    get_field_args: dict[str, Any] = {
        "kbid": kbid,
        "field_type": field_type.value,
        "field_id": field_id,
    }
    if page is not None:
        get_field_args["query_params"] = {"page": page}
    if rid:
        get_field_args["rid"] = rid
        fn = ndb.ndb.get_resource_field
    else:
        assert slug is not None
        get_field_args["slug"] = slug
        fn = ndb.ndb.get_resource_field_by_slug
    if inspect.iscoroutinefunction(fn):
        return fn(**get_field_args)
    return fn(**get_field_args)


def _entries_field_id(session_id: str) -> str:
    # __memory__bob123
    return f"{MEMORY_FIELD_PREFIX}{session_id}"


def _facts_field_id(session_id: str, ident: str) -> str:
    # da-facts-memory-c-__memory__-bob123
    return f"{FACTS_FIELD_PREFIX}{ident}-c-{MEMORY_FIELD_PREFIX}{session_id}"


def _global_entries_slug(session_id: str) -> str:
    """Return the predictable slug for the per-session global-entries resource."""
    return f"{GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX}-{session_id}"


def _resolve_resource_location(
    resource: str | None,
    session_id: str,
) -> tuple[str | None, str | None]:
    """Return (ruuid, rslug) scoped to resource, or the global entries resource slug when resource is None."""
    if resource is not None:
        return _uuid_or_slug(resource)
    return None, _global_entries_slug(session_id)


@overload
def _ensure_global_entries_resource(ndb: NucliaDBClient, session_id: str) -> str: ...


@overload
def _ensure_global_entries_resource(
    ndb: AsyncNucliaDBClient, session_id: str
) -> Awaitable[str]: ...


def _ensure_global_entries_resource(
    ndb: NucliaDBClient | AsyncNucliaDBClient, session_id: str
) -> str | Awaitable[str]:
    """
    Ensure the per-session global-entries resource exists, creating it if necessary.
    Returns the resource slug.
    """
    if isinstance(ndb, AsyncNucliaDBClient):
        return _ensure_global_entries_resource_async(ndb, session_id)
    return _ensure_global_entries_resource_sync(ndb, session_id)


def _ensure_global_entries_resource_sync(ndb: NucliaDBClient, session_id: str) -> str:
    slug = _global_entries_slug(session_id)
    if not ndb.ndb.exists_resource_by_slug(kbid=ndb.kbid, slug=slug):
        ndb.ndb.create_resource(
            kbid=ndb.kbid,
            content=CreateResourcePayload(
                title=f"Memory global entries - {session_id}", slug=slug
            ),
        )
    return slug


async def _ensure_global_entries_resource_async(
    ndb: AsyncNucliaDBClient, session_id: str
) -> str:
    slug = _global_entries_slug(session_id)
    if not await ndb.ndb.exists_resource_by_slug(kbid=ndb.kbid, slug=slug):
        await ndb.ndb.create_resource(
            kbid=ndb.kbid,
            content=CreateResourcePayload(
                title=f"Memory global entries - {session_id}", slug=slug
            ),
        )
    return slug


def validate_session_id(session_id: str) -> None:
    field_id_pattern = r"^[a-zA-Z0-9:_-]+$"
    if not re.match(field_id_pattern, session_id):
        raise ValueError(
            f"Invalid Session ID '{session_id}'. Session IDs can only contain letters, numbers, underscores, colons, and hyphens."
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


# ─── Pure request / response builders ────────────────────────────────────────


# ─── Session listing helpers ─────────────────────────────────────────────────────


@overload
def _get_resource_sessions(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> list[str]: ...


@overload
def _get_resource_sessions(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> Awaitable[list[str]]: ...


def _get_resource_sessions(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> list[str] | Awaitable[list[str]]:
    """Return the list of session IDs that have entries in the given resource.

    Inspects the resource's conversation fields for entries stored under the
    ``__memory__{session_id}`` naming convention.
    """
    if isinstance(ndb, AsyncNucliaDBClient):
        return _get_resource_sessions_async(ndb=ndb, kbid=kbid, rid=rid, slug=slug)
    return _get_resource_sessions_sync(ndb=ndb, kbid=kbid, rid=rid, slug=slug)


def _get_resource_sessions_sync(
    ndb: NucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> list[str]:
    get_resource_args: dict[str, Any] = {
        "kbid": kbid,
        "query_params": {"show": [ResourceProperties.ERRORS.value]},
    }
    if rid:
        get_resource_args["rid"] = rid
        resource: NDBResource = ndb.ndb.get_resource_by_id(**get_resource_args)
    else:
        assert slug is not None
        get_resource_args["slug"] = slug
        resource = ndb.ndb.get_resource_by_slug(**get_resource_args)
    conversations: dict[str, ConversationFieldData] = (
        (resource.data.conversations or {}) if resource.data else {}
    )
    return [
        field_id[len(MEMORY_FIELD_PREFIX) :]
        for field_id in conversations
        if field_id.startswith(MEMORY_FIELD_PREFIX)
    ]


async def _get_resource_sessions_async(
    ndb: AsyncNucliaDBClient,
    kbid: str,
    rid: str | None,
    slug: str | None,
) -> list[str]:
    get_resource_args: dict[str, Any] = {
        "kbid": kbid,
        "query_params": {"show": [ResourceProperties.ERRORS.value]},
    }
    if rid:
        get_resource_args["rid"] = rid
        resource: NDBResource = await ndb.ndb.get_resource_by_id(**get_resource_args)
    else:
        assert slug is not None
        get_resource_args["slug"] = slug
        resource = await ndb.ndb.get_resource_by_slug(**get_resource_args)
    conversations: dict[str, ConversationFieldData] = (
        (resource.data.conversations or {}) if resource.data else {}
    )
    return [
        field_id[len(MEMORY_FIELD_PREFIX) :]
        for field_id in conversations
        if field_id.startswith(MEMORY_FIELD_PREFIX)
    ]


@overload
def _get_global_sessions(
    ndb: NucliaDBClient,
) -> list[str]: ...


@overload
def _get_global_sessions(
    ndb: AsyncNucliaDBClient,
) -> Awaitable[list[str]]: ...


def _get_global_sessions(
    ndb: NucliaDBClient | AsyncNucliaDBClient,
) -> list[str] | Awaitable[list[str]]:
    """Return the list of all session IDs that have at least one global (resource-less) entry.

    Global entries live in per-session resources whose slugs start with
    ``GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX-``. This function paginates the
    catalog automatically so it works correctly with any number of sessions.
    """
    if isinstance(ndb, AsyncNucliaDBClient):
        return _get_global_sessions_async(ndb=ndb)
    return _get_global_sessions_sync(ndb=ndb)


def _get_global_sessions_sync(ndb: NucliaDBClient) -> list[str]:
    prefix = GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX + "-"
    page, session_ids = 0, []
    while True:
        catalog_response = ndb.ndb.catalog(
            kbid=ndb.kbid,
            content=CatalogRequest(
                query=CatalogQuery(
                    field=CatalogQueryField.Slug,
                    match=CatalogQueryMatch.StartsWith,
                    query=prefix,
                ),
                page_number=page,
                page_size=200,
                show=[ResourceProperties.BASIC],
            ),
        )
        for resource in catalog_response.resources.values():
            slug = resource.slug or ""
            if slug.startswith(prefix):
                session_ids.append(slug[len(prefix) :])
        has_more = (
            catalog_response.fulltext.next_page if catalog_response.fulltext else False
        )
        if not has_more:
            break
        page += 1
    return session_ids


async def _get_global_sessions_async(ndb: AsyncNucliaDBClient) -> list[str]:
    prefix = GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX + "-"
    page, session_ids = 0, []
    while True:
        catalog_response = await ndb.ndb.catalog(
            kbid=ndb.kbid,
            content=CatalogRequest(
                query=CatalogQuery(
                    field=CatalogQueryField.Slug,
                    match=CatalogQueryMatch.StartsWith,
                    query=prefix,
                ),
                page_number=page,
                page_size=200,
                show=[ResourceProperties.BASIC],
            ),
        )
        for resource in catalog_response.resources.values():
            slug = resource.slug or ""
            if slug.startswith(prefix):
                session_ids.append(slug[len(prefix) :])
        has_more = (
            catalog_response.fulltext.next_page if catalog_response.fulltext else False
        )
        if not has_more:
            break
        page += 1
    return session_ids


# ─── Pure request / response builders ────────────────────────────────────────


def _build_list_resources_catalog_request(
    query: str | CatalogQuery,
    page: int,
    size: int,
    global_sessions: list[str],
) -> CatalogRequest:
    filter_expression = None
    if len(global_sessions) > 0:
        # Exclude resources that are for global entries
        filter_expression = filters.CatalogFilterExpression(
            resource=filters.Not(
                operand=filters.Or(
                    operands=[
                        filters.Resource(slug=_global_entries_slug(session_id))
                        for session_id in global_sessions
                    ]
                )
            )
        )
    return CatalogRequest(
        query=query,
        page_number=page,
        page_size=size,
        show=[
            ResourceProperties.BASIC,
        ],
        filter_expression=filter_expression,
    )


def _build_entry_message(entry_id: str, entry_content: EntryContent) -> InputMessage:
    """Build the InputMessage that wraps a memory entry for storage in a conversation field."""
    return InputMessage(
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


def _build_recall_find_request(
    task_ident: str,
    question: str,
    resource: str,
    session_id: str,
    top_k: int,
) -> FindRequest:
    """Build and return the FindRequest, applying any caller-supplied field overrides."""
    find_request = FindRequest(
        query=question,
        features=[FindOptions.SEMANTIC, FindOptions.KEYWORD],
        filter_expression=filters.FilterExpression(
            field=_build_field_filter_expression(
                task_ident,
                resource=resource,
                session_id=session_id,
            )
        ),
        top_k=top_k,
        rephrase=False,
        reranker=RerankerName.NOOP,
    )
    return find_request


def _build_ask_request(
    task_ident: str,
    query: str,
    resource: str,
    session_id: str | None,
    include_global_facts: bool,
    global_facts_rid: str | None,
    extra_context: list[str] | None,
    global_facts: list[str],
    resource_facts: list[str],
    context: list[ChatContextMessage] | None,
    custom_prompt: CustomPrompt | None,
    ask_request_overrides: dict[str, Any] | None,
) -> AskRequest:
    """Build and return the AskRequest, applying any caller-supplied field overrides."""
    top_k = 5
    ask_request = AskRequest(
        query=query,
        top_k=top_k,
        citations=CitationsType.LLM_FOOTNOTES,
        rephrase=False,
        reranker=PredictReranker(window=min(top_k * 5, 200)),
        prompt=custom_prompt,
        filter_expression=filters.FilterExpression(
            field=_build_field_filter_expression(
                task_ident,
                resource=resource,
                session_id=session_id,
                include_global_facts=include_global_facts,
                session_global_facts_resource_id=global_facts_rid,
            )
        ),
        chat_history=context,
        extra_context=(extra_context or []) + global_facts + resource_facts,
    )
    if ask_request_overrides:
        for key, value in ask_request_overrides.items():
            if hasattr(ask_request, key):
                setattr(ask_request, key, value)
            else:
                logger.warning(f"Unknown AskRequest field: {key}")
    return ask_request


def _build_graph_search_request(
    task_ident: str,
    resource: str,
    session_id: str,
) -> graph.requests.GraphSearchRequest:
    """Build the GraphSearchRequest used by graph(), scoped to entity-to-entity paths."""
    return graph.requests.GraphSearchRequest(
        top_k=500,
        filter_expression=graph.requests.GraphFilterExpression(
            field=_build_field_filter_expression(
                task_ident,
                resource=resource,
                session_id=session_id,
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
                    da_task=GRAPH_EXTRACTION_TEMPLATE.format(task_ident=task_ident),
                ),
            ],
        ),
    )


def _parse_catalog_response_to_resource_page(
    catalog_response: CatalogResponse,
) -> ResourcePage:
    """Convert a raw catalog API response into a ResourcePage model."""
    return ResourcePage(
        items=[
            Resource(
                id=resource.id,
                slug=resource.slug or "",
                title=resource.title or "",
                summary=resource.summary,
                status=_get_resource_status(resource),
            )
            for resource in catalog_response.resources.values()
            # Do not include global entry resources in the resource listing.
            if not (resource.slug or "").startswith(
                GLOBAL_ANNOTATIONS_RESOURCE_SLUG_PREFIX + "-"
            )
        ],
        total=catalog_response.fulltext.total if catalog_response.fulltext else 0,
        has_more=catalog_response.fulltext.next_page
        if catalog_response.fulltext
        else False,
    )
