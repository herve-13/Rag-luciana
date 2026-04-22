"""Sparse BM25 embeddings with lightweight readable term extraction."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from chatfriends_retrieval.logging import get_logger
from chatfriends_retrieval.settings import settings

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_NOISE_TERMS = {
    "a",
    "ai",
    "and",
    "au",
    "aux",
    "c",
    "ce",
    "ces",
    "d",
    "de",
    "des",
    "du",
    "en",
    "et",
    "j",
    "je",
    "l",
    "la",
    "le",
    "les",
    "m",
    "me",
    "mon",
    "ma",
    "mes",
    "n",
    "ne",
    "nos",
    "notre",
    "ou",
    "par",
    "pour",
    "qu",
    "que",
    "s",
    "sa",
    "se",
    "ses",
    "sur",
    "t",
    "te",
    "tes",
    "ton",
    "ta",
    "type",
    "tu",
    "un",
    "une",
    "vos",
    "votre",
    "y",
}
_model_lock = asyncio.Lock()
_model: Any | None = None


@dataclass
class SparseEmbedding:
    indices: list[int]
    values: list[float]
    readable_terms: list[dict[str, float]]


def sparse_enabled() -> bool:
    return bool(settings.hybrid_enabled and settings.sparse_enabled)


def _normalize_text_for_terms(text: str) -> str:
    clean = unicodedata.normalize("NFKC", str(text or "")).lower()
    clean = clean.replace("’", "'")
    clean = clean.replace("'", " ")
    clean = clean.replace("-", " ")
    return clean


def _is_meaningful_term(token: str) -> bool:
    term = str(token or "").strip().lower()
    if not term:
        return False
    if term in _NOISE_TERMS:
        return False
    if len(term) <= 1:
        return False
    if len(term) == 2 and not any(ch.isdigit() for ch in term):
        return False
    return True


def _build_readable_terms(text: str) -> list[dict[str, float]]:
    normalized = _normalize_text_for_terms(text)
    tokens = [m.group(0).lower() for m in _TOKEN_RE.finditer(normalized)]
    tokens = [token for token in tokens if _is_meaningful_term(token)]
    if not tokens:
        return []
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    max_count = max(counts.values())
    weighted = [
        {"term": term, "weight": round(count / max_count, 6)}
        for term, count in counts.items()
        if count > 0
    ]
    weighted.sort(key=lambda item: item["weight"], reverse=True)
    min_weight = max(0.0, float(settings.sparse_min_weight_log))
    top_k = max(1, int(settings.sparse_top_terms_log))
    return [w for w in weighted if float(w["weight"]) >= min_weight][:top_k]


def _load_model_sync() -> Any | None:
    try:
        from fastembed import SparseTextEmbedding  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency/runtime dependent
        logger.warning("sparse_model_import_failed", error=str(exc))
        return None
    try:
        model = SparseTextEmbedding(model_name=settings.sparse_model)
        logger.info("sparse_model_loaded", model=settings.sparse_model)
        return model
    except Exception as exc:  # pragma: no cover - dependency/runtime dependent
        logger.warning("sparse_model_load_failed", model=settings.sparse_model, error=str(exc))
        return None


async def _get_model() -> Any | None:
    global _model
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is not None:
            return _model
        _model = await asyncio.to_thread(_load_model_sync)
        return _model


def _embed_sync(model: Any, text: str) -> SparseEmbedding | None:
    try:
        result = next(iter(model.embed([text])))
    except Exception as exc:  # pragma: no cover - dependency/runtime dependent
        logger.warning("sparse_embed_failed", error=str(exc))
        return None
    raw_indices = getattr(result, "indices", None)
    raw_values = getattr(result, "values", None)
    if raw_indices is None or raw_values is None:
        return None
    if hasattr(raw_indices, "tolist"):
        raw_indices = raw_indices.tolist()
    if hasattr(raw_values, "tolist"):
        raw_values = raw_values.tolist()
    indices = [int(v) for v in list(raw_indices)]
    values = [float(v) for v in list(raw_values)]
    if not indices or not values or len(indices) != len(values):
        return None
    return SparseEmbedding(
        indices=indices,
        values=values,
        readable_terms=_build_readable_terms(text),
    )


async def embed_sparse_text(text: str) -> SparseEmbedding | None:
    if not sparse_enabled():
        return None
    clean = (text or "").strip()
    if not clean:
        return None
    model = await _get_model()
    if model is None:
        return None
    return await asyncio.to_thread(_embed_sync, model, clean)


def _normalize_term(term: str) -> str:
    token = _normalize_text_for_terms(term)
    matches = _TOKEN_RE.findall(token)
    if not matches:
        return ""
    for match in matches:
        normalized = str(match or "").strip().lower()
        if _is_meaningful_term(normalized):
            return normalized
    return ""


async def embed_sparse_terms_weighted(terms: list[dict[str, float]]) -> SparseEmbedding | None:
    if not sparse_enabled():
        return None
    weighted_terms: list[str] = []
    for item in terms or []:
        if not isinstance(item, dict):
            continue
        term = _normalize_term(str(item.get("term") or ""))
        if not term:
            continue
        try:
            weight = float(item.get("weight") or 0.0)
        except Exception:
            weight = 0.0
        if weight <= 0.0:
            continue
        repeat = max(1, min(4, int(round(weight * 4.0))))
        weighted_terms.extend([term] * repeat)
        if len(weighted_terms) >= 24:
            break
    if not weighted_terms:
        return None
    synthetic_query = " ".join(weighted_terms).strip()
    return await embed_sparse_text(synthetic_query)


async def prewarm() -> bool:
    if not sparse_enabled():
        return False
    model = await _get_model()
    return model is not None

