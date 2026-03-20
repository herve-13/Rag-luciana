"""FastAPI application entry-point."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request

from rag_luciana.api.admin_router import router as admin_router
from rag_luciana.api.gifts_router import router as gifts_router
from rag_luciana.api.health_router import router as health_router
from rag_luciana.api.ingest_router import router as ingest_router
from rag_luciana.api.query_router import router as query_router
from rag_luciana.clients import ollama_client
from rag_luciana.core import reranker
from rag_luciana.core import sparse_embeddings
from rag_luciana.db.models import Base
from rag_luciana.db.session import engine
from rag_luciana.logging import setup_logging
from rag_luciana.settings import settings

setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Create tables (dev convenience – use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if settings.prewarm_embeddings_on_startup:
        warmed_embed = await ollama_client.prewarm_embed_model()
        logger.info("startup_prewarm_embeddings", success=bool(warmed_embed))
    if settings.prewarm_reranker_on_startup:
        warmed_reranker = await reranker.prewarm()
        logger.info("startup_prewarm_reranker", success=bool(warmed_reranker))
    if settings.prewarm_sparse_on_startup:
        warmed_sparse = await sparse_embeddings.prewarm()
        logger.info("startup_prewarm_sparse", success=bool(warmed_sparse))
    logger.info("startup_complete")
    yield
    await engine.dispose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="RAG Luciana",
    description="Multi-character RAG service with per-user memory isolation.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Routers ──────────────────────────────────────────────
app.include_router(health_router)
app.include_router(query_router)
app.include_router(ingest_router)
app.include_router(admin_router)
app.include_router(gifts_router)


# ── Request logging middleware ───────────────────────────


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
