from __future__ import annotations

import logging
import re
import string
import unicodedata
import uuid
from typing import Any, overload
from urllib.parse import urlparse

from nucliadb_models import filters
from nucliadb_models.link import LinkField
from nucliadb_models.resource import Resource
from nucliadb_models.search import (
    AskRequest,
    CatalogRequest,
    CatalogResponse,
    ChatContextMessage,
    CitationsType,
    PredictReranker,
    ResourceProperties,
    SyncAskResponse,
)
from nucliadb_models.text import TextField, TextFormat
from nucliadb_sdk.v2.exceptions import ConflictError, NotFoundError
from pydantic import BaseModel

from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.upload import NucliaUpload

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


# ─── Exceptions ─────────────────────────────────────────────────────────────


class TopicAlreadyExistsError(Exception):
    """Raised when attempting to create a new topic with a slug that already exists."""

    pass


class TopicNotFoundError(Exception):
    """Raised when an topic with the specified ID or slug cannot be found."""

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


class RecallCitation(BaseModel):
    chunk_id: str
    text: str


class RecallResult(BaseModel):
    """Result of a generative `recall()` call."""

    answer: str
    citations: dict[str, RecallCitation]


class TopicPage(BaseModel):
    """A paginated listing of topics."""

    items: list[Topic]
    total: int
    has_more: bool


# ─── Sync Memory ─────────────────────────────────────────────────────────────


class NucliaMemory:
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

    # ── recall ───────────────────────────────────────────────────────────────

    @kb
    def recall(
        self,
        query: str,
        *,
        topic: str,
        context: list[ChatContextMessage] | None = None,
        **kwargs,
    ) -> RecallResult:
        """Ask a question and get a generative answer grounded in stored topics.

        Parameters
        ----------
        query:
            Natural-language question.
        topic:
            Scope the answer to a single topic (ID or slug).
        context:
            Optional list of past messages to include as additional context for the recall. Messages should be ordered from oldest to most recent.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        filter_expression = self._build_recall_filter_expression(topic=topic)
        ask_request = AskRequest(
            query=query,
            top_k=5,
            citations=CitationsType.LLM_FOOTNOTES,
            rephrase=True,
            reranker=PredictReranker(window=50),
            prefer_markdown=True,
            filter_expression=filter_expression,
            chat_history=context,
        )
        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=kbid, content=ask_request)
        answer, citations = _parse_recall_answer(ask_response)
        result = RecallResult(answer=answer, citations=citations)
        return result

    # ── forget ───────────────────────────────────────────────────────────────

    @kb
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
        ruuid, rslug = _uuid_or_slug(topic)
        if not confirm:
            raise ValueError(
                "Deleting an entire topic is irreversible. To confirm, set confirm=True."
            )
        # Delete entire topic
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

    # ── utils ────────────────────────────────────────────────────────────

    def _build_recall_filter_expression(
        self,
        topic: str,
    ) -> filters.FilterExpression:
        ruuid, rslug = _uuid_or_slug(topic)
        if ruuid:
            resource_filter = filters.Resource(id=ruuid)
        else:
            assert rslug is not None
            resource_filter = filters.Resource(slug=rslug)
        filter_expression = filters.FilterExpression(field=resource_filter)
        return filter_expression


# ─── Async Memory (TODO) ─────────────────────────────────────────────────────────────


# ─── Utils ─────────────────────────────────────────────────────────────


def _uuid_or_slug(topic: str) -> tuple[str | None, str | None]:
    """Helper to determine if topic identifier is a UUID or slug."""
    ruuid = None
    rslug = None
    try:
        ruuid = str(uuid.UUID(topic))
    except ValueError:
        rslug = topic
    return ruuid, rslug


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


def _parse_recall_answer(
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
                    chunk_id=chunk_id,
                    text=retrieved_paragraphs[chunk_id].text,
                )
    return answer_text, citations


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
