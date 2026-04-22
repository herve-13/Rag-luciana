"""CRUD repository functions for all entities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select, func as sa_func, text
from sqlalchemy.ext.asyncio import AsyncSession

from chatfriends_retrieval.db.models import (
    Assistant,
    Character,
    Chunk,
    Conversation,
    GiftCatalog,
    IngestionRun,
    Message,
    Snapshot,
    Tenant,
    User,
    UserAgentRelation,
    UserGiftHistory,
    UserWallet,
)
from chatfriends_retrieval.settings import settings

DEFAULT_TENANT_ID = str(settings.default_tenant_id or "herve")
DEFAULT_TENANT_SQL = DEFAULT_TENANT_ID.replace("'", "''")

TENANTS_DDL = f"""
CREATE TABLE IF NOT EXISTS tenants (
  id BIGINT NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  label VARCHAR(128) NOT NULL DEFAULT 'Client',
  name VARCHAR(128) NOT NULL,
  description TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  meta_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tenant_id (tenant_id),
  KEY idx_tenant_status (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

ASSISTANTS_DDL = f"""
CREATE TABLE IF NOT EXISTS assistants (
  id BIGINT NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}',
  assistant_id VARCHAR(64) NOT NULL,
  character_id VARCHAR(64) NULL,
  label VARCHAR(128) NOT NULL DEFAULT 'Assistant',
  name VARCHAR(128) NOT NULL,
  description TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  meta_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tenant_assistant (tenant_id, assistant_id),
  UNIQUE KEY uq_assistant_character (character_id),
  KEY idx_assistant_tenant_status (tenant_id, status, updated_at),
  KEY idx_assistant_character (character_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

MEDIA_ASSETS_DDL = f"""
CREATE TABLE IF NOT EXISTS media_assets (
  id BIGINT NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}',
  character_id VARCHAR(64) NOT NULL,
  file_url VARCHAR(255) NOT NULL,
  title VARCHAR(128) NULL,
  description TEXT NULL,
  required_relationship_level TINYINT UNSIGNED NOT NULL DEFAULT 1,
  content_intensity VARCHAR(16) NOT NULL DEFAULT 'SOFT',
  purchase_hearts_cost INT NOT NULL DEFAULT 0,
  relation_gain_bonus INT NOT NULL DEFAULT 0,
  is_purchasable TINYINT(1) NOT NULL DEFAULT 0,
  media_kind VARCHAR(16) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_media_tenant_character_file (tenant_id, character_id, file_url),
  KEY idx_media_tenant_character_active (tenant_id, character_id, is_active, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

MEDIA_DELIVERY_HISTORY_DDL = f"""
CREATE TABLE IF NOT EXISTS media_delivery_history (
  id BIGINT NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}',
  user_id VARCHAR(64) NOT NULL,
  character_id VARCHAR(64) NOT NULL,
  media_asset_id BIGINT NOT NULL,
  delivered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_mdh_tenant_user_char_time (tenant_id, user_id, character_id, delivered_at),
  KEY idx_mdh_asset (media_asset_id),
  KEY idx_mdh_tenant_user_char_asset (tenant_id, user_id, character_id, media_asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def _resolve_tenant_id(tenant_id: str | None = None) -> str:
    resolved = str(tenant_id or DEFAULT_TENANT_ID or "").strip()
    if not resolved:
        raise ValueError("tenant_id is required")
    return resolved


def _default_tenant_name(tenant_id: str) -> str:
    compact = str(tenant_id or "").strip()
    if not compact:
        return str(settings.default_tenant_label or "").strip() or "Client Hervé"
    if compact == DEFAULT_TENANT_ID:
        return str(settings.default_tenant_label or "").strip() or "Client Hervé"
    return compact.replace("_", " ").replace("-", " ").title()


def _default_assistant_name(assistant_id: str) -> str:
    compact = str(assistant_id or "").strip()
    if not compact:
        return "Assistant"
    return compact.replace("_", " ").replace("-", " ").title()


async def _safe_execute(executor: Any, sql: str) -> None:
    try:
        await executor.execute(text(sql))
    except Exception:
        pass


async def _ensure_tenants_table(executor: Any) -> None:
    await executor.execute(text(TENANTS_DDL))
    for ddl in (
        f"ALTER TABLE tenants ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}'",
        "ALTER TABLE tenants ADD COLUMN label VARCHAR(128) NOT NULL DEFAULT 'Client'",
        "ALTER TABLE tenants ADD COLUMN name VARCHAR(128) NOT NULL DEFAULT 'Default Tenant'",
        "ALTER TABLE tenants ADD COLUMN description TEXT NULL",
        "ALTER TABLE tenants ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active'",
        "ALTER TABLE tenants ADD COLUMN meta_json JSON NULL",
        "ALTER TABLE tenants ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE tenants ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "ALTER TABLE tenants ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL",
        "ALTER TABLE tenants ADD UNIQUE KEY uq_tenant_id (tenant_id)",
        "ALTER TABLE tenants ADD INDEX idx_tenant_status (status, updated_at)",
    ):
        await _safe_execute(executor, ddl)


async def _ensure_assistants_table(executor: Any) -> None:
    await executor.execute(text(ASSISTANTS_DDL))
    for ddl in (
        f"ALTER TABLE assistants ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}'",
        "ALTER TABLE assistants ADD COLUMN assistant_id VARCHAR(64) NOT NULL DEFAULT ''",
        "ALTER TABLE assistants ADD COLUMN character_id VARCHAR(64) NULL",
        "ALTER TABLE assistants ADD COLUMN label VARCHAR(128) NOT NULL DEFAULT 'Assistant'",
        "ALTER TABLE assistants ADD COLUMN name VARCHAR(128) NOT NULL DEFAULT 'Assistant'",
        "ALTER TABLE assistants ADD COLUMN description TEXT NULL",
        "ALTER TABLE assistants ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active'",
        "ALTER TABLE assistants ADD COLUMN meta_json JSON NULL",
        "ALTER TABLE assistants ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE assistants ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "ALTER TABLE assistants ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL",
        "ALTER TABLE assistants ADD UNIQUE KEY uq_tenant_assistant (tenant_id, assistant_id)",
        "ALTER TABLE assistants ADD UNIQUE KEY uq_assistant_character (character_id)",
        "ALTER TABLE assistants ADD INDEX idx_assistant_tenant_status (tenant_id, status, updated_at)",
        "ALTER TABLE assistants ADD INDEX idx_assistant_character (character_id)",
    ):
        await _safe_execute(executor, ddl)


async def _ensure_media_assets_table(executor: Any) -> None:
    await executor.execute(text(MEDIA_ASSETS_DDL))
    # Backward-compatible column migration for existing installations.
    await _safe_execute(
        executor,
        f"""
        ALTER TABLE media_assets
        ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER id
        """,
    )
    await _safe_execute(
        executor,
        """
        ALTER TABLE media_assets
        ADD COLUMN required_relationship_level TINYINT UNSIGNED NOT NULL DEFAULT 1
        """,
    )
    await _safe_execute(
        executor,
        """
        ALTER TABLE media_assets
        ADD COLUMN content_intensity VARCHAR(16) NOT NULL DEFAULT 'SOFT'
        """,
    )
    for ddl in (
        "ALTER TABLE media_assets ADD COLUMN title VARCHAR(128) NULL AFTER file_url",
        "ALTER TABLE media_assets ADD COLUMN purchase_hearts_cost INT NOT NULL DEFAULT 0 AFTER content_intensity",
        "ALTER TABLE media_assets ADD COLUMN relation_gain_bonus INT NOT NULL DEFAULT 0 AFTER purchase_hearts_cost",
        "ALTER TABLE media_assets ADD COLUMN is_purchasable TINYINT(1) NOT NULL DEFAULT 0 AFTER relation_gain_bonus",
        "ALTER TABLE media_assets ADD COLUMN media_kind VARCHAR(16) NULL AFTER is_purchasable",
        "ALTER TABLE media_assets ADD COLUMN sort_order INT NOT NULL DEFAULT 0 AFTER media_kind",
        "ALTER TABLE media_assets ADD INDEX idx_media_tenant_character_active (tenant_id, character_id, is_active, created_at)",
    ):
        await _safe_execute(executor, ddl)


async def _ensure_media_delivery_history_table(executor: Any) -> None:
    await executor.execute(text(MEDIA_DELIVERY_HISTORY_DDL))
    await _safe_execute(
        executor,
        f"""
        ALTER TABLE media_delivery_history
        ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER id
        """,
    )
    for ddl in (
        "ALTER TABLE media_delivery_history ADD INDEX idx_mdh_tenant_user_char_time (tenant_id, user_id, character_id, delivered_at)",
        "ALTER TABLE media_delivery_history ADD INDEX idx_mdh_tenant_user_char_asset (tenant_id, user_id, character_id, media_asset_id)",
    ):
        await _safe_execute(executor, ddl)


async def run_progressive_schema_migrations(executor: Any) -> None:
    """Apply additive tenant-scope schema changes without destructive rewrites."""
    await _ensure_tenants_table(executor)
    await _ensure_assistants_table(executor)
    migration_ddls = (
        f"ALTER TABLE user_agent_relations ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER id",
        "ALTER TABLE user_agent_relations ADD INDEX idx_uar_tenant_character (tenant_id, character_id, updated_at)",
        "ALTER TABLE user_agent_relations ADD INDEX idx_uar_tenant_user (tenant_id, user_id, updated_at)",
        f"ALTER TABLE conversations ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER conversation_id",
        "ALTER TABLE conversations ADD INDEX idx_conv_tenant_user_char (tenant_id, user_id, character_id, updated_at)",
        "ALTER TABLE conversations ADD INDEX idx_conv_tenant_status (tenant_id, status, updated_at)",
        f"ALTER TABLE messages ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER conversation_id",
        "ALTER TABLE messages ADD INDEX idx_msg_tenant_conv_ts (tenant_id, character_id, conversation_id, ts)",
        f"ALTER TABLE snapshots ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER conversation_id",
        "ALTER TABLE snapshots ADD INDEX idx_snap_tenant_conv_turn (tenant_id, character_id, conversation_id, turn_index)",
        f"ALTER TABLE chunks ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER chunk_id",
        "ALTER TABLE chunks ADD INDEX idx_chunk_tenant_doc (tenant_id, character_id, doc_id, doc_version)",
        "ALTER TABLE chunks ADD INDEX idx_chunk_tenant_scope (tenant_id, character_id, scope, created_at)",
        "ALTER TABLE chunks ADD INDEX idx_chunk_tenant_private (tenant_id, character_id, user_id, created_at)",
        f"ALTER TABLE ingestion_runs ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER run_id",
        "ALTER TABLE ingestion_runs ADD INDEX idx_run_tenant_status (tenant_id, character_id, status)",
        "ALTER TABLE ingestion_runs ADD INDEX idx_run_tenant_started (tenant_id, character_id, started_at)",
        f"ALTER TABLE user_gift_history ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_SQL}' AFTER id",
        "ALTER TABLE user_gift_history ADD INDEX idx_gift_history_tenant_user_char (tenant_id, user_id, character_id, purchased_at)",
    )
    for ddl in migration_ddls:
        await _safe_execute(executor, ddl)
    await _ensure_media_assets_table(executor)
    await _ensure_media_delivery_history_table(executor)


async def create_tenant(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    description: str | None = None,
    status: str = "draft/review",
    meta_json: dict | None = None,
) -> Tenant:
    obj = Tenant(
        tenant_id=tenant_id,
        label=name,
        name=name,
        description=description,
        status=status,
        meta_json=meta_json,
    )
    db.add(obj)
    await db.flush()
    return obj


async def get_tenant(db: AsyncSession, tenant_id: str) -> Tenant | None:
    stmt = select(Tenant).where(
        Tenant.tenant_id == tenant_id,
        Tenant.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_tenants(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Tenant], int]:
    base = select(Tenant).where(Tenant.deleted_at.is_(None))
    count_base = select(sa_func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None))
    if status:
        base = base.where(Tenant.status == status)
        count_base = count_base.where(Tenant.status == status)

    total = (await db.execute(count_base)).scalar() or 0
    items = (
        await db.execute(
            base.order_by(Tenant.updated_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return items, total


async def update_tenant(
    db: AsyncSession,
    tenant_id: str,
    **fields: object,
) -> Tenant | None:
    obj = await get_tenant(db, tenant_id)
    if obj is None:
        return None
    for key, value in fields.items():
        if hasattr(obj, key) and value is not None:
            setattr(obj, key, value)
            if key == "name":
                obj.label = str(value or obj.label or "").strip() or obj.label
    await db.flush()
    return obj


async def ensure_tenant(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    meta_json: dict | None = None,
) -> Tenant:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    obj = await get_tenant(db, resolved_tenant_id)
    if obj is None:
        return await create_tenant(
            db,
            tenant_id=resolved_tenant_id,
            name=name or _default_tenant_name(resolved_tenant_id),
            description=description,
            meta_json=meta_json,
        )

    changed = False
    if name and obj.name != name:
        obj.name = name
        changed = True
    if description is not None and obj.description != description:
        obj.description = description
        changed = True
    if meta_json:
        merged = dict(obj.meta_json or {})
        merged.update(meta_json)
        if merged != (obj.meta_json or {}):
            obj.meta_json = merged
            changed = True
    if obj.deleted_at is not None:
        obj.deleted_at = None
        changed = True
    if changed:
        await db.flush()
    return obj


async def get_assistant(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    assistant_id: str,
) -> Assistant | None:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    stmt = select(Assistant).where(
        Assistant.tenant_id == resolved_tenant_id,
        Assistant.assistant_id == assistant_id,
        Assistant.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_assistant_by_character(
    db: AsyncSession,
    *,
    character_id: str,
) -> Assistant | None:
    stmt = select(Assistant).where(
        Assistant.character_id == character_id,
        Assistant.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_legacy_assistant_ids(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
) -> list[str]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    ids: set[str] = set()
    sources = (
        (UserAgentRelation, UserAgentRelation.character_id, UserAgentRelation.tenant_id),
        (Conversation, Conversation.character_id, Conversation.tenant_id),
        (Message, Message.character_id, Message.tenant_id),
        (Snapshot, Snapshot.character_id, Snapshot.tenant_id),
        (Chunk, Chunk.character_id, Chunk.tenant_id),
        (IngestionRun, IngestionRun.character_id, IngestionRun.tenant_id),
        (UserGiftHistory, UserGiftHistory.character_id, UserGiftHistory.tenant_id),
    )
    for model, value_column, tenant_column in sources:
        stmt = (
            select(value_column)
            .where(
                tenant_column == resolved_tenant_id,
                value_column.is_not(None),
            )
            .distinct()
        )
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            clean = str(row or "").strip()
            if clean:
                ids.add(clean)
    return sorted(ids)


async def list_assistants(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Assistant], int]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    base = select(Assistant).where(
        Assistant.tenant_id == resolved_tenant_id,
        Assistant.deleted_at.is_(None),
    )
    count_base = select(sa_func.count()).select_from(Assistant).where(
        Assistant.tenant_id == resolved_tenant_id,
        Assistant.deleted_at.is_(None),
    )
    if status:
        base = base.where(Assistant.status == status)
        count_base = count_base.where(Assistant.status == status)

    total = (await db.execute(count_base)).scalar() or 0
    items = (
        await db.execute(
            base.order_by(Assistant.updated_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return items, total


async def upsert_assistant(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    assistant_id: str,
    character_id: str | None = None,
    name: str,
    description: str | None = None,
    status: str = "active",
    meta_json: dict | None = None,
) -> Assistant:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    obj = await get_assistant(
        db,
        tenant_id=resolved_tenant_id,
        assistant_id=assistant_id,
    )
    if obj is None and character_id:
        obj = await get_assistant_by_character(db, character_id=character_id)

    if obj is None:
        obj = Assistant(
            tenant_id=resolved_tenant_id,
            assistant_id=assistant_id,
            character_id=character_id,
            label=name,
            name=name,
            description=description,
            status=status,
            meta_json=meta_json,
        )
        db.add(obj)
        await db.flush()
        return obj

    obj.tenant_id = obj.tenant_id or resolved_tenant_id
    obj.assistant_id = obj.assistant_id or assistant_id
    obj.character_id = character_id or obj.character_id
    obj.label = name
    obj.name = name
    obj.description = description
    obj.status = status
    obj.meta_json = meta_json
    obj.deleted_at = None
    await db.flush()
    return obj


async def update_assistant(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    assistant_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    meta_json: dict | None = None,
) -> Assistant | None:
    obj = await get_assistant(
        db,
        tenant_id=tenant_id,
        assistant_id=assistant_id,
    )
    if obj is None:
        return None
    if name is not None:
        obj.name = name
    if description is not None:
        obj.description = description
    if status is not None:
        obj.status = status
    if meta_json is not None:
        obj.meta_json = meta_json
    if obj.deleted_at is not None:
        obj.deleted_at = None
    await db.flush()
    return obj


async def soft_delete_assistant(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    assistant_id: str,
) -> bool:
    obj = await get_assistant(db, tenant_id=tenant_id, assistant_id=assistant_id)
    if obj is None:
        return False
    obj.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def sync_assistant_from_character(
    db: AsyncSession,
    *,
    character: Character,
    tenant_id: str | None = None,
) -> Assistant:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    await ensure_tenant(
        db,
        tenant_id=resolved_tenant_id,
        name=_default_tenant_name(resolved_tenant_id),
    )
    meta_json = dict(character.meta_json or {})
    meta_json.setdefault("registry_source", "character_sync")
    meta_json["legacy_character_id"] = character.character_id
    return await upsert_assistant(
        db,
        tenant_id=resolved_tenant_id,
        assistant_id=character.character_id,
        character_id=character.character_id,
        name=character.name,
        description=character.description,
        status=character.status,
        meta_json=meta_json,
    )


async def sync_assistant_registry_from_characters(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    page_size: int = 200,
) -> dict[str, int | str]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    await ensure_tenant(
        db,
        tenant_id=resolved_tenant_id,
        name=_default_tenant_name(resolved_tenant_id),
    )

    synced = 0
    offset = 0
    seeded_ids: set[str] = set()
    while True:
        items, _total = await list_characters(
            db,
            limit=page_size,
            offset=offset,
        )
        if not items:
            break
        for item in items:
            await sync_assistant_from_character(
                db,
                tenant_id=resolved_tenant_id,
                character=item,
            )
            synced += 1
            seeded_ids.add(str(item.character_id or "").strip())
        if len(items) < page_size:
            break
        offset += len(items)

    fallback_ids = await list_legacy_assistant_ids(
        db,
        tenant_id=resolved_tenant_id,
    )
    default_assistant_id = str(settings.default_assistant_id or "").strip()
    if default_assistant_id:
        fallback_ids = sorted(set(fallback_ids) | {default_assistant_id})

    for assistant_id in fallback_ids:
        clean_assistant_id = str(assistant_id or "").strip()
        if not clean_assistant_id or clean_assistant_id in seeded_ids:
            continue
        existing = await get_assistant(
            db,
            tenant_id=resolved_tenant_id,
            assistant_id=clean_assistant_id,
        )
        meta_json = dict((existing.meta_json or {}) if existing else {})
        meta_json.setdefault("registry_source", "legacy_bootstrap")
        meta_json["legacy_character_id"] = clean_assistant_id
        await upsert_assistant(
            db,
            tenant_id=resolved_tenant_id,
            assistant_id=clean_assistant_id,
            character_id=clean_assistant_id,
            name=(
                str(existing.name or "").strip()
                if existing and str(existing.name or "").strip() and str(existing.name or "").strip() != "Assistant"
                else _default_assistant_name(clean_assistant_id)
            ),
            description=existing.description if existing else None,
            status=str(existing.status or "active") if existing else "active",
            meta_json=meta_json,
        )
        synced += 1

    return {"tenant_id": resolved_tenant_id, "synced_count": synced}


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
    tenant_id: str | None = None,
    user_id: str,
    character_id: str,
) -> UserAgentRelation | None:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    stmt = select(UserAgentRelation).where(
        UserAgentRelation.tenant_id == resolved_tenant_id,
        UserAgentRelation.user_id == user_id,
        UserAgentRelation.character_id == character_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_user_agent_relations(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    character_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[UserAgentRelation], int]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    filters = [UserAgentRelation.tenant_id == resolved_tenant_id]
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
    tenant_id: str | None = None,
    user_id: str,
    character_id: str,
    version: str,
    relation_state_json: dict,
    interaction_stats_json: dict,
    flags_json: dict,
    meta_json: dict,
) -> UserAgentRelation:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    obj = await get_user_agent_relation(
        db,
        tenant_id=resolved_tenant_id,
        user_id=user_id,
        character_id=character_id,
    )
    if obj is None:
        obj = UserAgentRelation(
            tenant_id=resolved_tenant_id,
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
        obj.tenant_id = resolved_tenant_id
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
    tenant_id: str | None = None,
    character_id: str | None = None,
) -> Conversation | None:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    if character_id:
        stmt = select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.tenant_id == resolved_tenant_id,
            Conversation.character_id == character_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    stmt = select(Conversation).where(
        Conversation.conversation_id == conversation_id,
        Conversation.tenant_id == resolved_tenant_id,
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
    tenant_id: str | None = None,
    character_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    updated_after: datetime | None = None,
    updated_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Conversation], int]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    filters = [Conversation.tenant_id == resolved_tenant_id]
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
    tenant_id: str | None = None,
    character_id: str | None = None,
) -> Conversation | None:
    obj = await get_conversation(
        db,
        conversation_id,
        tenant_id=tenant_id,
        character_id=character_id,
    )
    if obj is None:
        return None
    obj.status = status
    await db.flush()
    return obj


async def upsert_conversation(
    db: AsyncSession,
    *,
    conversation_id: str,
    tenant_id: str | None = None,
    character_id: str,
    user_id: str,
    status: str = "active",
    meta_json: dict | None = None,
) -> Conversation:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    obj = await get_conversation(
        db,
        conversation_id,
        tenant_id=resolved_tenant_id,
        character_id=character_id,
    )
    if obj is None:
        obj = Conversation(
            conversation_id=conversation_id,
            tenant_id=resolved_tenant_id,
            character_id=character_id,
            user_id=user_id,
            status=status,
            meta_json=meta_json,
        )
        db.add(obj)
    else:
        obj.tenant_id = resolved_tenant_id
        obj.user_id = user_id
        obj.status = status
        if meta_json is not None:
            obj.meta_json = meta_json
    await db.flush()
    return obj


async def purge_conversation(
    db: AsyncSession,
    conversation_id: str,
    tenant_id: str | None = None,
    character_id: str | None = None,
) -> dict | None:
    """Hard-delete conversation + messages + snapshots.

    Returns the conversation metadata (character_id, user_id) needed to
    purge the corresponding vectors in Qdrant, or None if not found.
    """
    conv = await get_conversation(
        db,
        conversation_id,
        tenant_id=tenant_id,
        character_id=character_id,
    )
    if conv is None:
        return None

    info = {
        "tenant_id": conv.tenant_id,
        "character_id": conv.character_id,
        "user_id": conv.user_id,
        "conversation_id": conv.conversation_id,
    }

    # Delete messages
    await db.execute(
        delete(Message).where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == conv.tenant_id,
            Message.character_id == conv.character_id,
        )
    )
    # Delete snapshots
    await db.execute(
        delete(Snapshot).where(
            Snapshot.conversation_id == conversation_id,
            Snapshot.tenant_id == conv.tenant_id,
            Snapshot.character_id == conv.character_id,
        )
    )
    # Delete chunks tied to this conversation (private memory)
    await db.execute(
        delete(Chunk).where(
            Chunk.doc_id == f"conv_{conversation_id}",
            Chunk.tenant_id == conv.tenant_id,
            Chunk.character_id == conv.character_id,
        )
    )
    # Delete conversation
    await db.execute(
        delete(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.tenant_id == conv.tenant_id,
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
    tenant_id: str | None = None,
    character_id: str,
    scope: str,
    user_id: str | None,
    source_uri: str | None,
    docs_count: int = 1,
) -> IngestionRun:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    obj = IngestionRun(
        run_id=run_id,
        tenant_id=resolved_tenant_id,
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
    tenant_id: str | None = None,
    character_id: str,
    status: str,
    chunks_count: int,
    error: str | None = None,
) -> IngestionRun | None:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    stmt = select(IngestionRun).where(
        IngestionRun.run_id == run_id,
        IngestionRun.tenant_id == resolved_tenant_id,
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
    tenant_id: str | None = None,
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
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    stmt = select(Chunk).where(
        Chunk.tenant_id == resolved_tenant_id,
        Chunk.character_id == character_id,
        Chunk.chunk_id == chunk_id,
    )
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        obj = Chunk(
            chunk_id=chunk_id,
            tenant_id=resolved_tenant_id,
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
        obj.tenant_id = resolved_tenant_id
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
    tenant_id: str | None,
    character_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Message], int]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    count_stmt = (
        select(sa_func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == resolved_tenant_id,
            Message.character_id == character_id,
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == resolved_tenant_id,
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
    tenant_id: str | None = None,
    character_id: str,
) -> int:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    stmt = (
        select(sa_func.max(Message.turn_index))
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == resolved_tenant_id,
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
    tenant_id: str | None = None,
    character_id: str,
    user_id: str,
    turn_index: int,
    role: str,
    content: str,
    meta_json: dict | None = None,
    ts: datetime | None = None,
) -> Message:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    obj = Message(
        message_id=message_id,
        conversation_id=conversation_id,
        tenant_id=resolved_tenant_id,
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
    tenant_id: str | None,
    character_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Snapshot], int]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    count_stmt = (
        select(sa_func.count())
        .select_from(Snapshot)
        .where(
            Snapshot.conversation_id == conversation_id,
            Snapshot.tenant_id == resolved_tenant_id,
            Snapshot.character_id == character_id,
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    items_stmt = (
        select(Snapshot)
        .where(
            Snapshot.conversation_id == conversation_id,
            Snapshot.tenant_id == resolved_tenant_id,
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
    tenant_id: str | None = None,
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
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
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
        tenant_id=resolved_tenant_id,
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
    tenant_id: str | None = None,
    user_id: str,
    character_id: str | None = None,
    limit: int = 50,
) -> Sequence[UserGiftHistory]:
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    stmt = select(UserGiftHistory).where(
        UserGiftHistory.tenant_id == resolved_tenant_id,
        UserGiftHistory.user_id == user_id,
    )
    if character_id:
        stmt = stmt.where(UserGiftHistory.character_id == character_id)
    stmt = stmt.order_by(UserGiftHistory.purchased_at.desc()).limit(limit)
    return (await db.execute(stmt)).scalars().all()


async def list_media_assets(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    character_id: str,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List media assets from MariaDB table media_assets."""
    await _ensure_media_assets_table(db)
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    where = "WHERE tenant_id = :tenant_id AND character_id = :character_id"
    if active_only:
        where += " AND is_active = 1"

    count_sql = text(f"SELECT COUNT(*) AS total FROM media_assets {where}")
    total = int(
        (
            await db.execute(
                count_sql,
                {"tenant_id": resolved_tenant_id, "character_id": character_id},
            )
        ).scalar()
        or 0
    )

    list_sql = text(
        f"""
        SELECT id, tenant_id, character_id, file_url, title, description, required_relationship_level, content_intensity,
               purchase_hearts_cost, relation_gain_bonus, is_purchasable, media_kind, sort_order,
               is_active, created_at, updated_at
        FROM media_assets
        {where}
        ORDER BY sort_order ASC, id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await db.execute(
            list_sql,
            {
                "tenant_id": resolved_tenant_id,
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
    tenant_id: str | None = None,
    character_id: str,
    file_url: str,
    title: str | None = None,
    description: str | None = None,
    required_relationship_level: int = 1,
    content_intensity: str = "SOFT",
    purchase_hearts_cost: int = 0,
    relation_gain_bonus: int = 0,
    is_purchasable: bool = False,
    media_kind: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> dict:
    await _ensure_media_assets_table(db)
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    normalized_intensity = (content_intensity or "SOFT").strip().upper()
    if normalized_intensity not in {"SOFT", "SENSUAL", "ADULT", "EXPLICIT"}:
        normalized_intensity = "SOFT"
    level = max(1, min(5, int(required_relationship_level or 1)))
    normalized_kind = (media_kind or "").strip().lower()
    if normalized_kind not in {"photo", "video", "audio"}:
        lower_url = str(file_url or "").lower()
        if lower_url.endswith((".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv")):
            normalized_kind = "video"
        elif lower_url.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".weba")):
            normalized_kind = "audio"
        else:
            normalized_kind = "photo"

    upsert_sql = text(
        """
        INSERT INTO media_assets (
          tenant_id, character_id, file_url, title, description, required_relationship_level, content_intensity,
          purchase_hearts_cost, relation_gain_bonus, is_purchasable, media_kind, sort_order, is_active
        )
        VALUES (
          :tenant_id, :character_id, :file_url, :title, :description, :required_relationship_level, :content_intensity,
          :purchase_hearts_cost, :relation_gain_bonus, :is_purchasable, :media_kind, :sort_order, :is_active
        )
        ON DUPLICATE KEY UPDATE
          title = VALUES(title),
          description = VALUES(description),
          required_relationship_level = VALUES(required_relationship_level),
          content_intensity = VALUES(content_intensity),
          purchase_hearts_cost = VALUES(purchase_hearts_cost),
          relation_gain_bonus = VALUES(relation_gain_bonus),
          is_purchasable = VALUES(is_purchasable),
          media_kind = VALUES(media_kind),
          sort_order = VALUES(sort_order),
          is_active = VALUES(is_active),
          updated_at = CURRENT_TIMESTAMP
        """
    )
    await db.execute(
        upsert_sql,
        {
            "tenant_id": resolved_tenant_id,
            "character_id": character_id,
            "file_url": file_url,
            "title": title,
            "description": description,
            "required_relationship_level": level,
            "content_intensity": normalized_intensity,
            "purchase_hearts_cost": max(0, int(purchase_hearts_cost or 0)),
            "relation_gain_bonus": max(0, int(relation_gain_bonus or 0)),
            "is_purchasable": 1 if is_purchasable else 0,
            "media_kind": normalized_kind,
            "sort_order": max(0, int(sort_order or 0)),
            "is_active": 1 if is_active else 0,
        },
    )

    get_sql = text(
        """
        SELECT id, tenant_id, character_id, file_url, title, description, required_relationship_level, content_intensity,
               purchase_hearts_cost, relation_gain_bonus, is_purchasable, media_kind, sort_order,
               is_active, created_at, updated_at
        FROM media_assets
        WHERE tenant_id = :tenant_id AND character_id = :character_id AND file_url = :file_url
        LIMIT 1
        """
    )
    row = (
        await db.execute(
            get_sql,
            {
                "tenant_id": resolved_tenant_id,
                "character_id": character_id,
                "file_url": file_url,
            },
        )
    ).mappings().first()
    return dict(row) if row else {}


async def delete_media_asset(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    asset_id: int,
) -> dict | None:
    await _ensure_media_assets_table(db)
    resolved_tenant_id = _resolve_tenant_id(tenant_id)

    get_sql = text(
        """
        SELECT id, tenant_id, character_id, file_url, description, required_relationship_level, content_intensity, is_active, created_at, updated_at
        FROM media_assets
        WHERE id = :asset_id AND tenant_id = :tenant_id
        LIMIT 1
        """
    )
    row = (
        await db.execute(
            get_sql,
            {"asset_id": int(asset_id), "tenant_id": resolved_tenant_id},
        )
    ).mappings().first()
    if not row:
        return None

    await _ensure_media_delivery_history_table(db)
    await db.execute(
        text(
            """
            DELETE FROM media_delivery_history
            WHERE media_asset_id = :asset_id AND tenant_id = :tenant_id
            """
        ),
        {"asset_id": int(asset_id), "tenant_id": resolved_tenant_id},
    )
    delete_sql = text("DELETE FROM media_assets WHERE id = :asset_id AND tenant_id = :tenant_id")
    await db.execute(delete_sql, {"asset_id": int(asset_id), "tenant_id": resolved_tenant_id})
    return dict(row)


async def pick_media_asset_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    tenant_id: str | None = None,
    character_id: str,
    allow_recycle: bool = True,
    max_relationship_level: int = 5,
    max_content_intensity: str = "EXPLICIT",
    media_kind: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Pick media for a user, preferring unseen assets.

    Returns:
      (asset, source) where source is "unseen" or "recycled", or (None, None).
    """
    await _ensure_media_assets_table(db)
    await _ensure_media_delivery_history_table(db)
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    max_level = max(1, min(5, int(max_relationship_level or 5)))
    max_intensity = (max_content_intensity or "EXPLICIT").strip().upper()
    if max_intensity not in {"SOFT", "SENSUAL", "ADULT", "EXPLICIT"}:
        max_intensity = "EXPLICIT"
    requested_kind = (media_kind or "").strip().lower()
    if requested_kind not in {"photo", "video", "audio"}:
        requested_kind = ""
    media_kind_sql = ""
    if requested_kind:
        media_kind_sql = " AND m.media_kind = :media_kind "

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
        SELECT m.id, m.tenant_id, m.character_id, m.file_url, m.description, m.required_relationship_level, m.content_intensity, m.is_active, m.created_at, m.updated_at
        FROM media_assets m
        WHERE m.tenant_id = :tenant_id
          AND m.character_id = :character_id
          AND m.is_active = 1
          AND m.required_relationship_level <= :max_relationship_level
          AND ({intensity_rank_sql}) <= ({max_intensity_rank_sql})
          {media_kind_sql}
          AND NOT EXISTS (
            SELECT 1
            FROM media_delivery_history h
            WHERE h.media_asset_id = m.id
              AND h.tenant_id = :tenant_id
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
                "tenant_id": resolved_tenant_id,
                "character_id": character_id,
                "max_relationship_level": max_level,
                "max_content_intensity": max_intensity,
                "media_kind": requested_kind,
            },
        )
    ).mappings().first()

    source: str | None = None
    if row:
        source = "unseen"
    elif allow_recycle:
        recycled_sql = text(
            f"""
            SELECT m.id, m.tenant_id, m.character_id, m.file_url, m.description, m.required_relationship_level, m.content_intensity, m.is_active, m.created_at, m.updated_at
            FROM media_assets m
            JOIN media_delivery_history h
              ON h.media_asset_id = m.id
             AND h.tenant_id = :tenant_id
             AND h.user_id = :user_id
             AND h.character_id = :character_id
            WHERE m.tenant_id = :tenant_id
              AND m.character_id = :character_id
              AND m.is_active = 1
              AND m.required_relationship_level <= :max_relationship_level
              AND ({intensity_rank_sql}) <= ({max_intensity_rank_sql})
              {media_kind_sql}
            ORDER BY h.delivered_at ASC
            LIMIT 1
            """
        )
        row = (
            await db.execute(
                recycled_sql,
                {
                    "user_id": user_id,
                    "tenant_id": resolved_tenant_id,
                    "character_id": character_id,
                    "max_relationship_level": max_level,
                    "max_content_intensity": max_intensity,
                    "media_kind": requested_kind,
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
            INSERT INTO media_delivery_history (tenant_id, user_id, character_id, media_asset_id)
            VALUES (:tenant_id, :user_id, :character_id, :media_asset_id)
            """
        ),
        {
            "tenant_id": resolved_tenant_id,
            "user_id": user_id,
            "character_id": character_id,
            "media_asset_id": int(row["id"]),
        },
    )
    return dict(row), source

