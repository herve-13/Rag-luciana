"""FastAPI application entry-point."""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Awaitable

import structlog
from fastapi import FastAPI, Request

from chatfriends_retrieval.api.admin_router import router as admin_router
from chatfriends_retrieval.api.gifts_router import router as gifts_router
from chatfriends_retrieval.api.health_router import router as health_router
from chatfriends_retrieval.api.ingest_router import router as ingest_router
from chatfriends_retrieval.api.query_router import router as query_router
from chatfriends_retrieval.clients import ollama_client
from chatfriends_retrieval.core import reranker
from chatfriends_retrieval.core import sparse_embeddings
from chatfriends_retrieval.db import repo
from chatfriends_retrieval.db.models import Base
from chatfriends_retrieval.db.session import async_session_factory, engine
from chatfriends_retrieval.logging import setup_logging
from chatfriends_retrieval.settings import settings

setup_logging()
logger = structlog.get_logger(__name__)


async def _run_startup_prewarm(
    step_name: str,
    enabled: bool,
    operation: Awaitable[bool],
) -> None:
    """Keep startup non-blocking even if a prewarm step is slow or fails."""
    if not enabled:
        return

    timeout_s = max(1.0, float(settings.startup_prewarm_timeout_seconds))
    try:
        success = await asyncio.wait_for(operation, timeout=timeout_s)
        logger.info(step_name, success=bool(success))
    except asyncio.TimeoutError:
        logger.warning(step_name, success=False, timed_out=True, timeout_s=timeout_s)
    except Exception as exc:
        logger.warning(step_name, success=False, error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await repo.run_progressive_schema_migrations(conn)
    async with async_session_factory() as session:
        await repo.sync_assistant_registry_from_characters(
            session,
            tenant_id=settings.default_tenant_id,
        )
        await session.commit()

    await _run_startup_prewarm(
        "startup_prewarm_embeddings",
        settings.prewarm_embeddings_on_startup,
        ollama_client.prewarm_embed_model(),
    )
    await _run_startup_prewarm(
        "startup_prewarm_reranker",
        settings.prewarm_reranker_on_startup,
        reranker.prewarm(),
    )
    await _run_startup_prewarm(
        "startup_prewarm_sparse",
        settings.prewarm_sparse_on_startup,
        sparse_embeddings.prewarm(),
    )

    logger.info("startup_complete")
    yield
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="ChatFriends Retrieval Service",
    description="Retrieval and derived-memory service with per-user memory isolation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(query_router)
app.include_router(ingest_router)
app.include_router(admin_router)
app.include_router(gifts_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed_ms=elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response

