"""Retrieval pipeline for private memory chunks with hybrid dense+sparse support."""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_luciana.clients import qdrant_client as qc
from rag_luciana.core.embeddings import embed_text
from rag_luciana.core.reranker import rerank, reranker_enabled
from rag_luciana.core.sparse_embeddings import (
    embed_sparse_terms_weighted,
    embed_sparse_text,
    sparse_enabled,
)
from rag_luciana.settings import settings


@dataclass
class ChunkHit:
    chunk_id: str
    doc_id: str
    score: float
    text: str | None
    rerank_text: str | None = None
    metadata: dict = field(default_factory=dict)


def _normalize_sparse_terms_payload(sparse_query: dict | None) -> list[dict[str, float]]:
    if not isinstance(sparse_query, dict):
        return []
    raw_terms = sparse_query.get("terms")
    if not isinstance(raw_terms, list):
        return []
    out: list[dict[str, float]] = []
    for item in raw_terms:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        if not term:
            continue
        try:
            weight = float(item.get("weight") or 0.0)
        except Exception:
            weight = 0.0
        if weight <= 0.0:
            continue
        out.append({"term": term, "weight": weight})
        if len(out) >= 6:
            break
    return out


def _payload_matches_scope(
    payload: dict,
    *,
    character_id: str,
    user_id: str,
    conversation_id: str | None,
) -> bool:
    if str(payload.get("character_id") or "").strip() != str(character_id):
        return False
    if str(payload.get("user_id") or "").strip() != str(user_id):
        return False
    if conversation_id and str(payload.get("conversation_id") or "").strip() != str(conversation_id):
        return False
    return True


def _rrf_contribution(rank: int, k: int) -> float:
    return 1.0 / float(k + rank)


def _build_chunk_hit(*, payload: dict, score: float, return_text: bool) -> ChunkHit:
    payload_text = payload.get("text")
    return ChunkHit(
        chunk_id=str(payload.get("chunk_id") or ""),
        doc_id=str(payload.get("doc_id") or ""),
        score=float(score),
        text=payload_text if return_text else None,
        rerank_text=payload_text,
        metadata={k: v for k, v in payload.items() if k not in ("text",)},
    )


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
    if scope != "private":
        raise ValueError("scope must be private")
    if user_id is None:
        raise ValueError("user_id is required for scope=private")

    dense_query = await embed_text(query)
    candidate_multiplier = max(1, settings.reranker_candidate_multiplier)
    candidate_k = top_k * candidate_multiplier if reranker_enabled() else top_k
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

    sparse_terms = _normalize_sparse_terms_payload(sparse_query)
    sparse_mode = "disabled"
    sparse_disabled_reason = ""
    sparse_query_debug: list[dict[str, float]] = []
    sparse_embedding = None

    if sparse_enabled():
        if sparse_terms:
            sparse_embedding = await embed_sparse_terms_weighted(sparse_terms)
            sparse_mode = "llm_terms"
            sparse_query_debug = sparse_terms
            if sparse_embedding is None:
                sparse_disabled_reason = "sparse_embedding_failed_from_terms"
        else:
            raw_query_sparse = await embed_sparse_text(query)
            sparse_query_debug = [
                {"term": str(item.get("term") or ""), "weight": float(item.get("weight") or 0.0)}
                for item in (raw_query_sparse.readable_terms if raw_query_sparse else [])
                if str(item.get("term") or "").strip()
            ]
            if sparse_query_debug:
                sparse_embedding = await embed_sparse_terms_weighted(sparse_query_debug)
                sparse_mode = "clean_query_terms_fallback"
                if sparse_embedding is None:
                    sparse_disabled_reason = "sparse_embedding_failed_from_clean_query_terms"
            elif raw_query_sparse is not None:
                sparse_embedding = raw_query_sparse
                sparse_mode = "raw_query_fallback"
            else:
                sparse_disabled_reason = "sparse_embedding_failed_from_query"
    else:
        sparse_disabled_reason = "sparse_disabled_in_settings"

    sparse_hits = []
    if sparse_embedding is not None:
        sparse_hits = qc.search_sparse_vectors(
            character_id=character_id,
            scope="private",
            indices=sparse_embedding.indices,
            values=sparse_embedding.values,
            limit=candidate_k,
            filters=private_filters,
        )

    merged_by_chunk: dict[str, ChunkHit] = {}
    rrf_k = max(1, int(settings.rrf_k_hybrid))

    for rank, h in enumerate(dense_hits, start=1):
        payload = h.payload or {}
        if not _payload_matches_scope(
            payload,
            character_id=character_id,
            user_id=user_id,
            conversation_id=conversation_id,
        ):
            continue
        chunk_id = str(payload.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        entry = merged_by_chunk.get(chunk_id)
        if entry is None:
            entry = _build_chunk_hit(payload=payload, score=0.0, return_text=return_text)
            merged_by_chunk[chunk_id] = entry
        entry.metadata["dense_score"] = float(h.score)
        entry.metadata["rrf_score"] = float(entry.metadata.get("rrf_score") or 0.0) + _rrf_contribution(rank, rrf_k)

    for rank, h in enumerate(sparse_hits, start=1):
        payload = h.payload or {}
        if not _payload_matches_scope(
            payload,
            character_id=character_id,
            user_id=user_id,
            conversation_id=conversation_id,
        ):
            continue
        chunk_id = str(payload.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        entry = merged_by_chunk.get(chunk_id)
        if entry is None:
            entry = _build_chunk_hit(payload=payload, score=0.0, return_text=return_text)
            merged_by_chunk[chunk_id] = entry
        entry.metadata["sparse_score"] = float(h.score)
        entry.metadata["rrf_score"] = float(entry.metadata.get("rrf_score") or 0.0) + _rrf_contribution(rank, rrf_k)
        sparse_terms_payload = payload.get("sparse_terms")
        if isinstance(sparse_terms_payload, list):
            contrib_terms = [str(term).strip() for term in sparse_terms_payload if str(term).strip()]
            if contrib_terms:
                entry.metadata["sparse_contrib_terms"] = contrib_terms[:12]

    deduped = list(merged_by_chunk.values())
    if sparse_hits:
        for hit in deduped:
            hit.metadata["retrieval_stage"] = "hybrid_rrf"
            hit.score = float(hit.metadata.get("rrf_score") or 0.0)
        deduped.sort(key=lambda h: h.score, reverse=True)
    else:
        for hit in deduped:
            hit.metadata["retrieval_stage"] = "dense"
            hit.score = float(hit.metadata.get("dense_score") or 0.0)
        deduped.sort(key=lambda h: h.score, reverse=True)

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

    deduped = deduped[:top_k]

    if isinstance(debug_sink, dict):
        debug_sink["hybrid_debug"] = {
            "dense_hits_count": len(dense_hits),
            "sparse_hits_count": len(sparse_hits),
            "sparse_mode": sparse_mode,
            "sparse_disabled_reason": sparse_disabled_reason,
            "query_sparse_terms": sparse_query_debug,
            "dense_branch_hits": [
                {
                    "rank": int(rank),
                    "chunk_id": str((h.payload or {}).get("chunk_id") or ""),
                    "doc_id": str((h.payload or {}).get("doc_id") or ""),
                    "score": float(h.score),
                    "text_preview": str((h.payload or {}).get("text") or "")[:180],
                }
                for rank, h in enumerate(dense_hits, start=1)
            ],
            "sparse_branch_hits": [
                {
                    "rank": int(rank),
                    "chunk_id": str((h.payload or {}).get("chunk_id") or ""),
                    "doc_id": str((h.payload or {}).get("doc_id") or ""),
                    "score": float(h.score),
                    "text_preview": str((h.payload or {}).get("text") or "")[:180],
                }
                for rank, h in enumerate(sparse_hits, start=1)
            ],
            "top_hits": [
                {
                    "chunk_id": hit.chunk_id,
                    "doc_id": hit.doc_id,
                    "score": hit.score,
                    "text_preview": str(hit.text or "")[:180],
                }
                for hit in deduped
            ],
        }

    return deduped
