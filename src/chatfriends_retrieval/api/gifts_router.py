"""Gift economy endpoints used by the active backend contract."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from chatfriends_retrieval.api.deps import DbSession
from chatfriends_retrieval.db import repo
from chatfriends_retrieval.settings import settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/gifts", tags=["gifts"])


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


class GiftOut(BaseModel):
    id: int
    name: str
    hearts_cost: int
    bond_bonus: int
    category: str
    description: str | None = None
    image_url: str | None = None
    unlock_level: int = 0


class WalletOut(BaseModel):
    user_id: str
    hearts_balance: int
    total_earned: int
    total_spent: int


class PurchaseRequest(BaseModel):
    user_id: str
    tenant_id: str | None = None
    assistant_id: str = Field(..., min_length=1, max_length=64)
    gift_id: int


class PurchaseResult(BaseModel):
    ok: bool
    bond_bonus: int = 0
    hearts_remaining: int = 0
    gift_name: str | None = None
    category: str | None = None
    error: str | None = None


class CreditRequest(BaseModel):
    user_id: str
    amount: int


class GiftHistoryOut(BaseModel):
    id: int
    user_id: str
    tenant_id: str | None = None
    assistant_id: str
    gift_id: int
    purchased_at: str


@router.get("/catalog", response_model=list[GiftOut])
async def get_catalog(db: DbSession, category: str | None = None):
    items = await repo.list_gift_catalog(db, category=category)
    return [
        GiftOut(
            id=g.id,
            name=g.name,
            hearts_cost=g.hearts_cost,
            bond_bonus=g.bond_bonus,
            category=g.category,
            description=g.description,
            image_url=g.image_url,
            unlock_level=g.unlock_level,
        )
        for g in items
    ]


@router.get("/wallet/{user_id}", response_model=WalletOut)
async def get_wallet(db: DbSession, user_id: str):
    wallet = await repo.get_or_create_wallet(db, user_id)
    await db.commit()
    return WalletOut(
        user_id=wallet.user_id,
        hearts_balance=wallet.hearts_balance,
        total_earned=wallet.total_earned,
        total_spent=wallet.total_spent,
    )


@router.post("/purchase", response_model=PurchaseResult)
async def purchase_gift(db: DbSession, body: PurchaseRequest):
    resolved_tenant_id = _resolve_tenant_id(body.tenant_id)
    resolved_assistant_id = _resolve_assistant_id(body.assistant_id)
    result = await repo.purchase_gift(
        db,
        tenant_id=resolved_tenant_id,
        user_id=body.user_id,
        character_id=resolved_assistant_id,
        gift_id=body.gift_id,
    )
    if result["ok"]:
        await db.commit()
        logger.info(
            "gift_purchased",
            user_id=body.user_id,
            assistant_id=resolved_assistant_id,
            gift_name=result.get("gift_name"),
            bond_bonus=result["bond_bonus"],
        )
    else:
        await db.rollback()
    return PurchaseResult(**result)


@router.post("/credit", response_model=WalletOut)
async def credit_hearts(db: DbSession, body: CreditRequest):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")
    wallet = await repo.credit_hearts(db, body.user_id, body.amount)
    await db.commit()
    logger.info("hearts_credited", user_id=body.user_id, amount=body.amount)
    return WalletOut(
        user_id=wallet.user_id,
        hearts_balance=wallet.hearts_balance,
        total_earned=wallet.total_earned,
        total_spent=wallet.total_spent,
    )


@router.get("/history/{user_id}/assistants/{assistant_id}", response_model=list[GiftHistoryOut])
async def get_history(
    db: DbSession,
    user_id: str,
    assistant_id: str,
    tenant_id: str | None = Query(None),
):
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    items = await repo.list_gift_history(
        db,
        tenant_id=resolved_tenant_id,
        user_id=user_id,
        character_id=resolved_assistant_id,
    )
    return [
        GiftHistoryOut(
            id=h.id,
            user_id=h.user_id,
            tenant_id=getattr(h, "tenant_id", resolved_tenant_id),
            assistant_id=resolved_assistant_id,
            gift_id=h.gift_id,
            purchased_at=h.purchased_at.isoformat(),
        )
        for h in items
    ]

