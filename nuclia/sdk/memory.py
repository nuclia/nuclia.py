from __future__ import annotations

import logging
import re
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast, overload

from nucliadb_models import FieldTypeName, filters
from nucliadb_models.conversation import (
    Conversation,
    InputMessage,
    InputMessageContent,
    Message,
)
from nucliadb_models.link import LinkField
from nucliadb_models.resource import Resource, ResourceField
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
from pydantic import BaseModel, ValidationError

from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.upload import NucliaUpload

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


# ─── Exceptions ─────────────────────────────────────────────────────────────


class topicAlreadyExistsError(Exception):
    """Raised when attempting to create a new topic with a slug that already exists."""

    pass


class topicNotFoundError(Exception):
    """Raised when an topic with the specified ID or slug cannot be found."""

    pass


# ─── Data models ─────────────────────────────────────────────────────────────


@dataclass
class AnnotationContextMessage:
    """A context message attached to an annotation."""

    author: str
    text: str


class AnnotationContent(BaseModel):
    """The content of the annotation with separate fields for the text, reasoning, and context."""

    text: str
    reasoning: str | None = None
    context: list[AnnotationContextMessage] | None = None


class Annotation(BaseModel):
    """A single annotation message attached to an topic."""

    id: str
    timestamp: datetime
    content: AnnotationContent
    attachments: list[str] | None = None

    @classmethod
    def from_conversation_message(cls, message: Message) -> "Annotation":
        content = AnnotationContent.model_validate_json(message.content.text or "")
        return cls(
            id=message.ident,
            timestamp=message.timestamp,
            content=content,
            attachments=message.content.attachments_fields,
        )


class Fact(BaseModel):
    """
    A fact is a special type of annotation that represents an objective piece of information about the topic, as opposed to a subjective note or comment.
    Facts can be used to store key details or metadata about the topic that may be useful for recall or reference later on.
    Facts are generated automatically by the system from a specific annotation.
    """

    id: str
    timestamp: datetime
    text: str

    def from_conversation_message(cls, message: Message) -> "Fact":
        return cls(
            id=message.ident,
            timestamp=message.timestamp,
            text=message.content.text,
        )


@dataclass
class Topic:
    """A discrete unit of memory stored in the memory.
    Corresponds to a single resource in a Nuclia Knowledge Box.
    """

    id: str
    slug: str
    title: str
    summary: str | None = None
    annotations: list[Annotation] | None = None
    facts: list[Annotation] | None = None


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
class TopicPage:
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
                raise topicNotFoundError(f"topic '{topic}' not found.")
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
                raise topicAlreadyExistsError(
                    f"topic with slug '{slug}' already exists."
                )

    def _store_to_existing_topic(
        self,
        topic: str | None = None,
        text: str | None = None,
        url: str | None = None,
        path: str | None = None,
    ) -> None:
        if not text and not path and not url:
            raise ValueError("At least one of text, path, or url must be provided.")
        base_args = {}
        ruuid, rslug = uuid_or_slug(topic)
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
        topic: str,
        who: str | None = None,
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
        who:
            Filter search context to this user's annotations. Pass ``"*"``
            to include all users' annotations. Defaults to authenticated user.
        context:
            Optional list of past messages to include as additional context for the recall. Messages should be ordered from oldest to most recent.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        if who is None:
            who = self._authenticated_user_email
        filter_expression = self._build_recall_filter_expression(
            topic=topic,
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
            chat_history=context,
        )
        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=kbid, content=ask_request)
        answer, citations = parse_recall_answer(ask_response)
        result = RecallResult(answer=answer, citations=citations)
        return result

    # ── annotate ─────────────────────────────────────────────────────────────

    @kb
    def annotate(
        self,
        text: str | None = None,
        *,
        topic: str,
        context: list[AnnotationContextMessage] | None = None,
        reasoning: str | None = None,
        attachments: list[str] | None = None,
        metadata: dict | None = None,
        who: str | None = None,
        **kwargs,
    ) -> None:
        """Append a note to an existing topic.

        Parameters
        ----------
        text:
            Annotation text (the decision or fact to record).
        topic:
            topic ID or slug.
        context:
            Optional list of context messages that led to this annotation.
            Each entry is a dict with ``author`` and ``text`` keys, representing
            the conversational history or evidence that informed the decision.
        reasoning:
            Optional explanation of why this annotation was made. Useful for
            agents to record the logic behind a decision.
        attachments:
            Optional list of file paths to attach as supporting evidence.
        who:
            Author identifier (defaults to authenticated user).
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        kbid = ndb.kbid
        if who is None:
            who = self._authenticated_user_email
        field_id = annotation_field_id(who)
        ruuid, rslug = uuid_or_slug(topic)
        message = InputMessage(
            timestamp=datetime.now(tz=timezone.utc),
            ident=uuid.uuid4().hex,
            who=who,
            content=InputMessageContent(
                text=text,
            ),
        )
        add_conversation_args = {
            "kbid": kbid,
            "field_id": field_id,
            "content": [message],
        }
        if ruuid:
            add_conversation_args["rid"] = ruuid
            add_conversation_message = ndb.ndb.add_conversation_message
        else:
            assert rslug is not None
            add_conversation_args["slug"] = rslug
            add_conversation_message = ndb.ndb.add_conversation_message_by_slug
        add_conversation_message(**add_conversation_args)

    # ── forget ───────────────────────────────────────────────────────────────

    @kb
    def forget(
        self,
        *,
        topic: str,
        annotation: str | None = None,
        annotations: bool = False,
        who: str | None = None,
        confirm: bool = False,
        **kwargs,
    ) -> None:
        """Delete an topic, specific annotation(s), or the entire memory.

        Parameters
        ----------
        topic:
            topic ID or slug to target.
        annotation:
            Specific annotation ``ident`` to delete.
        annotations:
            If ``True``, delete all annotations by ``who`` on the topic.
        who:
            Author filter for annotation deletion (defaults to authenticated user).
        confirm:
            When set to True, confirms the deletion of the topic.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = uuid_or_slug(topic)
        if not annotation and not annotations:
            if not confirm:
                raise ValueError(
                    "Deleting an entire topic is irreversible. To confirm, set confirm=True."
                )
            # Delete entire topic
            self.kb.resource.delete(rid=ruuid, slug=rslug)
            return
        if who == "*":
            raise ValueError("Bulk deletion of all users' annotations is not allowed.")
        if who is None:
            who = self._authenticated_user_email
        if annotations:
            # Delete all annotatios for the user on this topic
            self._delete_annotations(
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

    def _delete_annotations(
        self,
        *,
        rid: str | None = None,
        slug: str | None = None,
        who: str,
        ndb: NucliaDBClient,
    ) -> None:
        # Delete both the raw annotations and the auto-generated summary for that user
        field_ids = [
            annotation_field_id(who),
            facts_field_id(who),
        ]
        for field_id in field_ids:
            delete_field_args = {
                "kbid": ndb.kbid,
                "field_type": FieldTypeName.CONVERSATION.value,
                "field_id": field_id,
            }
            if rid:
                delete_field_args["rid"] = rid
                delete_field = ndb.ndb.delete_field_by_id
            else:
                assert slug is not None
                delete_field_args["slug"] = slug
                delete_field = ndb.ndb.delete_field_by_slug
            try:
                delete_field(**delete_field_args)
            except NotFoundError:
                # If the summary field doesn't exist, we can ignore the error and continue.
                pass

    def _delete_annotation_by_id(
        self,
        *,
        rid: str | None = None,
        slug: str | None = None,
        annotation_id: str,
        who: str,
        ndb: NucliaDBClient,
    ) -> None:
        # Delete the annotation from both the raw annotations field and the auto-generated
        # summary field for that user (if it exists) to maintain the 1-to-1 mapping.
        field_ids = [
            annotation_field_id(who),
            facts_field_id(who),
        ]
        for field_id in field_ids:
            delete_conversation_message_args = {
                "kbid": ndb.kbid,
                "field_id": field_id,
                "message_id": annotation_id,
            }
            if rid:
                delete_conversation_message_args["rid"] = rid
                delete_conversation_message = ndb.ndb.delete_conversation_message
            else:
                assert slug is not None
                delete_conversation_message_args["slug"] = slug
                delete_conversation_message = (
                    ndb.ndb.delete_conversation_message_by_slug
                )
            try:
                delete_conversation_message(**delete_conversation_message_args)
            except NotFoundError:
                # If the summary message doesn't exist, we can ignore the error and continue.
                pass

    # ── get ─────────────────────────────────────────────────────────────────

    @kb
    def get(
        self,
        *,
        topic: str,
        who: str | None = None,
        annotations: int = 0,
        facts: int = 0,
        **kwargs,
    ) -> Topic:
        """Retrieve an topic by ID or slug."""

        # TODO: do not get all values on the GET resource.
        # Replace the ResourceProperties.VALUES.value with a more specific request inside _get_most_recent_messages to
        # get the corresponding pages of annotations.

        ndb: NucliaDBClient = kwargs["ndb"]
        ruuid, rslug = uuid_or_slug(topic)
        get_resource_args = {
            "kbid": ndb.kbid,
            "query_params": {
                "show": [
                    ResourceProperties.BASIC.value,
                    ResourceProperties.VALUES.value,
                ],
            },
        }
        if ruuid:
            get_resource_func = ndb.ndb.get_resource_by_id
            get_resource_args["rid"] = ruuid
        else:
            assert rslug is not None
            get_resource_func = ndb.ndb.get_resource_by_slug
            get_resource_args["slug"] = rslug
        resource: Resource = get_resource_func(**get_resource_args)
        topic = Topic(
            id=resource.id,
            slug=resource.slug,
            title=resource.title,
            summary=resource.summary or None,
            annotations=None,
            facts=None,
        )
        if who == "*":
            raise ValueError("Retrieving all users' annotations is not allowed.")
        if who is None:
            who = self._authenticated_user_email
        if annotations > 0:
            topic.annotations = self._get_annotations(
                resource, who, ndb=ndb, n=annotations
            )
        if facts > 0:
            topic.facts = self._get_facts(resource, who, ndb=ndb, n=facts)
        return topic

    def _get_annotations(
        self,
        resource: Resource,
        who: str,
        ndb: NucliaDBClient,
        n: int = 10,
    ) -> list[Annotation]:
        field_id = annotation_field_id(who)
        messages = self._get_most_recent_messages(
            resource=resource,
            field_id=field_id,
            ndb=ndb,
            n=n,
        )
        annotations = []
        for message in messages:
            try:
                annotation = Annotation.from_conversation_message(message)
            except ValidationError:
                logger.warning(
                    f"Skipping message with id {message.ident} in facts field {field_id} because it does not conform to the expected format."
                )
                continue
            annotations.append(annotation)
        return annotations

    def _get_facts(
        self,
        resource: Resource,
        who: str,
        ndb: NucliaDBClient,
        n: int = 10,
    ) -> list[Annotation]:
        field_id = facts_field_id(who)
        messages = self._get_most_recent_messages(
            resource=resource,
            field_id=field_id,
            ndb=ndb,
            n=n,
        )
        facts = []
        for message in messages:
            try:
                fact = Fact.from_conversation_message(message)
            except ValidationError:
                logger.warning(
                    f"Skipping message with id {message.ident} in facts field {field_id} because it does not conform to the expected format."
                )
                continue
            facts.append(fact)
        return facts

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
                topic(
                    id=resource.id,
                    slug=resource.slug,
                    title=resource.title,
                    summary=resource.summary or None,
                    annotations=[],  # Do not load annotations in list view for performance reasons
                )
                for resource in catalog_response.resources.values()
            ],
            total=catalog_response.fulltext.total,
            has_more=catalog_response.fulltext.next_page,
        )
        return topic_page

    # ── utils ────────────────────────────────────────────────────────────

    def _build_recall_filter_expression(
        self,
        topic: str,
        who: str,
        ndb: NucliaDBClient,
    ) -> filters.FilterExpression:
        """
        To build the filter expression for the recall we need to include the explicit list of fields
        we want to do retrieval on.

        This implies we need to do an extra get request to obtain the list of fields, which is not ideal.
        An alternative approach 


        
        """
        # First, add the filter for the resource representing the topic
        ruuid, rslug = uuid_or_slug(topic)
        if ruuid:
            resource_filter = filters.Resource(id=ruuid)
        else:
            assert rslug is not None
            resource_filter = filters.Resource(slug=rslug)

        # Then add filters for the current user's annotations on that resource (if any)
        field_filter = None
        if who != "*":
            resource_fields = self._get_all_resource_fields(
                rid=ruuid, slug=rslug, ndb=ndb
            )
            field_filter_operands = []
            for field_type, field_id in resource_fields:
                is_memory_field = (
                    field_type == FieldTypeName.CONVERSATION
                    and field_id.startswith(f"memory--")
                )
                is_annotation_field = (
                    is_memory_field and field_id == annotation_field_id(who)
                )
                is_facts_field = is_memory_field and field_id == facts_field_id(who)
                if is_annotation_field or is_facts_field or not is_memory_field:
                    field_filter_operands.append(
                        filters.Field(type=field_type, name=field_id)
                    )
            if len(field_filter_operands) == 1:
                field_filter = field_filter_operands[0]
            elif len(field_filter_operands) > 1:
                field_filter = filters.Or(operands=field_filter_operands)

        # Finally, combine the resource filter and the field filter (if any)
        if field_filter is not None:
            filter_expression = filters.FilterExpression(
                field=filters.And(operands=[resource_filter, field_filter])
            )
        else:
            filter_expression = filters.FilterExpression(field=resource_filter)
        return filter_expression

    def _get_all_resource_fields(
        self,
        *,
        rid: str | None = None,
        slug: str | None = None,
        ndb: NucliaDBClient,
    ) -> list[tuple[FieldTypeName, str]]:
        get_resource_args = {
            "kbid": ndb.kbid,
            "query_params": {
                "show": [
                    ResourceProperties.ERRORS.value,
                ],
            },
        }
        if rid:
            get_resource_args["rid"] = rid
            get_resource = ndb.ndb.get_resource_by_id
        elif slug:
            get_resource_args["slug"] = slug
            get_resource = ndb.ndb.get_resource_by_slug
        else:
            raise ValueError("Either rid or slug must be provided.")
        resource: Resource = get_resource(**get_resource_args)
        if resource.data is None:
            return []
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

    def _get_most_recent_messages(
        self,
        resource: Resource,
        field_id: str,
        ndb: NucliaDBClient,
        n: int = 10,
    ) -> list[Message]:
        if (
            resource.data is None
            or resource.data.conversations is None
            or resource.data.conversations.get(field_id) is None
            or resource.data.conversations[field_id].value is None
        ):
            return []
        conversation = resource.data.conversations[field_id]
        total_messages = conversation.value.total
        current_page = conversation.value.pages
        messages = []
        # Get from the most recent messages backwards.
        while True:
            if current_page <= 0 or total_messages == 0:
                break
            page = self._get_page_of_conversation_messages(
                resource_id=resource.id,
                field_id=field_id,
                ndb=ndb,
                page=str(current_page),
            )
            for message in reversed(page):
                messages.append(message)
                if len(messages) >= n:
                    break
            if len(messages) >= n:
                break
            current_page -= 1
        return messages

    def _get_page_of_conversation_messages(
        self,
        resource_id: str,
        field_id: str,
        ndb: NucliaDBClient,
        page: str,
    ) -> list[Message]:
        kbid = ndb.kbid
        field: ResourceField = ndb.ndb.get_resource_field(
            kbid=kbid,
            rid=resource_id,
            field_type=FieldTypeName.CONVERSATION.value,
            field_id=field_id,
            query_params={"page": page},
        )
        if field.value is None:
            return []
        conversation = cast(Conversation, field.value)
        return [
            message
            for message in conversation.messages or []
            if message.content.text  # Skip deleted messages
        ]


# ─── Async Memory (TODO) ─────────────────────────────────────────────────────────────


def uuid_or_slug(topic: str) -> tuple[str | None, str | None]:
    """Helper to determine if topic identifier is a UUID or slug."""
    ruuid = None
    rslug = None
    try:
        ruuid = str(uuid.UUID(topic))
    except ValueError:
        rslug = topic
    return ruuid, rslug


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    Slugs cannot contain special characters or spaces, and are typically lowercase with words separated by hyphens.
    Examples:
    - "My Vacation Policy" -> "my-vacation-policy"
    - "Project Plan v2.0!" -> "project-plan-v20"
    """
    allowed_characters = string.ascii_letters + string.digits + " " + "-"
    cleaned_text = "".join(c for c in text if c in allowed_characters)
    return cleaned_text.lower().replace(" ", "-")


def infer_title(
    *,
    slug: str | None = None,
    text: str | None = None,
    path: str | None = None,
    url: str | None = None,
):
    """
    Try to infer a human-friendly title for an topic based on available metadata.
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
        title = "Untitled topic"
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


def facts_field_id(user_email: str) -> str:
    """Helper to generate the field ID for a user's annotation summary field, where all the extracted facts are stored"""
    user_email = user_email.replace("@", "_at_").replace(".", "_dot_")
    return f"memory--{user_email}--summary"


if __name__ == "__main__":
    memory = NucliaMemory()
    # Create a new topic
    try:
        print(f"Storing new topic")
        print("=" * 50)
        memory.store(
            "Employees are entitled to 22 working days of paid vacation per year. "
            "Vacation must be requested at least 2 weeks in advance. "
            "A maximum of 10 consecutive days can be taken without director approval. "
            "Unused days cannot be carried over to the next year.",
            title="Vacation Policy",
            slug="vacation-policy",
        )
    except topicAlreadyExistsError:
        print("topic already exists, skipping creation.")

    print(f"Annotating topic")
    print("=" * 50)
    memory.annotate(
        topic="vacation-policy",
        text="Catalan employees have an exception allowing up to 60 consecutive days.",
    )

    # List topics
    print(f"List all topics")
    print("=" * 50)
    topics = memory.list()
    for topic in topics.items:
        print(f"- {topic.title} (id={topic.id}, slug={topic.slug})")

    # Get
    print(f"Get topic by slug")
    print("=" * 50)
    topic = memory.get(topic="vacation-policy")
    print(f"topic title: {topic.title}")
    print(f"topic summary: {topic.summary}")
    print("topic annotations:")
    for annotation in topic.annotations:
        print(f"- {annotation.text} (by {annotation.who} at {annotation.timestamp})")

    # Recall
    print(f"Recall answer for a question about the topic")
    print("=" * 50)
    question = "Can a Catalan employee take 15 consecutive vacation days?"
    result = memory.recall(question, topic="vacation-policy")
    print(f"Question: {question}")
    print()
    print(f"Answer: {result.answer}")
    print()
    print(f"Citations: {result.citations}")
