"""FastAPI dependencies: DB session, admin auth, clients."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from chatfriends_retrieval.db.session import get_db as _get_db
from chatfriends_retrieval.settings import settings

# ── Database session ─────────────────────────────────────

DbSession = Annotated[AsyncSession, Depends(_get_db)]

# ── Admin key verification ───────────────────────────────


async def verify_admin_key(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    """Raise 401 if the X-Admin-Key header is missing or invalid."""
    if not x_admin_key or x_admin_key != settings.admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header.",
        )


AdminAuth = Depends(verify_admin_key)

