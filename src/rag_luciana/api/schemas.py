"""Pydantic schemas for all API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int


# ─────────────────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────────────────


class CharacterCreate(BaseModel):
    character_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    meta_json: dict[str, Any] | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    status: str | None = Field(None, pattern=r"^(active|inactive)$")
    meta_json: dict[str, Any] | None = None


class CharacterResponse(BaseModel):
    character_id: str
    name: str
    description: str | None = None
    status: str
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CharacterListResponse(PaginatedResponse):
    items: list[CharacterResponse]


# ─────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    meta_json: dict[str, Any] | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=128)
    status: str | None = Field(None, pattern=r"^(active|inactive)$")
    meta_json: dict[str, Any] | None = None


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    status: str
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(PaginatedResponse):
    items: list[UserResponse]


# ─────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────


class ConversationResponse(BaseModel):
    conversation_id: str
    character_id: str
    user_id: str
    status: str
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(PaginatedResponse):
    items: list[ConversationResponse]


class ConversationUpsertRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=36)
    character_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    status: str = Field("active", pattern=r"^(active|closed)$")
    meta_json: dict[str, Any] | None = None


# ─────────────────────────────────────────────────────────

# -------------------------------------------------------------------------
# User-Agent relation state (evolutive contract)
# -------------------------------------------------------------------------


class RelationState(BaseModel):
    familiarity: float = Field(0.10, ge=0.0, le=1.0)
    trust: float = Field(0.10, ge=0.0, le=1.0)
    attachment: float = Field(0.05, ge=0.0, le=1.0)
    tension: float = Field(0.00, ge=0.0, le=1.0)


class InteractionStats(BaseModel):
    total_messages: int = Field(0, ge=0)
    last_interaction: datetime | None = None


class RelationFlags(BaseModel):
    favorite: bool = False
    blocked: bool = False


class RelationMeta(BaseModel):
    created_at: datetime
    last_updated: datetime


class UserAgentRelationUpsert(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    agent_id: str = Field(..., min_length=1, max_length=64)
    version: str = Field("1.0", min_length=1, max_length=16)
    relation_state: RelationState = Field(default_factory=RelationState)
    interaction_stats: InteractionStats = Field(default_factory=InteractionStats)
    flags: RelationFlags = Field(default_factory=RelationFlags)
    meta: RelationMeta | None = None


class UserAgentRelationResponse(BaseModel):
    user_id: str
    agent_id: str
    version: str
    relation_state: RelationState
    interaction_stats: InteractionStats
    flags: RelationFlags
    meta: RelationMeta
    created_at: datetime
    updated_at: datetime


class UserAgentRelationListResponse(PaginatedResponse):
    items: list[UserAgentRelationResponse]
# Messages
# ─────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    character_id: str
    user_id: str
    turn_index: int
    role: str
    content: str
    meta_json: dict[str, Any] | None = None
    ts: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(PaginatedResponse):
    items: list[MessageResponse]


class MessageCreateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(user|character|assistant|system|tool)$")
    content: str = Field(..., min_length=1)
    meta_json: dict[str, Any] | None = None
    ts: datetime | None = None


class MessageBatchCreateRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=36)
    character_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    messages: list[MessageCreateRequest] = Field(default_factory=list, min_length=1)


# ─────────────────────────────────────────────────────────
# Snapshots
# ─────────────────────────────────────────────────────────


class SnapshotResponse(BaseModel):
    snapshot_id: str
    conversation_id: str
    character_id: str
    user_id: str
    turn_index: int
    summary: str
    state_json: dict[str, Any] | None = None
    ts: datetime

    model_config = {"from_attributes": True}


class SnapshotListResponse(PaginatedResponse):
    items: list[SnapshotResponse]


# ─────────────────────────────────────────────────────────
# Query (retrieval)
# ─────────────────────────────────────────────────────────


class QueryFilters(BaseModel):
    tags: list[str] | None = None
    kinds: list[str] | None = None
    metadata: dict[str, Any] | None = None


class SparseTerm(BaseModel):
    term: str = Field(..., min_length=1, max_length=64)
    weight: float = Field(1.0, ge=0.0, le=1.0)


class SparseQueryPayload(BaseModel):
    terms: list[SparseTerm] = Field(default_factory=list, max_length=6)


class QueryRequest(BaseModel):
    character_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    conversation_id: str | None = None
    query: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=100)
    scope: str = Field("private", pattern=r"^private$")
    filters: QueryFilters | None = None
    sparse_query: SparseQueryPayload | None = None
    return_text: bool = True


class ChunkResult(BaseModel):
    chunk_id: str
    doc_id: str
    score: float
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    query_id: str
    character_id: str
    user_id: str
    top_k: int
    results: list[ChunkResult]
    hybrid_debug: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────
# Ingest
# ─────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    character_id: str = Field(..., min_length=1, max_length=64)
    scope: str = Field("private", pattern=r"^private$")
    user_id: str | None = Field(None, min_length=1, max_length=64)
    doc_id: str = Field(..., min_length=1, max_length=64)
    doc_version: int = Field(1, ge=1)
    source_uri: str | None = Field(None, max_length=512)
    kind: str | None = Field(None, max_length=32)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    lang: str | None = Field(None, max_length=16)
    data: Any
    chunk_max_length: int = Field(500, ge=100, le=5000)
    chunk_overlap: int = Field(50, ge=0, le=1000)

    @model_validator(mode="after")
    def validate_scope_user(self) -> "IngestRequest":
        if self.scope != "private":
            raise ValueError("scope must be private")
        if not self.user_id:
            raise ValueError("user_id is required for scope=private")
        if self.chunk_overlap >= self.chunk_max_length:
            raise ValueError("chunk_overlap must be less than chunk_max_length")
        return self


class IngestResponse(BaseModel):
    run_id: str
    character_id: str
    scope: str
    user_id: str | None = None
    doc_id: str
    doc_version: int
    status: str
    chunks_count: int


# ─────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str  # "ok"


class ReadyResponse(BaseModel):
    status: str  # "ready" | "not_ready"
    checks: dict[str, bool]  # {"mariadb": true, "qdrant": true, "ollama": true}


class MediaAssetResponse(BaseModel):
    id: int
    character_id: str
    file_url: str
    title: str | None = None
    description: str | None = None
    required_relationship_level: int = 1
    content_intensity: str = "SOFT"
    purchase_hearts_cost: int = 0
    relation_gain_bonus: int = 0
    is_purchasable: bool = False
    media_kind: str | None = None
    sort_order: int = 0
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MediaAssetListResponse(PaginatedResponse):
    items: list[MediaAssetResponse]


class MediaAssetUpsertRequest(BaseModel):
    character_id: str = Field(..., min_length=1, max_length=64)
    file_url: str = Field(..., min_length=1, max_length=255)
    title: str | None = Field(None, max_length=128)
    description: str | None = None
    required_relationship_level: int = Field(1, ge=1, le=5)
    content_intensity: str = Field("SOFT", pattern=r"^(SOFT|SENSUAL|ADULT|EXPLICIT)$")
    purchase_hearts_cost: int = Field(0, ge=0)
    relation_gain_bonus: int = Field(0, ge=0)
    is_purchasable: bool = False
    media_kind: str | None = Field(None, pattern=r"^(photo|video)$")
    sort_order: int = Field(0, ge=0)
    is_active: bool = True


class MediaPickRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    character_id: str = Field(..., min_length=1, max_length=64)
    allow_recycle: bool = True
    max_relationship_level: int = Field(5, ge=1, le=5)
    max_content_intensity: str = Field(
        "EXPLICIT",
        pattern=r"^(SOFT|SENSUAL|ADULT|EXPLICIT)$",
    )


class MediaPickResponse(BaseModel):
    item: MediaAssetResponse | None = None
    source: str | None = None  # unseen | recycled | null


class VectorDeleteRequest(BaseModel):
    character_id: str = Field(..., min_length=1, max_length=64)
    scope: str = Field("private", pattern=r"^(global|private)$")
    filters: dict[str, Any] = Field(default_factory=dict)


class VectorDeleteResponse(BaseModel):
    status: str
    character_id: str
    scope: str
    filters: dict[str, Any] = Field(default_factory=dict)

