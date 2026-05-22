from __future__ import annotations

import re
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, cast

from nucliadb_models import FieldTypeName
from nucliadb_models.conversation import Conversation, InputMessage, InputMessageContent
from nucliadb_models.filters import (
    And,
    Field,
    FilterExpression,
    Or,
    Resource,
)
from nucliadb_models.link import LinkField
from nucliadb_models.resource import ResourceField
from nucliadb_models.search import (
    AskRequest,
    CatalogRequest,
    CatalogResponse,
    CitationsType,
    PredictReranker,
    ResourceProperties,
    SyncAskResponse,
)
from nucliadb_models.text import TextField, TextFormat
from nucliadb_sdk.v2.exceptions import ConflictError, NotFoundError

from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.upload import NucliaUpload

# ─── Exceptions ─────────────────────────────────────────────────────────────


class EngramAlreadyExistsError(Exception):
    """Raised when attempting to create a new engram with a slug that already exists."""

    pass


class EngramNotFoundError(Exception):
    """Raised when an engram with the specified ID or slug cannot be found."""

    pass


# ─── Data models ─────────────────────────────────────────────────────────────


@dataclass
class Annotation:
    """A single annotation message attached to an engram."""

    ident: str
    timestamp: str
    text: str
    who: str


@dataclass
class Engram:
    """A discrete unit of memory stored in a Nuclia KnowledgeBox resource."""

    id: str
    slug: str
    title: str
    summary: Optional[str] = None
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class RecallCitation:
    id: str
    text: str


@dataclass
class RecallResult:
    """Result of a generative `recall()` call."""

    answer: str
    citations: dict[str, RecallCitation]


@dataclass
class EngramPage:
    """A paginated listing of engrams."""

    items: list[Engram]
    total: int
    has_more: bool


# ─── Sync Memory ─────────────────────────────────────────────────────────────


class NucliaMemory:
    """
    Persistent, queryable memory for AI agents backed by a Nuclia KnowledgeBox.

    All methods accept the standard ``url`` / ``api_key`` keyword arguments
    (or fall back to the configured default KB) that are forwarded to the
    ``@kb`` decorator.

    Example::

        from nuclia.sdk.memory import NucliaMemory

        mem = NucliaMemory()

        engram_id = mem.remember("The deployment uses GitHub Actions.")
        result    = mem.recall("How does deployment work?")
        print(result.answer)
    """

    def __init__(self):
        self.kb = NucliaKB()
        self.upload = NucliaUpload()
        self._user_email = None

    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    @property
    def _authenticated_user_email(self) -> str:
        if self._user_email is None:
            auth = self._auth
            self._user_email = auth.get_user().email
        return self._user_email

    # ── store ────────────────────────────────────────────────────────────

    @kb
    def store(
        self,
        text: Optional[str] = None,
        *,
        engram: Optional[str] = None,
        title: Optional[str] = None,
        slug: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None,
        summary: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Store a text engram or append content to an existing one.

        Parameters
        ----------
        text:
            The text content to store.
        engram:
            Existing engram ID or slug to append to.
        title:
            Optional resource title (new engrams only).
        slug:
            Optional resource slug (new engrams only).
        url:
            Optional resource URL (new engrams only).
        path:
            Path to a local file to upload as engram content (new engrams only).
        summary:
            Optional resource summary (new engrams only).
        """
        if engram:
            try:
                self._store_to_existing_engram(
                    engram=engram,
                    text=text,
                    url=url,
                    path=path,
                )
            except NotFoundError:
                raise EngramNotFoundError(f"Engram '{engram}' not found.")
        else:
            try:
                self._store_to_new_engram(
                    slug=slug,
                    title=title,
                    summary=summary,
                    text=text,
                    url=url,
                    path=path,
                )
            except ConflictError:
                raise EngramAlreadyExistsError(
                    f"Engram with slug '{slug}' already exists."
                )

    def _store_to_existing_engram(
        self,
        engram: Optional[str] = None,
        text: Optional[str] = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        """Store content in an existing engram."""
        if not text and not path and not url:
            raise ValueError("At least one of text, path, or url must be provided.")

        # Append to existing engram
        base_args = {}
        ruuid, rslug = uuid_or_slug(engram)
        if ruuid:
            base_args["rid"] = ruuid
        else:
            assert rslug is not None
            base_args["slug"] = rslug

        update_args = base_args.copy()
        field_id = uuid.uuid4().hex
        if text or url:
            if text:
                update_args["texts"] = {
                    field_id: TextField(
                        body=text,
                        format=TextFormat.PLAIN,
                    )
                }
            if url:
                update_args["links"] = {
                    field_id: LinkField(
                        uri=url,
                    )
                }
            self.kb.resource.update(**update_args)

        if path:
            upload_args = {"path": path, "field": field_id, **base_args}
            self.upload.file(**upload_args)

    def _store_to_new_engram(
        self,
        slug: Optional[str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        text: Optional[str] = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
    ) -> None:
        if not text and not path and not url:
            raise ValueError("At least one of text, path, or url must be provided.")
        if title is None:
            title = infer_title(slug=slug, text=text, path=path, url=url)
        if slug is None:
            slug = slugify(title)
        create_args = {
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

    # ── recall ───────────────────────────────────────────────────────────────

    @kb
    def recall(
        self,
        query: str,
        *,
        engram: str,
        who: Optional[str] = None,
        **kwargs,
    ) -> RecallResult:
        """Ask a question and get a generative answer grounded in stored engrams.

        Parameters
        ----------
        query:
            Natural-language question.
        engram:
            Scope the answer to a single engram (ID or slug).
        who:
            Filter search context to this user's annotations. Pass ``"*"``
            to include all users' annotations. Defaults to authenticated user.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        if who is None:
            who = self._authenticated_user_email
        filter_expression = self._build_recall_filter_expression(
            engram=engram,
            who=who,
            ndb=ndb,
        )
        ask_request = AskRequest(
            query=query,
            top_k=5,
            citations=CitationsType.LLM_FOOTNOTES,
            rephrase=True,
            reranker=PredictReranker(window=50),
            prefer_markdown=True,
            filter_expression=filter_expression,
        )
        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=kbid, content=ask_request)
        answer, citations = parse_recall_answer(ask_response)
        result = RecallResult(answer=answer, citations=citations)
        return result

    # ── annotate ─────────────────────────────────────────────────────────────

    @kb
    def annotate(
        self,
        *,
        engram: str,
        text: str,
        who: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Append a note to an existing engram.

        Parameters
        ----------
        engram:
            Engram ID or slug.
        text:
            Annotation text.
        who:
            Author identifier (defaults to authenticated user).
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        if who is None:
            who = self._authenticated_user_email
        field_id = annotation_field_id(who)
        ruuid, rslug = uuid_or_slug(engram)
        message = InputMessage(
            timestamp=datetime.now(tz=timezone.utc),
            ident=uuid.uuid4().hex,
            who=who,
            content=InputMessageContent(
                text=text,
            ),
        )
        if ruuid:
            ndb.ndb.add_conversation_message(
                kbid=kbid, rid=ruuid, field_id=field_id, content=[message]
            )
        else:
            assert rslug is not None
            ndb.ndb.add_conversation_message_by_slug(
                kbid=kbid, slug=rslug, field_id=field_id, content=[message]
            )

    # ── forget ───────────────────────────────────────────────────────────────

    @kb
    def forget(
        self,
        *,
        engram: str,
        annotation: Optional[str] = None,
        annotations: bool = False,
        who: Optional[str] = None,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """Delete an engram, specific annotation(s), or the entire memory.

        Parameters
        ----------
        engram:
            Engram ID or slug to target.
        annotation:
            Specific annotation ``ident`` to delete.
        annotations:
            If ``True``, delete all annotations by ``who`` on the engram.
        who:
            Author filter for annotation deletion (defaults to authenticated user).
        confirm:
            When set to True, confirms the deletion of the engram.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = uuid_or_slug(engram)
        if not annotation and not annotations:
            if not confirm:
                raise ValueError(
                    "Deleting an entire engram is irreversible. To confirm, set confirm=True."
                )
            # Delete entire engram
            self.kb.resource.delete(rid=ruuid, slug=rslug)
            return
        if who == "*":
            raise ValueError("Bulk deletion of all users' annotations is not allowed.")
        if who is None:
            who = self._authenticated_user_email
        if annotations:
            # Delete all annotatios for the user on this engram
            self._delete_user_annotations(
                rid=ruuid,
                slug=rslug,
                who=who,
                ndb=ndb,
            )
        elif annotation:
            # Delete a particular annotation by id
            self._delete_annotation_by_id(
                rid=ruuid,
                slug=rslug,
                annotation_id=annotation,
                who=who,
                ndb=ndb,
            )

    def _delete_user_annotations(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        who: str,
        ndb: NucliaDBClient,
    ) -> None:
        # Delete both the raw annotations and the auto-generated summary for that user
        field_ids = [
            annotation_field_id(who),
            annotation_summary_field_id(who),
        ]
        for field_id in field_ids:
            try:
                if rid:
                    ndb.ndb.delete_field_by_id(
                        kbid=ndb.kbid,
                        rid=rid,
                        field_type=FieldTypeName.CONVERSATION.value,
                        field_id=field_id,
                    )
                else:
                    assert slug is not None
                    ndb.ndb.delete_field_by_slug(
                        kbid=ndb.kbid,
                        slug=slug,
                        field_type=FieldTypeName.CONVERSATION.value,
                        field_id=field_id,
                    )
            except NotFoundError:
                # If the summary field doesn't exist, we can ignore the error and continue.
                pass

    def _delete_annotation_by_id(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        annotation_id: str,
        who: str,
        ndb: NucliaDBClient,
    ) -> None:
        # Delete the annotation from both the raw annotations field and the auto-generated
        # summary field for that user (if it exists) to maintain the 1-to-1 mapping.
        field_ids = [
            annotation_field_id(who),
            annotation_summary_field_id(who),
        ]
        for field_id in field_ids:
            try:
                if rid:
                    ndb.ndb.delete_conversation_message(
                        kbid=ndb.kbid,
                        rid=rid,
                        field_id=field_id,
                        message_id=annotation_id,
                    )
                else:
                    assert slug is not None
                    ndb.ndb.delete_conversation_message_by_slug(
                        kbid=ndb.kbid,
                        slug=slug,
                        field_id=field_id,
                        message_id=annotation_id,
                    )
            except NotFoundError:
                # If the summary message doesn't exist, we can ignore the error and continue.
                pass

    # ── get ─────────────────────────────────────────────────────────────────

    @kb
    def get(
        self,
        *,
        engram: str,
        who: Optional[str] = None,
        **kwargs,
    ) -> Engram:
        """Retrieve an engram by ID or slug."""
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = uuid_or_slug(engram)
        resource = self.kb.resource.get(
            rid=ruuid,
            slug=rslug,
            show=[
                ResourceProperties.BASIC.value,
                ResourceProperties.VALUES.value,
            ],
        )
        engram = Engram(
            id=resource.id,
            slug=resource.slug,
            title=resource.title,
            summary=resource.summary or None,
            annotations=[],
        )
        if who is None:
            who = self._authenticated_user_email
        annotations = self._get_most_recent_user_annotations(
            engram.id, who, ndb=ndb, n=10
        )
        engram.annotations = annotations
        return engram

    # ── list ─────────────────────────────────────────────────────────────────

    @kb
    def list(
        self,
        *,
        query: str = "",
        page: int = 0,
        size: int = 20,
        **kwargs,
    ) -> EngramPage:
        """List engrams in this memory.

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
        engram_page = EngramPage(
            items=[
                Engram(
                    id=resource.id,
                    slug=resource.slug,
                    title=resource.title,
                    summary=resource.summary or None,
                )
                for resource in catalog_response.resources.values()
            ],
            total=catalog_response.fulltext.total,
            has_more=catalog_response.fulltext.next_page,
        )
        return engram_page

    # ── utils ────────────────────────────────────────────────────────────

    def _build_recall_filter_expression(
        self,
        engram: str,
        who: str,
        ndb: NucliaDBClient,
    ) -> FilterExpression:
        # First, add the filter for the resource representing the engram
        ruuid, rslug = uuid_or_slug(engram)
        if ruuid:
            resource_filter = Resource(id=ruuid)
        else:
            assert rslug is not None
            resource_filter = Resource(slug=rslug)

        # Then add filters for the current user's annotations on that resource (if any)
        field_filter = None
        if who != "*":
            resource_fields = self._get_all_resource_fields(
                rid=ruuid, slug=rslug, ndb=ndb
            )
            field_filter_operands = []
            for field_type, field_id in resource_fields:
                is_annotation_field = (
                    field_type == FieldTypeName.CONVERSATION
                    and field_id.startswith(f"memory--")
                )
                is_user_annotation_field = (
                    is_annotation_field and field_id == annotation_field_id(who)
                )
                if is_user_annotation_field or not is_annotation_field:
                    field_filter_operands.append(Field(type=field_type, name=field_id))
            if len(field_filter_operands) == 1:
                field_filter = field_filter_operands[0]
            elif len(field_filter_operands) > 1:
                field_filter = Or(operands=field_filter_operands)

        # Finally, combine the resource filter and the field filter (if any)
        if field_filter is not None:
            filter_expression = FilterExpression(
                field=And(operands=[resource_filter, field_filter])
            )
        else:
            filter_expression = FilterExpression(field=resource_filter)
        return filter_expression

    def _get_all_resource_fields(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        ndb: NucliaDBClient,
    ) -> list[tuple[FieldTypeName, str]]:
        if rid:
            resource = ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid,
                rid=rid,
                query_params={"show": [ResourceProperties.VALUES.value]},
            )
        else:
            assert slug is not None
            resource = ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid,
                slug=slug,
                query_params={"show": [ResourceProperties.VALUES.value]},
            )
        assert resource.data is not None

        return [
            *(
                (FieldTypeName.CONVERSATION, id)
                for id in resource.data.conversations or {}
            ),
            *((FieldTypeName.TEXT, id) for id in resource.data.texts or {}),
            *((FieldTypeName.LINK, id) for id in resource.data.links or {}),
            *((FieldTypeName.FILE, id) for id in resource.data.files or {}),
            *((FieldTypeName.GENERIC, id) for id in resource.data.generics or {}),
            *((FieldTypeName.KEY_VALUE, id) for id in resource.data.key_values or {}),
        ]

    def _get_most_recent_user_annotations(
        self,
        engram_id: str,
        who: str,
        ndb: NucliaDBClient,
        n: int = 10,
    ) -> list[Annotation]:
        """
        TODO: First, get the resource to check how many pages the conversation has.
        This way, we can easily paginate backwards.
        """
        kbid = ndb.kbid
        field_id = annotation_field_id(who)
        field: ResourceField = ndb.ndb.get_resource_field(
            kbid=kbid,
            rid=engram_id,
            field_type=FieldTypeName.CONVERSATION.value,
            field_id=field_id,
            query_params={"page": "last"},
        )
        if field.value is None:
            return []
        conversation = cast(Conversation, field.value)

        # Return the last n messages by the user on this engram as annotations, in reverse chronological order
        for message in reversed(conversation.messages or []):
            if not message.content.text:
                # Skip deleted messages
                continue
            annotations.append(
                Annotation(
                    ident=message.ident,
                    timestamp=message.timestamp,
                    text=message.content.text or "",
                    who=message.who,
                )
            )
            if len(annotations) >= n:
                break
        return annotations


# ─── Async Memory ─────────────────────────────────────────────────────────────


class AsyncNucliaMemory:
    """
    Async version of :class:`NucliaMemory`.

    Example::

        from nuclia.sdk.memory import AsyncNucliaMemory

        mem = AsyncNucliaMemory()

        engram_id = await mem.remember("The deployment uses GitHub Actions.")
        result    = await mem.recall("How does deployment work?")
        print(result.answer)
    """

    @property
    def _auth(self) -> AsyncNucliaAuth:
        return get_async_auth()

    # ── remember ────────────────────────────────────────────────────────────

    @kb
    async def remember(
        self,
        text: Optional[str] = None,
        *,
        engram: Optional[str] = None,
        title: Optional[str] = None,
        slug: Optional[str] = None,
        format: TextFormat = TextFormat.PLAIN,
        **kwargs,
    ) -> str:
        """Async version of :meth:`NucliaMemory.remember`."""
        raise NotImplementedError

    # ── recall ───────────────────────────────────────────────────────────────

    @kb
    async def recall(
        self,
        query: str,
        *,
        engram: Optional[str] = None,
        who: Optional[str] = None,
        **kwargs,
    ) -> RecallResult:
        """Async version of :meth:`NucliaMemory.recall`."""
        raise NotImplementedError

    # ── annotate ─────────────────────────────────────────────────────────────

    @kb
    async def annotate(
        self,
        *,
        engram: str,
        text: str,
        who: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Async version of :meth:`NucliaMemory.annotate`."""
        raise NotImplementedError

    # ── forget ───────────────────────────────────────────────────────────────

    @kb
    async def forget(
        self,
        *,
        engram: Optional[str] = None,
        annotation: Optional[str] = None,
        annotations: bool = False,
        who: Optional[str] = None,
        all: bool = False,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """Async version of :meth:`NucliaMemory.forget`."""
        raise NotImplementedError

    # ── list ─────────────────────────────────────────────────────────────────

    @kb
    async def list(
        self,
        *,
        query: str = "",
        page: int = 0,
        size: int = 20,
        **kwargs,
    ) -> EngramPage:
        """Async version of :meth:`NucliaMemory.list`."""
        raise NotImplementedError


def uuid_or_slug(engram: str) -> tuple[str | None, str | None]:
    """Helper to determine if engram identifier is a UUID or slug."""
    ruuid = None
    rslug = None
    try:
        ruuid = str(uuid.UUID(engram))
    except ValueError:
        rslug = engram
    return ruuid, rslug


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    Slugs cannot contain special characters or spaces, and are typically lowercase with words separated by hyphens.
    """
    allowed_characters = string.ascii_letters + string.digits + " "
    cleaned_text = "".join(c for c in text if c in allowed_characters)
    return cleaned_text.lower().replace(" ", "-")


def infer_title(
    *,
    slug: Optional[str] = None,
    text: Optional[str] = None,
    path: Optional[str] = None,
    url: Optional[str] = None,
):
    """
    Try to infer a human-friendly title for an engram based on available metadata.
    """
    if slug:
        title = slug
    elif text:
        title = text[:50]
    elif path:
        title = path.split("/")[-1]
    elif url:
        title = url.split("/")[-1]
    else:
        title = "Untitled engram"
    title = title.replace("-", " ").title()
    return title


def parse_recall_answer(
    ask_response: SyncAskResponse,
) -> tuple[str, dict[str, RecallCitation]]:
    """Parse an LLM footnotes answer into clean text and citations mapping."""
    parts = ask_response.answer.rsplit("\n\n", 1)
    answer_text = parts[0]
    citations: dict[str, RecallCitation] = {}
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
                citations[footnote_id] = RecallCitation(
                    id=chunk_id,
                    text=retrieved_paragraphs[chunk_id].text,
                )
    return answer_text, citations


def annotation_field_id(user_email: str) -> str:
    """Helper to generate the field ID for a user's annotation conversation field."""
    user_email = user_email.replace("@", "_at_").replace(".", "_dot_")
    return f"memory--{user_email}"


def annotation_summary_field_id(user_email: str) -> str:
    """Helper to generate the field ID for a user's annotation summary field."""
    user_email = user_email.replace("@", "_at_").replace(".", "_dot_")
    return f"memory--{user_email}--summary"


if __name__ == "__main__":
    memory = NucliaMemory()

    # Create a new engram
    try:
        memory.store(
            "Employees are entitled to 22 working days of paid vacation per year. "
            "Vacation must be requested at least 2 weeks in advance. "
            "A maximum of 10 consecutive days can be taken without director approval. "
            "Unused days cannot be carried over to the next year.",
            title="Vacation Policy",
            slug="vacation-policy",
        )
    except EngramAlreadyExistsError:
        print("Engram already exists, skipping creation.")

    memory.annotate(
        engram="vacation-policy",
        text="Catalan employees have an exception allowing up to 60 consecutive days.",
    )

    engram = memory.get(engram="vacation-policy")

    # List engrams
    engrams = memory.list()
    for engram in engrams.items:
        print(f"- {engram.title} (id={engram.id}, slug={engram.slug})")

    # Recall
    question = "Can a Catalan employee take 15 consecutive vacation days?"
    result = memory.recall(question, engram="vacation-policy")
    print(f"Question: {question}")
    print()
    print(f"Answer: {result.answer}")
    print()
    print(f"Citations: {result.citations}")
