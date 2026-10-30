"""Common source representation plus source-specific input schemas."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.ids import make_document_id


class SourceType(str, Enum):
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    TICKET = "ticket"


def to_utc(value: datetime | None) -> datetime | None:
    """Naive datetimes are interpreted as UTC; aware ones are converted to UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeSource(BaseModel):
    """A registry entry (row of knowledge_sources)."""

    source_id: str
    source_type: SourceType
    name: str
    description: str
    authority_level: float = Field(ge=0, le=1)
    authority_basis: str | None = None


class TextSegment(BaseModel):
    """A unit that chunking must not split unless it exceeds the chunk size
    (a message, a ticket comment, a markdown section, a PDF page...)."""

    text: str
    label: str | None = None
    speaker: str | None = None
    timestamp: datetime | None = None

    _utc = field_validator("timestamp")(lambda v: to_utc(v))

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("segment text is empty")
        return v


class SourceRecord(BaseModel):
    """Normalized record shared by documents, conversations and tickets."""

    source_id: str
    source_type: SourceType
    original_record_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    description: str | None = None
    source_reference: str = Field(min_length=1)  # path/URI of the original record
    author: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    authority_level: float = Field(ge=0, le=1)
    authority_basis: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ingestion_timestamp: datetime = Field(default_factory=_utcnow)
    segments: list[TextSegment] = Field(default_factory=list, exclude=True)

    _utc = field_validator("created_at", "updated_at", "ingestion_timestamp")(lambda v: to_utc(v))

    @model_validator(mode="after")
    def _check_times(self) -> "SourceRecord":
        if self.created_at and self.updated_at and self.updated_at < self.created_at:
            raise ValueError("updated_at is earlier than created_at")
        return self

    @property
    def document_id(self) -> str:
        return make_document_id(self.source_type.value, self.original_record_id)


# ----- Conversation input -------------------------------------------------

class ConversationMessage(BaseModel):
    message_id: str | None = None
    speaker: str = Field(min_length=1)
    content: str
    timestamp: datetime

    _utc = field_validator("timestamp")(lambda v: to_utc(v))

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "speaker" not in d and "author" in d:
                d["speaker"] = d["author"]
            if "content" not in d and "text" in d:
                d["content"] = d["text"]
            return d
        return data

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message content is empty")
        return v


class ConversationInput(BaseModel):
    conversation_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    channel: str | None = None
    participants: list[str] = Field(default_factory=list)
    messages: list[ConversationMessage] = Field(min_length=1)
    status: str | None = None
    authority_level: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    _utc = field_validator("created_at", "updated_at")(lambda v: to_utc(v))

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            auth = d.get("authority_level")
            if isinstance(auth, str):
                if "authority_score" in d and isinstance(d["authority_score"], (int, float)):
                    d["authority_level"] = float(d["authority_score"])
                else:
                    d.setdefault("metadata", {})["raw_authority_level"] = auth
                    d["authority_level"] = None
            elif auth is None and "authority_score" in d and isinstance(d["authority_score"], (int, float)):
                d["authority_level"] = float(d["authority_score"])
            return d
        return data


# ----- Ticket input -------------------------------------------------------

class TicketComment(BaseModel):
    author: str = Field(min_length=1)
    timestamp: datetime
    content: str

    _utc = field_validator("timestamp")(lambda v: to_utc(v))

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("comment content is empty")
        return v


class TicketInput(BaseModel):
    ticket_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: str = Field(min_length=1)
    priority: str | None = None
    reporter: str | None = None
    assignee: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None
    labels: list[str] = Field(default_factory=list)
    comments: list[TicketComment] = Field(default_factory=list)
    authority_level: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _utc = field_validator("created_at", "updated_at", "resolved_at")(lambda v: to_utc(v))

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "resolution" not in d and "resolution_notes" in d:
                d["resolution"] = d["resolution_notes"]
            if "labels" not in d and "components" in d:
                d["labels"] = d["components"]
            auth = d.get("authority_level")
            if isinstance(auth, str):
                if "authority_score" in d and isinstance(d["authority_score"], (int, float)):
                    d["authority_level"] = float(d["authority_score"])
                else:
                    d.setdefault("metadata", {})["raw_authority_level"] = auth
                    d["authority_level"] = None
            elif auth is None and "authority_score" in d and isinstance(d["authority_score"], (int, float)):
                d["authority_level"] = float(d["authority_score"])
            return d
        return data

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")

    @model_validator(mode="after")
    def _check(self) -> "TicketInput":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at is earlier than created_at")
        return self


# ----- Chunks & reports ---------------------------------------------------

class Chunk(BaseModel):
    chunk_id: str
    point_id: str
    document_id: str
    source_id: str
    source_type: SourceType
    original_record_id: str
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    title: str
    source_reference: str
    status: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    authority_level: float
    authority_basis: str | None = None
    segment_labels: list[str] = Field(default_factory=list)
    speakers: list[str] = Field(default_factory=list)
    time_start: datetime | None = None
    time_end: datetime | None = None

    def embedding_text(self) -> str:
        """Text sent to the embedder: a short context header plus the chunk."""
        return f"{self.title} ({self.source_type.value})\n{self.text}"

    def to_payload(self) -> dict[str, Any]:
        def iso(d: datetime | None) -> str | None:
            return d.isoformat() if d else None

        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "original_record_id": self.original_record_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "title": self.title,
            "source_reference": self.source_reference,
            "status": self.status,
            "author": self.author,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "authority_level": self.authority_level,
            "authority_basis": self.authority_basis,
            "segment_labels": self.segment_labels,
            "speakers": self.speakers,
            "time_start": iso(self.time_start),
            "time_end": iso(self.time_end),
        }


class RecordFailure(BaseModel):
    reference: str
    error: str


class SourceReport(BaseModel):
    source_id: str
    source_type: SourceType
    job_id: str | None = None
    status: str = "running"
    total: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    chunks: int = 0
    failures: list[RecordFailure] = Field(default_factory=list)
