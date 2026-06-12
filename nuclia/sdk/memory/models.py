from __future__ import annotations

from datetime import datetime
from typing import Any

from nucliadb_models.conversation import Message
from pydantic import BaseModel


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
    reasoning: str | None = None
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
