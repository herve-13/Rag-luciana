"""Gift economy API endpoints (catalog, wallet, purchase, history)."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rag_luciana.api.deps import DbSession
from rag_luciana.db import repo

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/gifts", tags=["gifts"])


# ── Schemas ──────────────────────────────────────────────


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
    character_id: str
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
    character_id: str
    gift_id: int
    purchased_at: str


# ── Endpoints ────────────────────────────────────────────


@router.get("/catalog", response_model=list[GiftOut])
async def get_catalog(db: DbSession, category: str | None = None):
    """List active gifts, optionally filtered by category."""
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
    """Get or create a user's heart wallet."""
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
    """
    Purchase a gift. Returns bond_bonus for backend to update trust.
    Transaction secured with FOR UPDATE to prevent double-debit.
    """
    result = await repo.purchase_gift(
        db,
        user_id=body.user_id,
        character_id=body.character_id,
        gift_id=body.gift_id,
    )
    if result["ok"]:
        await db.commit()
        logger.info(
            "gift_purchased",
            user_id=body.user_id,
            character_id=body.character_id,
            gift_name=result.get("gift_name"),
            bond_bonus=result["bond_bonus"],
        )
    else:
        await db.rollback()
    return PurchaseResult(**result)


@router.post("/credit", response_model=WalletOut)
async def credit_hearts(db: DbSession, body: CreditRequest):
    """Credit hearts to a user (admin / streak / milestone)."""
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


@router.get("/history/{user_id}", response_model=list[GiftHistoryOut])
@router.get("/history/{user_id}/{character_id}", response_model=list[GiftHistoryOut])
async def get_history(db: DbSession, user_id: str, character_id: str | None = None):
    """List gift history for a user, optionally filtered by character."""
    items = await repo.list_gift_history(db, user_id=user_id, character_id=character_id)
    return [
        GiftHistoryOut(
            id=h.id,
            user_id=h.user_id,
            character_id=h.character_id,
            gift_id=h.gift_id,
            purchased_at=h.purchased_at.isoformat(),
        )
        for h in items
    ]
