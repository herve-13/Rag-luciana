"""Health & readiness routers."""

from __future__ import annotations

from fastapi import APIRouter

from chatfriends_retrieval.api.schemas import HealthResponse, ReadyResponse
from chatfriends_retrieval.clients import ollama_client
from chatfriends_retrieval.clients.qdrant_client import health_check as qdrant_health
from chatfriends_retrieval.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe — always returns 200."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse)
async def readyz() -> ReadyResponse:
    """Readiness probe — checks MariaDB, Qdrant, and Ollama."""
    checks: dict[str, bool] = {}

    # MariaDB
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        checks["mariadb"] = True
    except Exception:
        checks["mariadb"] = False

    # Qdrant
    checks["qdrant"] = qdrant_health()

    # Ollama
    checks["ollama"] = await ollama_client.health_check()

    all_ready = all(checks.values())
    return ReadyResponse(
        status="ready" if all_ready else "not_ready",
        checks=checks,
    )

