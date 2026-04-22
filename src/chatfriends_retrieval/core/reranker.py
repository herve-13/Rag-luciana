"""Optional cross-encoder reranker for retrieval results."""

from __future__ import annotations

import asyncio
from threading import Lock
from typing import Any

from chatfriends_retrieval.logging import get_logger
from chatfriends_retrieval.settings import settings

logger = get_logger(__name__)

_model: Any | None = None
_model_lock = Lock()
_warned_missing_dependency = False


def reranker_enabled() -> bool:
    return settings.reranker_enabled


def _get_model() -> Any | None:
    global _model
    global _warned_missing_dependency

    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        try:
            from sentence_transformers import CrossEncoder
        except Exception:
            if not _warned_missing_dependency:
                logger.warning(
                    "Reranker enabled but sentence-transformers is unavailable; "
                    "falling back to vector scores."
                )
                _warned_missing_dependency = True
            return None

        kwargs: dict[str, Any] = {
            "model_name": settings.reranker_model,
            "trust_remote_code": settings.reranker_trust_remote_code,
            "max_length": settings.reranker_max_length,
        }
        if settings.reranker_device:
            kwargs["device"] = settings.reranker_device

        _model = CrossEncoder(**kwargs)
        logger.info("Loaded reranker model", model=settings.reranker_model)
        return _model


async def rerank(query: str, texts: list[str]) -> list[float] | None:
    """Return rerank scores for (query, text) pairs, or None if unavailable."""
    if not texts:
        return []

    model = _get_model()
    if model is None:
        return None

    pairs = [[query, text] for text in texts]

    def _predict() -> list[float]:
        scores = model.predict(
            pairs,
            batch_size=settings.reranker_batch_size,
            show_progress_bar=False,
        )
        return [float(s) for s in scores]

    try:
        return await asyncio.to_thread(_predict)
    except Exception:
        logger.exception("Reranker inference failed; using vector ranking fallback.")
        return None


async def prewarm() -> bool:
    """Force-load the reranker model if enabled."""
    if not settings.reranker_enabled:
        return False
    model = await asyncio.to_thread(_get_model)
    return model is not None

