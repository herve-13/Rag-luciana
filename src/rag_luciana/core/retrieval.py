"""Retrieval pipeline: embed query → search Qdrant → merge & dedup."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from rag_luciana.clients import qdrant_client as qc
from rag_luciana.core.embeddings import embed_text
from rag_luciana.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkHit:
    chunk_id: str
    doc_id: str
    score: float
    text: str | None
    metadata: dict = field(default_factory=dict)


async def retrieve(
    *,
    character_id: str,
    query: str,
    scope: str = "both",
    user_id: str | None = None,
    conversation_id: str | None = None,
    top_k: int = 10,
    filters: dict | None = None,
    return_text: bool = True,
) -> list[ChunkHit]:
    """Run the full retrieval pipeline.

    Parameters
    ----------
    scope : "global" | "private" | "both"
    filters : extra Qdrant payload filters (tags, kinds …)
    """
    vector = await embed_text(query)

    results: list[ChunkHit] = []

    if scope in ("global", "both"):
        k_global = top_k if scope == "global" else math.ceil(top_k / 2)
        global_filters = {**(filters or {}), "character_id": character_id}
        hits = qc.search_vectors(
            character_id=character_id,
            scope="global",
            vector=vector,
            limit=k_global,
            filters=global_filters,
        )
        for h in hits:
            payload = h.payload or {}
            results.append(
                ChunkHit(
                    chunk_id=payload.get("chunk_id", ""),
                    doc_id=payload.get("doc_id", ""),
                    score=h.score,
                    text=payload.get("text") if return_text else None,
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ("text",)
                    },
                )
            )

    if scope in ("private", "both"):
        if user_id is None:
            raise ValueError("user_id is required for scope=private")
        k_private = top_k if scope == "private" else top_k - math.ceil(top_k / 2)
        private_filters: dict = {
            **(filters or {}),
            "character_id": character_id,
            "user_id": user_id,
        }
        if conversation_id:
            private_filters["conversation_id"] = conversation_id
        hits = qc.search_vectors(
            character_id=character_id,
            scope="private",
            vector=vector,
            limit=k_private,
            filters=private_filters,
        )
        for h in hits:
            payload = h.payload or {}
            results.append(
                ChunkHit(
                    chunk_id=payload.get("chunk_id", ""),
                    doc_id=payload.get("doc_id", ""),
                    score=h.score,
                    text=payload.get("text") if return_text else None,
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ("text",)
                    },
                )
            )

    # Dedup by chunk_id, keep highest score
    seen: dict[str, ChunkHit] = {}
    for hit in results:
        if hit.chunk_id not in seen or hit.score > seen[hit.chunk_id].score:
            seen[hit.chunk_id] = hit
    deduped = sorted(seen.values(), key=lambda h: h.score, reverse=True)

    return deduped[:top_k]
