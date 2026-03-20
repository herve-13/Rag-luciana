"""Admin router — /admin/* endpoints protected by X-Admin-Key."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from rag_luciana.api.deps import AdminAuth, DbSession
from rag_luciana.api.schemas import (
    CharacterCreate,
    CharacterListResponse,
    CharacterResponse,
    CharacterUpdate,
    ConversationListResponse,
    ConversationUpsertRequest,
    ConversationResponse,
    MessageBatchCreateRequest,
    MessageListResponse,
    MessageResponse,
    SnapshotListResponse,
    SnapshotResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
    UserAgentRelationListResponse,
    UserAgentRelationResponse,
    UserAgentRelationUpsert,
    MediaAssetListResponse,
    MediaAssetResponse,
    MediaAssetUpsertRequest,
    MediaPickRequest,
    MediaPickResponse,
    VectorDeleteRequest,
    VectorDeleteResponse,
)
from rag_luciana.clients.qdrant_client import delete_by_filter
from rag_luciana.db import repo
from rag_luciana.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[AdminAuth])


# ═════════════════════════════════════════════════════════
#  Characters
# ═════════════════════════════════════════════════════════


@router.post(
    "/characters",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_character(body: CharacterCreate, db: DbSession):
    existing = await repo.get_character(db, body.character_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Character '{body.character_id}' already exists.",
        )
    obj = await repo.create_character(
        db,
        character_id=body.character_id,
        name=body.name,
        description=body.description,
        meta_json=body.meta_json,
    )
    return obj


@router.get("/characters", response_model=CharacterListResponse)
async def list_characters(
    db: DbSession,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await repo.list_characters(
        db, status=status_filter, limit=limit, offset=offset
    )
    return CharacterListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/characters/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: str, db: DbSession):
    obj = await repo.get_character(db, character_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Character not found.")
    return obj


@router.patch("/characters/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str, body: CharacterUpdate, db: DbSession
):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    obj = await repo.update_character(db, character_id, **fields)
    if obj is None:
        raise HTTPException(status_code=404, detail="Character not found.")
    return obj


@router.delete(
    "/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_character(character_id: str, db: DbSession):
    ok = await repo.soft_delete_character(db, character_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Character not found.")


# ═════════════════════════════════════════════════════════
#  Users
# ═════════════════════════════════════════════════════════


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(body: UserCreate, db: DbSession):
    existing = await repo.get_user(db, body.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{body.user_id}' already exists.",
        )
    obj = await repo.create_user(
        db,
        user_id=body.user_id,
        display_name=body.display_name,
        meta_json=body.meta_json,
    )
    return obj


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: DbSession,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await repo.list_users(
        db, status=status_filter, limit=limit, offset=offset
    )
    return UserListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: DbSession):
    obj = await repo.get_user(db, user_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return obj


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, body: UserUpdate, db: DbSession):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    obj = await repo.update_user(db, user_id, **fields)
    if obj is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return obj


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, db: DbSession):
    ok = await repo.soft_delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")


# ═════════════════════════════════════════════════════════

# ========================================================================
#  User-Agent Relations
# ========================================================================


def _relation_row_to_response(row) -> UserAgentRelationResponse:
    return UserAgentRelationResponse(
        user_id=row.user_id,
        agent_id=row.character_id,
        version=row.version,
        relation_state=row.relation_state_json,
        interaction_stats=row.interaction_stats_json,
        flags=row.flags_json,
        meta=row.meta_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "/relations",
    response_model=UserAgentRelationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_relation(body: UserAgentRelationUpsert, db: DbSession):
    now = datetime.utcnow()
    meta = body.meta.model_dump() if body.meta else {
        "created_at": now,
        "last_updated": now,
    }
    if "created_at" not in meta:
        meta["created_at"] = now
    meta["last_updated"] = now

    obj = await repo.upsert_user_agent_relation(
        db,
        user_id=body.user_id,
        character_id=body.agent_id,
        version=body.version,
        relation_state_json=body.relation_state.model_dump(),
        interaction_stats_json=body.interaction_stats.model_dump(),
        flags_json=body.flags.model_dump(),
        meta_json=meta,
    )
    return _relation_row_to_response(obj)


@router.get("/relations", response_model=UserAgentRelationListResponse)
async def list_relations(
    db: DbSession,
    user_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await repo.list_user_agent_relations(
        db,
        user_id=user_id,
        character_id=agent_id,
        limit=limit,
        offset=offset,
    )
    return UserAgentRelationListResponse(
        items=[_relation_row_to_response(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/relations/{user_id}/{agent_id}",
    response_model=UserAgentRelationResponse,
)
async def get_relation(user_id: str, agent_id: str, db: DbSession):
    obj = await repo.get_user_agent_relation(
        db,
        user_id=user_id,
        character_id=agent_id,
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Relation not found.")
    return _relation_row_to_response(obj)
#  Conversations
# ═════════════════════════════════════════════════════════


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    db: DbSession,
    character_id: str | None = Query(None),
    user_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    updated_after: datetime | None = Query(None),
    updated_before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await repo.list_conversations(
        db,
        character_id=character_id,
        user_id=user_id,
        status=status_filter,
        updated_after=updated_after,
        updated_before=updated_before,
        limit=limit,
        offset=offset,
    )
    return ConversationListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.post(
    "/conversations/upsert",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_conversation(body: ConversationUpsertRequest, db: DbSession):
    obj = await repo.upsert_conversation(
        db,
        conversation_id=body.conversation_id,
        character_id=body.character_id,
        user_id=body.user_id,
        status=body.status,
        meta_json=body.meta_json,
    )
    return obj


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationResponse
)
async def get_conversation(conversation_id: str, db: DbSession):
    obj = await repo.get_conversation(db, conversation_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return obj


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def get_conversation_messages(
    conversation_id: str,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    # Verify conversation exists
    conv = await repo.get_conversation(db, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    items, total = await repo.list_messages(
        db,
        conversation_id,
        conv.character_id,
        limit=limit,
        offset=offset,
    )
    return MessageListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_messages(
    conversation_id: str,
    body: MessageBatchCreateRequest,
    db: DbSession,
):
    if body.conversation_id != conversation_id:
        raise HTTPException(
            status_code=400,
            detail="Path/body conversation_id mismatch.",
        )

    conv = await repo.get_conversation(
        db, conversation_id, body.character_id
    )
    if conv is None:
        conv = await repo.upsert_conversation(
            db,
            conversation_id=conversation_id,
            character_id=body.character_id,
            user_id=body.user_id,
            status="active",
            meta_json=None,
        )
    elif conv.user_id != body.user_id:
        raise HTTPException(
            status_code=400,
            detail="Conversation belongs to a different user.",
        )

    last_turn = await repo.get_last_turn_index(
        db,
        conversation_id=conversation_id,
        character_id=body.character_id,
    )
    created_items: list[MessageResponse] = []
    turn = last_turn + 1
    for msg in body.messages:
        normalized_role = "character" if msg.role == "assistant" else msg.role
        created = await repo.create_message(
            db,
            message_id=str(uuid4()),
            conversation_id=conversation_id,
            character_id=body.character_id,
            user_id=body.user_id,
            turn_index=turn,
            role=normalized_role,
            content=msg.content,
            meta_json=msg.meta_json,
            ts=msg.ts,
        )
        created_items.append(MessageResponse.model_validate(created))
        turn += 1

    # Touch conversation updated_at and keep it active.
    await repo.upsert_conversation(
        db,
        conversation_id=conversation_id,
        character_id=body.character_id,
        user_id=body.user_id,
        status="active",
        meta_json=conv.meta_json if conv else None,
    )

    return MessageListResponse(
        items=created_items,
        total=len(created_items),
        limit=len(created_items),
        offset=0,
    )


@router.get(
    "/conversations/{conversation_id}/snapshots",
    response_model=SnapshotListResponse,
)
async def get_conversation_snapshots(
    conversation_id: str,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conv = await repo.get_conversation(db, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    items, total = await repo.list_snapshots(
        db,
        conversation_id,
        conv.character_id,
        limit=limit,
        offset=offset,
    )
    return SnapshotListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.post(
    "/conversations/{conversation_id}/close",
    response_model=ConversationResponse,
)
async def close_conversation(conversation_id: str, db: DbSession):
    obj = await repo.set_conversation_status(db, conversation_id, "closed")
    if obj is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return obj


@router.post(
    "/conversations/{conversation_id}/open",
    response_model=ConversationResponse,
)
async def open_conversation(conversation_id: str, db: DbSession):
    obj = await repo.set_conversation_status(db, conversation_id, "active")
    if obj is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return obj


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def purge_conversation(conversation_id: str, db: DbSession):
    """Hard-delete conversation + messages + snapshots + vector memory.

    This is a destructive operation. The conversation and all associated
    data (including private embeddings in Qdrant) are permanently removed.
    """
    info = await repo.purge_conversation(db, conversation_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # ── Purge vectors in Qdrant (private collection) ─────
    try:
        delete_by_filter(
            character_id=info["character_id"],
            scope="private",
            filters={
                "user_id": info["user_id"],
                "conversation_id": info["conversation_id"],
            },
        )
        logger.info(
            "conversation_vectors_purged",
            conversation_id=conversation_id,
            character_id=info["character_id"],
        )
    except Exception:
        # Log but don't fail the request — SQL data is already purged
        logger.error(
            "conversation_vector_purge_failed",
            conversation_id=conversation_id,
            exc_info=True,
        )


@router.get("/media/assets", response_model=MediaAssetListResponse)
async def list_media_assets(
    db: DbSession,
    character_id: str = Query(..., min_length=1),
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items, total = await repo.list_media_assets(
        db,
        character_id=character_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return MediaAssetListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/media/assets",
    response_model=MediaAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_media_asset(body: MediaAssetUpsertRequest, db: DbSession):
    obj = await repo.upsert_media_asset(
        db,
        character_id=body.character_id,
        file_url=body.file_url,
        title=body.title,
        description=body.description,
        required_relationship_level=body.required_relationship_level,
        content_intensity=body.content_intensity,
        purchase_hearts_cost=body.purchase_hearts_cost,
        relation_gain_bonus=body.relation_gain_bonus,
        is_purchasable=body.is_purchasable,
        media_kind=body.media_kind,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    return MediaAssetResponse(**obj)


@router.post("/media/pick", response_model=MediaPickResponse)
async def pick_media_asset(body: MediaPickRequest, db: DbSession):
    item, source = await repo.pick_media_asset_for_user(
        db,
        user_id=body.user_id,
        character_id=body.character_id,
        allow_recycle=body.allow_recycle,
        max_relationship_level=body.max_relationship_level,
        max_content_intensity=body.max_content_intensity,
    )
    if item is None:
        return MediaPickResponse(item=None, source=None)
    return MediaPickResponse(item=MediaAssetResponse(**item), source=source)


@router.delete("/media/assets/{asset_id}", response_model=MediaAssetResponse)
async def delete_media_asset(asset_id: int, db: DbSession):
    obj = await repo.delete_media_asset(db, asset_id=asset_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Media asset not found.")
    return MediaAssetResponse(**obj)


@router.post("/vectors/delete", response_model=VectorDeleteResponse)
async def delete_vectors(body: VectorDeleteRequest):
    if not isinstance(body.filters, dict) or not body.filters:
        raise HTTPException(status_code=400, detail="filters must be a non-empty object.")
    try:
        delete_by_filter(
            character_id=body.character_id,
            scope=body.scope,
            filters=body.filters,
        )
        logger.info(
            "vectors_deleted_by_filter",
            character_id=body.character_id,
            scope=body.scope,
            filters=body.filters,
        )
        return VectorDeleteResponse(
            status="ok",
            character_id=body.character_id,
            scope=body.scope,
            filters=body.filters,
        )
    except Exception:
        logger.error(
            "vector_delete_by_filter_failed",
            character_id=body.character_id,
            scope=body.scope,
            filters=body.filters,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="vector deletion failed")

