"""Pydantic schemas for all API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from chatfriends_retrieval.settings import settings


# ─────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int


def _resolve_tenant_id(tenant_id: str | None) -> str:
    resolved = str(tenant_id or settings.default_tenant_id or "").strip()
    if not resolved:
        raise ValueError("tenant_id is required")
    return resolved


def _resolve_assistant_id(assistant_id: str | None) -> str:
    resolved = str(assistant_id or "").strip()
    if not resolved:
        raise ValueError("assistant_id is required")
    return resolved


def _resolve_assistant_character_ids(
    assistant_id: str | None,
    character_id: str | None,
) -> tuple[str, str]:
    resolved = _resolve_assistant_id(assistant_id or character_id)
    return resolved, resolved


def _resolve_assistant_agent_ids(
    assistant_id: str | None,
    agent_id: str | None,
) -> tuple[str, str]:
    resolved = _resolve_assistant_id(assistant_id or agent_id)
    return resolved, resolved


class TenantCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    status: str = Field("draft/review", pattern=r"^(draft/review|active|paused|suspended)$")
    meta_json: dict[str, Any] | None = None


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    status: str | None = Field(None, pattern=r"^(draft/review|active|paused|suspended)$")
    meta_json: dict[str, Any] | None = None


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    description: str | None = None
    status: str
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantListResponse(PaginatedResponse):
    items: list[TenantResponse]


class AssistantResponse(BaseModel):
    tenant_id: str | None = None
    assistant_id: str
    name: str
    description: str | None = None
    status: str
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def normalize_scope(self) -> "AssistantResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        return self


class AssistantListResponse(PaginatedResponse):
    items: list[AssistantResponse]


class AssistantCreate(BaseModel):
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    status: str = Field("active", pattern=r"^(active|paused|suspended)$")
    meta_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "AssistantCreate":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        self.assistant_id = _resolve_assistant_id(self.assistant_id)
        return self


class AssistantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    status: str | None = Field(None, pattern=r"^(active|paused|suspended)$")
    meta_json: dict[str, Any] | None = None


class RegistrySyncResponse(BaseModel):
    tenant_id: str
    synced_count: int


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
    tenant_id: str | None = None
    assistant_id: str | None = None
    character_id: str
    user_id: str
    status: str
    meta_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def populate_assistant_id(self) -> "ConversationResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class ConversationListResponse(PaginatedResponse):
    items: list[ConversationResponse]


class ConversationUpsertRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=36)
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    character_id: str | None = Field(None, min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    status: str = Field("active", pattern=r"^(active|closed)$")
    meta_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "ConversationUpsertRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


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
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    agent_id: str | None = Field(None, min_length=1, max_length=64)
    version: str = Field("1.0", min_length=1, max_length=16)
    relation_state: RelationState = Field(default_factory=RelationState)
    interaction_stats: InteractionStats = Field(default_factory=InteractionStats)
    flags: RelationFlags = Field(default_factory=RelationFlags)
    meta: RelationMeta | None = None

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "UserAgentRelationUpsert":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, agent_id = _resolve_assistant_agent_ids(
            self.assistant_id,
            self.agent_id,
        )
        self.assistant_id = assistant_id
        self.agent_id = agent_id
        return self


class UserAgentRelationResponse(BaseModel):
    user_id: str
    tenant_id: str | None = None
    assistant_id: str | None = None
    agent_id: str
    version: str
    relation_state: RelationState
    interaction_stats: InteractionStats
    flags: RelationFlags
    meta: RelationMeta
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def populate_assistant_id(self) -> "UserAgentRelationResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, agent_id = _resolve_assistant_agent_ids(
            self.assistant_id,
            self.agent_id,
        )
        self.assistant_id = assistant_id
        self.agent_id = agent_id
        return self


class UserAgentRelationListResponse(PaginatedResponse):
    items: list[UserAgentRelationResponse]
# Messages
# ─────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    tenant_id: str | None = None
    assistant_id: str | None = None
    character_id: str
    user_id: str
    turn_index: int
    role: str
    content: str
    meta_json: dict[str, Any] | None = None
    ts: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def populate_assistant_id(self) -> "MessageResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class MessageListResponse(PaginatedResponse):
    items: list[MessageResponse]


class MessageCreateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(user|character|assistant|system|tool)$")
    content: str = Field(..., min_length=1)
    meta_json: dict[str, Any] | None = None
    ts: datetime | None = None


class MessageBatchCreateRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=36)
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    character_id: str | None = Field(None, min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    messages: list[MessageCreateRequest] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "MessageBatchCreateRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


# ─────────────────────────────────────────────────────────
# Snapshots
# ─────────────────────────────────────────────────────────


class SnapshotResponse(BaseModel):
    snapshot_id: str
    conversation_id: str
    tenant_id: str | None = None
    assistant_id: str | None = None
    character_id: str
    user_id: str
    turn_index: int
    summary: str
    state_json: dict[str, Any] | None = None
    ts: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def populate_assistant_id(self) -> "SnapshotResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class SnapshotListResponse(PaginatedResponse):
    items: list[SnapshotResponse]


# ─────────────────────────────────────────────────────────
# Query (retrieval)
# ─────────────────────────────────────────────────────────


class QueryFilters(BaseModel):
    tags: list[str] | None = None
    kinds: list[str] | None = None
    bucket: list[str] | None = None
    subject: str | None = None
    canonical: bool | None = None
    source: list[str] | None = None
    metadata: dict[str, Any] | None = None


class SparseTerm(BaseModel):
    term: str = Field(..., min_length=1, max_length=64)
    weight: float = Field(1.0, ge=0.0, le=1.0)


class SparseQueryPayload(BaseModel):
    terms: list[SparseTerm] = Field(default_factory=list, max_length=6)


class QueryRequest(BaseModel):
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    conversation_id: str | None = None
    query: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=100)
    scope: str = Field("private", pattern=r"^private$")
    filters: QueryFilters | None = None
    sparse_query: SparseQueryPayload | None = None
    return_text: bool = True

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "QueryRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        self.assistant_id = _resolve_assistant_id(self.assistant_id)
        return self


class ChunkResult(BaseModel):
    chunk_id: str
    doc_id: str
    score: float
    score_source: str = "dense"
    display_score: int = Field(0, ge=0, le=100)
    display_band: str = Field("faible", pattern=r"^(faible|moyen|fort|tres_fort)$")
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    query_id: str
    tenant_id: str
    assistant_id: str
    user_id: str
    top_k: int
    results: list[ChunkResult]
    hybrid_debug: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────
# Ingest
# ─────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    scope: str = Field("private", pattern=r"^private$")
    user_id: str | None = Field(None, min_length=1, max_length=64)
    doc_id: str = Field(..., min_length=1, max_length=64)
    doc_version: int = Field(1, ge=1)
    source_uri: str | None = Field(None, max_length=512)
    kind: str | None = Field(None, max_length=32)
    tags: list[str] | None = None
    bucket: str | None = Field(None, max_length=16)
    subject: str | None = Field(None, max_length=16)
    canonical: bool | None = None
    source: str | None = Field(None, max_length=16)
    metadata: dict[str, Any] | None = None
    lang: str | None = Field(None, max_length=16)
    data: Any
    chunk_max_length: int = Field(500, ge=100, le=5000)
    chunk_overlap: int = Field(50, ge=0, le=1000)

    @model_validator(mode="after")
    def validate_scope_user(self) -> "IngestRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        self.assistant_id = _resolve_assistant_id(self.assistant_id)
        if self.scope != "private":
            raise ValueError("scope must be private")
        if not self.user_id:
            raise ValueError("user_id is required for scope=private")
        if self.chunk_overlap >= self.chunk_max_length:
            raise ValueError("chunk_overlap must be less than chunk_max_length")
        return self


class IngestResponse(BaseModel):
    run_id: str
    tenant_id: str
    assistant_id: str
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
    tenant_id: str | None = None
    assistant_id: str | None = None
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

    @model_validator(mode="after")
    def populate_assistant_id(self) -> "MediaAssetResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class MediaAssetListResponse(PaginatedResponse):
    items: list[MediaAssetResponse]


class MediaAssetUpsertRequest(BaseModel):
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    character_id: str | None = Field(None, min_length=1, max_length=64)
    file_url: str = Field(..., min_length=1, max_length=255)
    title: str | None = Field(None, max_length=128)
    description: str | None = None
    required_relationship_level: int = Field(1, ge=1, le=5)
    content_intensity: str = Field("SOFT", pattern=r"^(SOFT|SENSUAL|ADULT|EXPLICIT)$")
    purchase_hearts_cost: int = Field(0, ge=0)
    relation_gain_bonus: int = Field(0, ge=0)
    is_purchasable: bool = False
    media_kind: str | None = Field(None, pattern=r"^(photo|video|audio)$")
    sort_order: int = Field(0, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "MediaAssetUpsertRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class MediaPickRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    character_id: str | None = Field(None, min_length=1, max_length=64)
    allow_recycle: bool = True
    max_relationship_level: int = Field(5, ge=1, le=5)
    max_content_intensity: str = Field(
        "EXPLICIT",
        pattern=r"^(SOFT|SENSUAL|ADULT|EXPLICIT)$",
    )
    media_kind: str | None = Field(None, pattern=r"^(photo|video|audio)$")

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "MediaPickRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class MediaPickResponse(BaseModel):
    item: MediaAssetResponse | None = None
    source: str | None = None  # unseen | recycled | null


class VectorDeleteRequest(BaseModel):
    tenant_id: str | None = Field(None, min_length=1, max_length=64)
    assistant_id: str | None = Field(None, min_length=1, max_length=64)
    character_id: str | None = Field(None, min_length=1, max_length=64)
    scope: str = Field("private", pattern=r"^(global|private)$")
    filters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_assistant_identifier(self) -> "VectorDeleteRequest":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


class VectorDeleteResponse(BaseModel):
    status: str
    tenant_id: str | None = None
    assistant_id: str | None = None
    character_id: str
    scope: str
    filters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_assistant_id(self) -> "VectorDeleteResponse":
        self.tenant_id = _resolve_tenant_id(self.tenant_id)
        assistant_id, character_id = _resolve_assistant_character_ids(
            self.assistant_id,
            self.character_id,
        )
        self.assistant_id = assistant_id
        self.character_id = character_id
        return self


