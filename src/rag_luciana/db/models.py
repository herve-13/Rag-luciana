"""SQLAlchemy ORM models for RAG Luciana."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# ─────────────────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────────────────


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_char_status", "status", "updated_at"),
    )


# ─────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_user_status", "status", "updated_at"),
    )


# ─────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────


# -------------------------------------------------------------------------
# User-Agent Relation State
# -------------------------------------------------------------------------


class UserAgentRelation(Base):
    __tablename__ = "user_agent_relations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")

    relation_state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    interaction_stats_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    flags_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "character_id", name="uq_user_agent_relation"),
        Index("idx_uar_user", "user_id", "updated_at"),
        Index("idx_uar_character", "character_id", "updated_at"),
    )

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("character_id", "conversation_id", name="uq_conv"),
        Index("idx_conv_user_char", "user_id", "character_id", "updated_at"),
        Index("idx_conv_char", "character_id", "updated_at"),
        Index("idx_conv_status", "status", "updated_at"),
    )


# ─────────────────────────────────────────────────────────
# Messages (append-only)
# ─────────────────────────────────────────────────────────


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / character / system / tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "character_id", "conversation_id", "turn_index", name="uq_turn"
        ),
        Index("idx_msg_conv_ts", "character_id", "conversation_id", "ts"),
        Index("idx_msg_user", "user_id", "character_id", "ts"),
    )


# ─────────────────────────────────────────────────────────
# Snapshots (summaries / state)
# ─────────────────────────────────────────────────────────


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_snap_conv_turn", "character_id", "conversation_id", "turn_index"),
        Index("idx_snap_user_char", "user_id", "character_id", "ts"),
    )


# ─────────────────────────────────────────────────────────
# Chunks (text + metadata for vector rebuild)
# ─────────────────────────────────────────────────────────


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)

    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # global / private
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    doc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tags_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("character_id", "chunk_id", name="uq_chunk"),
        Index("idx_chunk_doc", "character_id", "doc_id", "doc_version"),
        Index("idx_chunk_scope", "character_id", "scope", "created_at"),
        Index("idx_chunk_private", "character_id", "user_id", "created_at"),
        Index("idx_chunk_text_hash", "character_id", "text_hash"),
    )


# ─────────────────────────────────────────────────────────
# Ingestion Runs (tracking)
# ─────────────────────────────────────────────────────────


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)

    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("character_id", "run_id", name="uq_run"),
        Index("idx_run_status", "character_id", "status"),
        Index("idx_run_started", "character_id", "started_at"),
        Index("idx_run_private", "character_id", "user_id", "started_at"),
    )


# ─────────────────────────────────────────────────────────
# Gift Catalog
# ─────────────────────────────────────────────────────────


class GiftCatalog(Base):
    __tablename__ = "gift_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hearts_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    bond_bonus: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="cute"
    )  # cute, romantic, intimate, luxury
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unlock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_gift_category", "category", "is_active"),
    )


# ─────────────────────────────────────────────────────────
# User Wallets (hearts economy)
# ─────────────────────────────────────────────────────────


class UserWallet(Base):
    __tablename__ = "user_wallets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hearts_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ─────────────────────────────────────────────────────────
# User Gift History
# ─────────────────────────────────────────────────────────


class UserGiftHistory(Base):
    __tablename__ = "user_gift_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    character_id: Mapped[str] = mapped_column(String(64), nullable=False)
    gift_id: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_gift_history_user", "user_id", "purchased_at"),
        Index("idx_gift_history_user_char", "user_id", "character_id", "purchased_at"),
    )

