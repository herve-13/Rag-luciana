"""CRUD repository functions for all entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, select, func as sa_func, text
from sqlalchemy.ext.asyncio import AsyncSession

from rag_luciana.db.models import (
    Character,
    Chunk,
    Conversation,
    GiftCatalog,
    IngestionRun,
    Message,
    Snapshot,
    User,
    UserAgentRelation,
    UserGiftHistory,
    UserWallet,
)

MEDIA_ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS media_assets (
  id BIGINT NOT NULL AUTO_INCREMENT,
  character_id VARCHAR(64) NOT NULL,
  file_url VARCHAR(255) NOT NULL,
  description TEXT NULL,
  required_relationship_level TINYINT UNSIGNED NOT NULL DEFAULT 1,
  content_intensity VARCHAR(16) NOT NULL DEFAULT 'SOFT',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_media_character_file (character_id, file_url),
  KEY idx_media_character_active (character_id, is_active, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

MEDIA_DELIVERY_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS media_delivery_history (
  id BIGINT NOT NULL AUTO_INCREMENT,
  user_id VARCHAR(64) NOT NULL,
  character_id VARCHAR(64) NOT NULL,
  media_asset_id BIGINT NOT NULL,
  delivered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_mdh_user_char_time (user_id, character_id, delivered_at),
  KEY idx_mdh_asset (media_asset_id),
  KEY idx_mdh_user_char_asset (user_id, character_id, media_asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


async def _ensure_media_assets_table(db: AsyncSession) -> None:
    await db.execute(text(MEDIA_ASSETS_DDL))
    # Backward-compatible column migration for existing installations.
    try:
        await db.execute(
            text(
                """
                ALTER TABLE media_assets
                ADD COLUMN required_relationship_level TINYINT UNSIGNED NOT NULL DEFAULT 1
                """
            )
        )
    except Exception:
        pass
    try:
        await db.execute(
            text(
                """
                ALTER TABLE media_assets
                ADD COLUMN content_intensity VARCHAR(16) NOT NULL DEFAULT 'SOFT'
                """
            )
        )
    except Exception:
        pass


async def _ensure_media_delivery_history_table(db: AsyncSession) -> None:
    await db.execute(text(MEDIA_DELIVERY_HISTORY_DDL))


# ─────────────────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────────────────


async def create_character(
    db: AsyncSession,
    *,
    character_id: str,
    name: str,
    description: str | None = None,
    meta_json: dict | None = None,
) -> Character:
    obj = Character(
        character_id=character_id,
        name=name,
        description=description,
        meta_json=meta_json,
    )
    db.add(obj)
    await db.flush()
    return obj


async def get_character(db: AsyncSession, character_id: str) -> Character | None:
    stmt = select(Character).where(
        Character.character_id == character_id,
        Character.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_characters(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Character], int]:
    base = select(Character).where(Character.deleted_at.is_(None))
    count_base = select(sa_func.count()).select_from(Character).where(Character.deleted_at.is_(None))
    if status:
        base = base.where(Character.status == status)
        count_base = count_base.where(Character.status == status)

    total = (await db.execute(count_base)).scalar() or 0
    items = (
        await db.execute(
            base.order_by(Character.updated_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return items, total


async def update_character(
    db: AsyncSession,
    character_id: str,
    **fields: object,
) -> Character | None:
    obj = await get_character(db, character_id)
    if obj is None:
        return None
    for key, value in fields.items():
        if hasattr(obj, key) and value is not None:
            setattr(obj, key, value)
    await db.flush()
    return obj


async def soft_delete_character(db: AsyncSession, character_id: str) -> bool:
    obj = await get_character(db, character_id)
    if obj is None:
        return False
    obj.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return True


# ─────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────


async def create_user(
    db: AsyncSession,
    *,
    user_id: str,
    display_name: str,
    meta_json: dict | None = None,
) -> User:
    obj = User(user_id=user_id, display_name=display_name, meta_json=meta_json)
    db.add(obj)
    await db.flush()
    return obj


async def get_user(db: AsyncSession, user_id: str) -> User | None:
    stmt = select(User).where(User.user_id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[User], int]:
    base = select(User).where(User.deleted_at.is_(None))
    count_base = select(sa_func.count()).select_from(User).where(User.deleted_at.is_(None))
    if status:
        base = base.where(User.status == status)
        count_base = count_base.where(User.status == status)

    total = (await db.execute(count_base)).scalar() or 0
    items = (
        await db.execute(
            base.order_by(User.updated_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return items, total


async def update_user(
    db: AsyncSession,
    user_id: str,
    **fields: object,
) -> User | None:
    obj = await get_user(db, user_id)
    if obj is None:
        return None
    for key, value in fields.items():
        if hasattr(obj, key) and value is not None:
            setattr(obj, key, value)
    await db.flush()
    return obj


async def soft_delete_user(db: AsyncSession, user_id: str) -> bool:
    obj = await get_user(db, user_id)
    if obj is None:
        return False
    obj.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return True


# ─────────────────────────────────────────────────────────

# -------------------------------------------------------------------------
# User-Agent Relations
# -------------------------------------------------------------------------


async def get_user_agent_relation(
    db: AsyncSession,
    *,
    user_id: str,
    character_id: str,
) -> UserAgentRelation | None:
    stmt = select(UserAgentRelation).where(
        UserAgentRelation.user_id == user_id,
        UserAgentRelation.character_id == character_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_user_agent_relations(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    character_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[UserAgentRelation], int]:
    filters = []
    if user_id:
        filters.append(UserAgentRelation.user_id == user_id)
    if character_id:
        filters.append(UserAgentRelation.character_id == character_id)

    count_stmt = (
        select(sa_func.count()).select_from(UserAgentRelation).where(*filters)
        if filters
        else select(sa_func.count()).select_from(UserAgentRelation)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = select(UserAgentRelation)
    if filters:
        items_stmt = items_stmt.where(*filters)
    items_stmt = (
        items_stmt.order_by(UserAgentRelation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = (await db.execute(items_stmt)).scalars().all()
    return items, total


async def upsert_user_agent_relation(
    db: AsyncSession,
    *,
    user_id: str,
    character_id: str,
    version: str,
    relation_state_json: dict,
    interaction_stats_json: dict,
    flags_json: dict,
    meta_json: dict,
) -> UserAgentRelation:
    obj = await get_user_agent_relation(
        db,
        user_id=user_id,
        character_id=character_id,
    )
    if obj is None:
        obj = UserAgentRelation(
            user_id=user_id,
            character_id=character_id,
            version=version,
            relation_state_json=relation_state_json,
            interaction_stats_json=interaction_stats_json,
            flags_json=flags_json,
            meta_json=meta_json,
        )
        db.add(obj)
    else:
        obj.version = version
        obj.relation_state_json = relation_state_json
        obj.interaction_stats_json = interaction_stats_json
        obj.flags_json = flags_json
        obj.meta_json = meta_json
    await db.flush()
    return obj
# Conversations
# ─────────────────────────────────────────────────────────


async def get_conversation(
    db: AsyncSession,
    conversation_id: str,
    character_id: str | None = None,
) -> Conversation | None:
    if character_id:
        stmt = select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.character_id == character_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    stmt = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
    )
    items = (await db.execute(stmt)).scalars().all()
    if not items:
        return None
    if len(items) > 1:
        raise ValueError(
            "Ambiguous conversation_id across multiple characters. "
            "Provide character_id."
        )
    return items[0]


async def list_conversations(
    db: AsyncSession,
    *,
    character_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    updated_after: datetime | None = None,
    updated_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Conversation], int]:
    base = select(Conversation)
    count_base = select(sa_func.count()).select_from(Conversation)

    for stmt_ref in (base, count_base):
        if character_id:
            stmt_ref = stmt_ref.where(Conversation.character_id == character_id)
        if user_id:
            stmt_ref = stmt_ref.where(Conversation.user_id == user_id)
        if status:
            stmt_ref = stmt_ref.where(Conversation.status == status)
        if updated_after:
            stmt_ref = stmt_ref.where(Conversation.updated_at >= updated_after)
        if updated_before:
            stmt_ref = stmt_ref.where(Conversation.updated_at <= updated_before)

    # Rebuild with filters applied
    filters = []
    if character_id:
        filters.append(Conversation.character_id == character_id)
    if user_id:
        filters.append(Conversation.user_id == user_id)
    if status:
        filters.append(Conversation.status == status)
    if updated_after:
        filters.append(Conversation.updated_at >= updated_after)
    if updated_before:
        filters.append(Conversation.updated_at <= updated_before)

    count_stmt = select(sa_func.count()).select_from(Conversation).where(*filters) if filters else select(sa_func.count()).select_from(Conversation)
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = select(Conversation)
    if filters:
        items_stmt = items_stmt.where(*filters)
    items_stmt = items_stmt.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    items = (await db.execute(items_stmt)).scalars().all()
    return items, total


async def set_conversation_status(
    db: AsyncSession,
    conversation_id: str,
    status: str,
    character_id: str | None = None,
) -> Conversation | None:
    obj = await get_conversation(db, conversation_id, character_id)
    if obj is None:
        return None
    obj.status = status
    await db.flush()
    return obj


async def upsert_conversation(
    db: AsyncSession,
    *,
    conversation_id: str,
    character_id: str,
    user_id: str,
    status: str = "active",
    meta_json: dict | None = None,
) -> Conversation:
    obj = await get_conversation(db, conversation_id, character_id)
    if obj is None:
        obj = Conversation(
            conversation_id=conversation_id,
            character_id=character_id,
            user_id=user_id,
            status=status,
            meta_json=meta_json,
        )
        db.add(obj)
    else:
        obj.user_id = user_id
        obj.status = status
        if meta_json is not None:
            obj.meta_json = meta_json
    await db.flush()
    return obj


async def purge_conversation(
    db: AsyncSession,
    conversation_id: str,
    character_id: str | None = None,
) -> dict | None:
    """Hard-delete conversation + messages + snapshots.

    Returns the conversation metadata (character_id, user_id) needed to
    purge the corresponding vectors in Qdrant, or None if not found.
    """
    conv = await get_conversation(db, conversation_id, character_id)
    if conv is None:
        return None

    info = {
        "character_id": conv.character_id,
        "user_id": conv.user_id,
        "conversation_id": conv.conversation_id,
    }

    # Delete messages
    await db.execute(
        delete(Message).where(
            Message.conversation_id == conversation_id,
            Message.character_id == conv.character_id,
        )
    )
    # Delete snapshots
    await db.execute(
        delete(Snapshot).where(
            Snapshot.conversation_id == conversation_id,
            Snapshot.character_id == conv.character_id,
        )
    )
    # Delete chunks tied to this conversation (private memory)
    await db.execute(
        delete(Chunk).where(
            Chunk.doc_id == f"conv_{conversation_id}",
            Chunk.character_id == conv.character_id,
        )
    )
    # Delete conversation
    await db.execute(
        delete(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.character_id == conv.character_id,
        )
    )

    await db.flush()
    return info


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Ingestion
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


async def create_ingestion_run(
    db: AsyncSession,
    *,
    run_id: str,
    character_id: str,
    scope: str,
    user_id: str | None,
    source_uri: str | None,
    docs_count: int = 1,
) -> IngestionRun:
    obj = IngestionRun(
        run_id=run_id,
        character_id=character_id,
        scope=scope,
        user_id=user_id,
        source_uri=source_uri,
        status="running",
        docs_count=docs_count,
        chunks_count=0,
    )
    db.add(obj)
    await db.flush()
    return obj


async def finish_ingestion_run(
    db: AsyncSession,
    *,
    run_id: str,
    character_id: str,
    status: str,
    chunks_count: int,
    error: str | None = None,
) -> IngestionRun | None:
    stmt = select(IngestionRun).where(
        IngestionRun.run_id == run_id,
        IngestionRun.character_id == character_id,
    )
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        return None
    obj.status = status
    obj.chunks_count = chunks_count
    obj.error = error
    obj.finished_at = datetime.now(timezone.utc)
    await db.flush()
    return obj


async def upsert_chunk(
    db: AsyncSession,
    *,
    chunk_id: str,
    character_id: str,
    scope: str,
    user_id: str | None,
    doc_id: str,
    doc_version: int,
    ordinal: int,
    json_path: str | None,
    kind: str | None,
    text: str,
    text_hash: str,
    lang: str | None,
    tags_json: list | None,
    meta_json: dict | None,
) -> Chunk:
    stmt = select(Chunk).where(
        Chunk.character_id == character_id,
        Chunk.chunk_id == chunk_id,
    )
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        obj = Chunk(
            chunk_id=chunk_id,
            character_id=character_id,
            scope=scope,
            user_id=user_id,
            doc_id=doc_id,
            doc_version=doc_version,
            ordinal=ordinal,
            json_path=json_path,
            kind=kind,
            text=text,
            text_hash=text_hash,
            lang=lang,
            tags_json=tags_json,
            meta_json=meta_json,
        )
        db.add(obj)
    else:
        obj.scope = scope
        obj.user_id = user_id
        obj.doc_id = doc_id
        obj.doc_version = doc_version
        obj.ordinal = ordinal
        obj.json_path = json_path
        obj.kind = kind
        obj.text = text
        obj.text_hash = text_hash
        obj.lang = lang
        obj.tags_json = tags_json
        obj.meta_json = meta_json
    await db.flush()
    return obj


# ─────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────


async def list_messages(
    db: AsyncSession,
    conversation_id: str,
    character_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Message], int]:
    count_stmt = (
        select(sa_func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.character_id == character_id,
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.character_id == character_id,
        )
        .order_by(Message.turn_index.asc())
        .limit(limit)
        .offset(offset)
    )
    items = (await db.execute(items_stmt)).scalars().all()
    return items, total


async def get_last_turn_index(
    db: AsyncSession,
    *,
    conversation_id: str,
    character_id: str,
) -> int:
    stmt = (
        select(sa_func.max(Message.turn_index))
        .where(
            Message.conversation_id == conversation_id,
            Message.character_id == character_id,
        )
    )
    value = (await db.execute(stmt)).scalar()
    return int(value) if value is not None else -1


async def create_message(
    db: AsyncSession,
    *,
    message_id: str,
    conversation_id: str,
    character_id: str,
    user_id: str,
    turn_index: int,
    role: str,
    content: str,
    meta_json: dict | None = None,
    ts: datetime | None = None,
) -> Message:
    obj = Message(
        message_id=message_id,
        conversation_id=conversation_id,
        character_id=character_id,
        user_id=user_id,
        turn_index=turn_index,
        role=role,
        content=content,
        meta_json=meta_json,
        ts=ts or datetime.now(timezone.utc),
    )
    db.add(obj)
    await db.flush()
    return obj


# ─────────────────────────────────────────────────────────
# Snapshots
# ─────────────────────────────────────────────────────────


async def list_snapshots(
    db: AsyncSession,
    conversation_id: str,
    character_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Snapshot], int]:
    count_stmt = (
        select(sa_func.count())
        .select_from(Snapshot)
        .where(
            Snapshot.conversation_id == conversation_id,
            Snapshot.character_id == character_id,
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(Snapshot)
        .where(
            Snapshot.conversation_id == conversation_id,
            Snapshot.character_id == character_id,
        )
        .order_by(Snapshot.turn_index.asc())
        .limit(limit)
        .offset(offset)
    )
    items = (await db.execute(items_stmt)).scalars().all()
    return items, total


# ─────────────────────────────────────────────────────────
# Gift Catalog
# ─────────────────────────────────────────────────────────


async def list_gift_catalog(
    db: AsyncSession,
    *,
    category: str | None = None,
    active_only: bool = True,
) -> Sequence[GiftCatalog]:
    stmt = select(GiftCatalog)
    if active_only:
        stmt = stmt.where(GiftCatalog.is_active == True)  # noqa: E712
    if category:
        stmt = stmt.where(GiftCatalog.category == category)
    stmt = stmt.order_by(GiftCatalog.hearts_cost.asc())
    return (await db.execute(stmt)).scalars().all()


# ─────────────────────────────────────────────────────────
# User Wallets
# ─────────────────────────────────────────────────────────


async def get_or_create_wallet(
    db: AsyncSession,
    user_id: str,
) -> UserWallet:
    """Return existing wallet or auto-create one with 0 hearts."""
    stmt = select(UserWallet).where(UserWallet.user_id == user_id)
    wallet = (await db.execute(stmt)).scalar_one_or_none()
    if wallet is None:
        wallet = UserWallet(user_id=user_id, hearts_balance=0, total_earned=0, total_spent=0)
        db.add(wallet)
        await db.flush()
    return wallet


async def credit_hearts(
    db: AsyncSession,
    user_id: str,
    amount: int,
) -> UserWallet:
    """Credit hearts to a user's wallet (auto-creates if needed)."""
    wallet = await get_or_create_wallet(db, user_id)
    wallet.hearts_balance += amount
    wallet.total_earned += amount
    await db.flush()
    return wallet


# ─────────────────────────────────────────────────────────
# Gift Purchase (transactional, FOR UPDATE)
# ─────────────────────────────────────────────────────────


async def purchase_gift(
    db: AsyncSession,
    *,
    user_id: str,
    character_id: str,
    gift_id: int,
) -> dict:
    """
    Atomic gift purchase:
      1. Lock wallet row (FOR UPDATE)
      2. Validate gift exists, is active, and user has enough hearts
      3. Debit wallet
      4. Insert history
      5. Return result with bond_bonus for the caller to update trust

    Returns dict with keys: ok, bond_bonus, hearts_remaining, error
    """
    # 1. Lock wallet
    stmt = select(UserWallet).where(UserWallet.user_id == user_id).with_for_update()
    wallet = (await db.execute(stmt)).scalar_one_or_none()
    if wallet is None:
        wallet = UserWallet(user_id=user_id, hearts_balance=0, total_earned=0, total_spent=0)
        db.add(wallet)
        await db.flush()
        # Re-lock
        stmt = select(UserWallet).where(UserWallet.user_id == user_id).with_for_update()
        wallet = (await db.execute(stmt)).scalar_one()

    # 2. Validate gift
    gift_stmt = select(GiftCatalog).where(
        GiftCatalog.id == gift_id,
        GiftCatalog.is_active == True,  # noqa: E712
    )
    gift = (await db.execute(gift_stmt)).scalar_one_or_none()
    if gift is None:
        return {"ok": False, "error": "gift_not_found", "bond_bonus": 0, "hearts_remaining": wallet.hearts_balance}

    # 3. Check balance
    if wallet.hearts_balance < gift.hearts_cost:
        return {
            "ok": False,
            "error": "insufficient_hearts",
            "bond_bonus": 0,
            "hearts_remaining": wallet.hearts_balance,
            "hearts_cost": gift.hearts_cost,
        }

    # 4. Debit
    wallet.hearts_balance -= gift.hearts_cost
    wallet.total_spent += gift.hearts_cost

    # 5. Insert history
    history = UserGiftHistory(
        user_id=user_id,
        character_id=character_id,
        gift_id=gift_id,
    )
    db.add(history)
    await db.flush()

    return {
        "ok": True,
        "bond_bonus": gift.bond_bonus,
        "hearts_remaining": wallet.hearts_balance,
        "gift_name": gift.name,
        "category": gift.category,
        "error": None,
    }


# ─────────────────────────────────────────────────────────
# Gift History
# ─────────────────────────────────────────────────────────


async def list_gift_history(
    db: AsyncSession,
    *,
    user_id: str,
    character_id: str | None = None,
    limit: int = 50,
) -> Sequence[UserGiftHistory]:
    stmt = select(UserGiftHistory).where(UserGiftHistory.user_id == user_id)
    if character_id:
        stmt = stmt.where(UserGiftHistory.character_id == character_id)
    stmt = stmt.order_by(UserGiftHistory.purchased_at.desc()).limit(limit)
    return (await db.execute(stmt)).scalars().all()


async def list_media_assets(
    db: AsyncSession,
    *,
    character_id: str,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List media assets from MariaDB table media_assets."""
    await _ensure_media_assets_table(db)
    where = "WHERE character_id = :character_id"
    if active_only:
        where += " AND is_active = 1"

    count_sql = text(f"SELECT COUNT(*) AS total FROM media_assets {where}")
    total = int(
        (await db.execute(count_sql, {"character_id": character_id})).scalar() or 0
    )

    list_sql = text(
        f"""
        SELECT id, character_id, file_url, description, required_relationship_level, content_intensity, is_active, created_at, updated_at
        FROM media_assets
        {where}
        ORDER BY id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await db.execute(
            list_sql,
            {
                "character_id": character_id,
                "limit": int(limit),
                "offset": int(offset),
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows], total


async def upsert_media_asset(
    db: AsyncSession,
    *,
    character_id: str,
    file_url: str,
    description: str | None = None,
    required_relationship_level: int = 1,
    content_intensity: str = "SOFT",
    is_active: bool = True,
) -> dict:
    await _ensure_media_assets_table(db)
    normalized_intensity = (content_intensity or "SOFT").strip().upper()
    if normalized_intensity not in {"SOFT", "SENSUAL", "ADULT", "EXPLICIT"}:
        normalized_intensity = "SOFT"
    level = max(1, min(5, int(required_relationship_level or 1)))

    upsert_sql = text(
        """
        INSERT INTO media_assets (
          character_id, file_url, description, required_relationship_level, content_intensity, is_active
        )
        VALUES (
          :character_id, :file_url, :description, :required_relationship_level, :content_intensity, :is_active
        )
        ON DUPLICATE KEY UPDATE
          description = VALUES(description),
          required_relationship_level = VALUES(required_relationship_level),
          content_intensity = VALUES(content_intensity),
          is_active = VALUES(is_active),
          updated_at = CURRENT_TIMESTAMP
        """
    )
    await db.execute(
        upsert_sql,
        {
            "character_id": character_id,
            "file_url": file_url,
            "description": description,
            "required_relationship_level": level,
            "content_intensity": normalized_intensity,
            "is_active": 1 if is_active else 0,
        },
    )

    get_sql = text(
        """
        SELECT id, character_id, file_url, description, required_relationship_level, content_intensity, is_active, created_at, updated_at
        FROM media_assets
        WHERE character_id = :character_id AND file_url = :file_url
        LIMIT 1
        """
    )
    row = (
        await db.execute(
            get_sql,
            {"character_id": character_id, "file_url": file_url},
        )
    ).mappings().first()
    return dict(row) if row else {}


async def delete_media_asset(
    db: AsyncSession,
    *,
    asset_id: int,
) -> dict | None:
    await _ensure_media_assets_table(db)

    get_sql = text(
        """
        SELECT id, character_id, file_url, description, required_relationship_level, content_intensity, is_active, created_at, updated_at
        FROM media_assets
        WHERE id = :asset_id
        LIMIT 1
        """
    )
    row = (
        await db.execute(
            get_sql,
            {"asset_id": int(asset_id)},
        )
    ).mappings().first()
    if not row:
        return None

    await _ensure_media_delivery_history_table(db)
    await db.execute(
        text("DELETE FROM media_delivery_history WHERE media_asset_id = :asset_id"),
        {"asset_id": int(asset_id)},
    )
    delete_sql = text("DELETE FROM media_assets WHERE id = :asset_id")
    await db.execute(delete_sql, {"asset_id": int(asset_id)})
    return dict(row)


async def pick_media_asset_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    character_id: str,
    allow_recycle: bool = True,
    max_relationship_level: int = 5,
    max_content_intensity: str = "EXPLICIT",
) -> tuple[dict | None, str | None]:
    """
    Pick media for a user, preferring unseen assets.

    Returns:
      (asset, source) where source is "unseen" or "recycled", or (None, None).
    """
    await _ensure_media_assets_table(db)
    await _ensure_media_delivery_history_table(db)
    max_level = max(1, min(5, int(max_relationship_level or 5)))
    max_intensity = (max_content_intensity or "EXPLICIT").strip().upper()
    if max_intensity not in {"SOFT", "SENSUAL", "ADULT", "EXPLICIT"}:
        max_intensity = "EXPLICIT"

    intensity_rank_sql = """
      CASE m.content_intensity
        WHEN 'SOFT' THEN 1
        WHEN 'SENSUAL' THEN 2
        WHEN 'ADULT' THEN 3
        WHEN 'EXPLICIT' THEN 4
        ELSE 1
      END
    """
    max_intensity_rank_sql = """
      CASE :max_content_intensity
        WHEN 'SOFT' THEN 1
        WHEN 'SENSUAL' THEN 2
        WHEN 'ADULT' THEN 3
        WHEN 'EXPLICIT' THEN 4
        ELSE 4
      END
    """

    unseen_sql = text(
        f"""
        SELECT m.id, m.character_id, m.file_url, m.description, m.required_relationship_level, m.content_intensity, m.is_active, m.created_at, m.updated_at
        FROM media_assets m
        WHERE m.character_id = :character_id
          AND m.is_active = 1
          AND m.required_relationship_level <= :max_relationship_level
          AND ({intensity_rank_sql}) <= ({max_intensity_rank_sql})
          AND NOT EXISTS (
            SELECT 1
            FROM media_delivery_history h
            WHERE h.media_asset_id = m.id
              AND h.user_id = :user_id
              AND h.character_id = :character_id
          )
        ORDER BY RAND()
        LIMIT 1
        """
    )
    row = (
        await db.execute(
            unseen_sql,
            {
                "user_id": user_id,
                "character_id": character_id,
                "max_relationship_level": max_level,
                "max_content_intensity": max_intensity,
            },
        )
    ).mappings().first()

    source: str | None = None
    if row:
        source = "unseen"
    elif allow_recycle:
        recycled_sql = text(
            f"""
            SELECT m.id, m.character_id, m.file_url, m.description, m.required_relationship_level, m.content_intensity, m.is_active, m.created_at, m.updated_at
            FROM media_assets m
            JOIN media_delivery_history h
              ON h.media_asset_id = m.id
             AND h.user_id = :user_id
             AND h.character_id = :character_id
            WHERE m.character_id = :character_id
              AND m.is_active = 1
              AND m.required_relationship_level <= :max_relationship_level
              AND ({intensity_rank_sql}) <= ({max_intensity_rank_sql})
            ORDER BY h.delivered_at ASC
            LIMIT 1
            """
        )
        row = (
            await db.execute(
                recycled_sql,
                {
                    "user_id": user_id,
                    "character_id": character_id,
                    "max_relationship_level": max_level,
                    "max_content_intensity": max_intensity,
                },
            )
        ).mappings().first()
        if row:
            source = "recycled"

    if not row:
        return None, None

    await db.execute(
        text(
            """
            INSERT INTO media_delivery_history (user_id, character_id, media_asset_id)
            VALUES (:user_id, :character_id, :media_asset_id)
            """
        ),
        {
            "user_id": user_id,
            "character_id": character_id,
            "media_asset_id": int(row["id"]),
        },
    )
    return dict(row), source
