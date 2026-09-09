from datetime import datetime
from typing import Any

from nucliadb_models.conversation import (
    Message,
)
from pydantic import BaseModel


class Resource(BaseModel):
    """A discrete unit of memory stored in the memory.
    Corresponds to a single resource in a Nuclia Knowledge Box.
    """

    id: str
    slug: str
    title: str
    summary: str | None = None
    status: str


class ResourcePage(BaseModel):
    """A paginated listing of resources."""

    items: list[Resource]
    total: int
    has_more: bool


# Keeping the `Topic` alias for backwards compatibility, but it is now deprecated in favor of `Resource`.
Topic = Resource
TopicPage = ResourcePage


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
    """A single entry message attached to a resource."""

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


class ContextBlock(BaseModel):
    id: str
    text: str
    entry: Entry | None = None
    fact: Fact | None = None


class RelevantContextBlock(ContextBlock):
    score: float


class AskResult(BaseModel):
    """Result of a generative `recall()` call."""

    answer: str
    citations: dict[str, RelevantContextBlock]
