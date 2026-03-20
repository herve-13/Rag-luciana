"""Retrieval pipeline: dense+sparse hybrid (private scope) with RRF and rerank."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_luciana.clients import qdrant_client as qc
from rag_luciana.core.embeddings import embed_text
from rag_luciana.core.reranker import rerank, reranker_enabled
from rag_luciana.core.sparse_embeddings import embed_sparse_terms_weighted, sparse_enabled
from rag_luciana.settings import settings


@dataclass
class ChunkHit:
    chunk_id: str
    doc_id: str
    score: float
    text: str | None
    rerank_text: str | None = None
    metadata: dict = field(default_factory=dict)


def _rrf_add(scores: dict[str, float], seen: set[str], chunk_id: str, rank: int, k: int) -> None:
    if chunk_id in seen:
        return
    scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank))
    seen.add(chunk_id)


def _normalize_sparse_terms_payload(sparse_query: dict | None) -> list[dict[str, float]]:
    if not isinstance(sparse_query, dict):
        return []
    raw_terms = sparse_query.get("terms")
    if not isinstance(raw_terms, list):
        return []
    out: list[dict[str, float]] = []
    seen: set[str] = set()
    for item in raw_terms:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip().lower()
        if not term or term in seen:
            continue
        try:
            weight = float(item.get("weight") or 0.0)
        except Exception:
            weight = 0.0
        if weight <= 0.0:
            continue
        seen.add(term)
        out.append({"term": term, "weight": max(0.0, min(1.0, weight))})
        if len(out) >= 6:
            break
    return out


async def retrieve(
    *,
    character_id: str,
    query: str,
    scope: str = "private",
    user_id: str | None = None,
    conversation_id: str | None = None,
    top_k: int = 10,
    filters: dict | None = None,
    sparse_query: dict | None = None,
    return_text: bool = True,
    debug_sink: dict | None = None,
) -> list[ChunkHit]:
    """Run hybrid retrieval for private memory only."""
    if scope != "private":
        raise ValueError("scope must be private")
    if user_id is None:
        raise ValueError("user_id is required for scope=private")

    dense_query = await embed_text(query)
    sparse_terms_weighted = _normalize_sparse_terms_payload(sparse_query)
    sparse_mode = "disabled"
    sparse_disabled_reason = ""
    sparse_vector = None
    if sparse_enabled() and sparse_terms_weighted:
        sparse_vector = await embed_sparse_terms_weighted(sparse_terms_weighted)
        if sparse_vector is not None:
            sparse_mode = "llm_terms"
        else:
            sparse_disabled_reason = "sparse_embedding_failed"
    elif not sparse_terms_weighted:
        sparse_disabled_reason = "no_sparse_terms_from_backend"

    candidate_multiplier = max(1, settings.reranker_candidate_multiplier)
    candidate_k = top_k * candidate_multiplier if reranker_enabled() else top_k
    rrf_k = max(1, int(settings.rrf_k_hybrid or settings.rrf_k))

    private_filters: dict = {
        **(filters or {}),
        "character_id": character_id,
        "user_id": user_id,
    }
    if conversation_id:
        private_filters["conversation_id"] = conversation_id

    dense_hits = qc.search_vectors(
        character_id=character_id,
        scope="private",
        vector=dense_query,
        limit=candidate_k,
        filters=private_filters,
    )

    sparse_hits = []
    if sparse_vector is not None:
        sparse_hits = qc.search_sparse_vectors(
            character_id=character_id,
            scope="private",
            indices=sparse_vector.indices,
            values=sparse_vector.values,
            limit=candidate_k,
            filters=private_filters,
        )

    seen: dict[str, ChunkHit] = {}
    rrf_scores: dict[str, float] = {}
    dense_seen: set[str] = set()
    sparse_seen: set[str] = set()
    dense_scores: dict[str, float] = {}
    sparse_scores: dict[str, float] = {}
    query_terms = [t["term"] for t in (sparse_vector.readable_terms if sparse_vector else [])]

    for rank, h in enumerate(dense_hits, start=1):
        payload = h.payload or {}
        if str(payload.get("character_id") or "").strip() != str(character_id):
            continue
        if str(payload.get("user_id") or "").strip() != str(user_id):
            continue
        if conversation_id and str(payload.get("conversation_id") or "").strip() != str(conversation_id):
            continue
        chunk_id = str(payload.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        dense_scores[chunk_id] = float(h.score)
        _rrf_add(rrf_scores, dense_seen, chunk_id, rank, rrf_k)
        payload_text = payload.get("text")
        hit = seen.get(chunk_id)
        if hit is None:
            seen[chunk_id] = ChunkHit(
                chunk_id=chunk_id,
                doc_id=str(payload.get("doc_id") or ""),
                score=float(h.score),
                text=payload_text if return_text else None,
                rerank_text=payload_text,
                metadata={k: v for k, v in payload.items() if k not in ("text",)},
            )
        elif float(h.score) > float(hit.score):
            hit.score = float(h.score)

    for rank, h in enumerate(sparse_hits, start=1):
        payload = h.payload or {}
        if str(payload.get("character_id") or "").strip() != str(character_id):
            continue
        if str(payload.get("user_id") or "").strip() != str(user_id):
            continue
        if conversation_id and str(payload.get("conversation_id") or "").strip() != str(conversation_id):
            continue
        chunk_id = str(payload.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        sparse_scores[chunk_id] = float(h.score)
        _rrf_add(rrf_scores, sparse_seen, chunk_id, rank, rrf_k)
        if chunk_id not in seen:
            payload_text = payload.get("text")
            seen[chunk_id] = ChunkHit(
                chunk_id=chunk_id,
                doc_id=str(payload.get("doc_id") or ""),
                score=float(h.score),
                text=payload_text if return_text else None,
                rerank_text=payload_text,
                metadata={k: v for k, v in payload.items() if k not in ("text",)},
            )

    deduped = list(seen.values())
    for hit in deduped:
        chunk_id = hit.chunk_id
        hit.metadata["dense_score"] = dense_scores.get(chunk_id)
        hit.metadata["sparse_score"] = sparse_scores.get(chunk_id)
        hit.metadata["rrf_score"] = rrf_scores.get(chunk_id, 0.0)
        hit.metadata["retrieval_stage"] = "hybrid_rrf"
        sparse_terms = hit.metadata.get("sparse_terms") or []
        if isinstance(sparse_terms, list) and query_terms:
            overlap = [t for t in sparse_terms if t in query_terms][: max(1, settings.sparse_top_terms_log)]
            if overlap:
                hit.metadata["sparse_contrib_terms"] = overlap
        hit.score = float(hit.metadata["rrf_score"])

    deduped.sort(
        key=lambda h: (
            h.metadata.get("rrf_score", 0.0),
            h.metadata.get("dense_score", float("-inf")) or float("-inf"),
            h.metadata.get("sparse_score", float("-inf")) or float("-inf"),
        ),
        reverse=True,
    )
    deduped = deduped[:candidate_k]

    if reranker_enabled() and deduped:
        rerank_indices: list[int] = []
        rerank_texts: list[str] = []
        for i, hit in enumerate(deduped):
            text = (hit.rerank_text or "").strip()
            if text:
                rerank_indices.append(i)
                rerank_texts.append(text)
        if rerank_texts:
            rerank_scores = await rerank(query=query, texts=rerank_texts)
            if rerank_scores is not None:
                for idx, rerank_score in zip(rerank_indices, rerank_scores, strict=True):
                    hit = deduped[idx]
                    hit.metadata["rerank_score"] = float(rerank_score)
                    hit.metadata["retrieval_stage"] = "reranked"
                    hit.score = float(rerank_score)
                deduped.sort(key=lambda h: h.score, reverse=True)

    if isinstance(debug_sink, dict):
        dense_hits_debug = []
        for rank, h in enumerate(dense_hits, start=1):
            payload = h.payload or {}
            dense_hits_debug.append(
                {
                    "rank": int(rank),
                    "chunk_id": str(payload.get("chunk_id") or ""),
                    "doc_id": str(payload.get("doc_id") or ""),
                    "score": float(h.score),
                    "text_preview": str(payload.get("text") or "")[:180],
                }
            )
        sparse_hits_debug = []
        for rank, h in enumerate(sparse_hits, start=1):
            payload = h.payload or {}
            sparse_hits_debug.append(
                {
                    "rank": int(rank),
                    "chunk_id": str(payload.get("chunk_id") or ""),
                    "doc_id": str(payload.get("doc_id") or ""),
                    "score": float(h.score),
                    "sparse_terms": payload.get("sparse_terms") if isinstance(payload.get("sparse_terms"), list) else [],
                    "text_preview": str(payload.get("text") or "")[:180],
                }
            )
        top_hits_debug = []
        for hit in deduped[: min(len(deduped), 8)]:
            top_hits_debug.append(
                {
                    "chunk_id": hit.chunk_id,
                    "dense_score": hit.metadata.get("dense_score"),
                    "sparse_score": hit.metadata.get("sparse_score"),
                    "rrf_score": hit.metadata.get("rrf_score"),
                    "rerank_score": hit.metadata.get("rerank_score"),
                    "sparse_contrib_terms": hit.metadata.get("sparse_contrib_terms", []),
                }
            )
        debug_sink["hybrid_debug"] = {
            "dense_hits_count": len(dense_hits),
            "sparse_hits_count": len(sparse_hits),
            "sparse_mode": sparse_mode,
            "sparse_disabled_reason": sparse_disabled_reason,
            "sparse_used_terms": sparse_terms_weighted,
            "query_dense_vector_preview": dense_query[:32] if isinstance(dense_query, list) else [],
            "query_sparse_terms": sparse_vector.readable_terms if sparse_vector else [],
            "query_sparse_vector": {
                "indices": (sparse_vector.indices[:32] if sparse_vector else []),
                "values": (sparse_vector.values[:32] if sparse_vector else []),
            },
            "dense_branch_hits": dense_hits_debug,
            "sparse_branch_hits": sparse_hits_debug,
            "top_hits": top_hits_debug,
        }

    return deduped[:top_k]

