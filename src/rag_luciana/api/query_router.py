"""Query router — POST /query."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from rag_luciana.api.schemas import ChunkResult, QueryRequest, QueryResponse
from rag_luciana.core.retrieval import retrieve
from rag_luciana.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Semantic retrieval across character knowledge / private memory."""
    query_id = str(uuid.uuid4())
    logger.info(
        "query_start",
        query_id=query_id,
        character_id=req.character_id,
        scope=req.scope,
    )

    # Build extra Qdrant payload filters from request
    extra_filters: dict = {}
    if req.filters:
        if req.filters.tags:
            extra_filters["tags"] = req.filters.tags
        if req.filters.kinds:
            extra_filters["kind"] = req.filters.kinds

    hits = await retrieve(
        character_id=req.character_id,
        query=req.query,
        scope=req.scope,
        user_id=req.user_id,
        conversation_id=req.conversation_id,
        top_k=req.top_k,
        filters=extra_filters or None,
        return_text=req.return_text,
    )

    results = [
        ChunkResult(
            chunk_id=h.chunk_id,
            doc_id=h.doc_id,
            score=h.score,
            text=h.text,
            metadata=h.metadata,
        )
        for h in hits
    ]

    logger.info(
        "query_done",
        query_id=query_id,
        results_count=len(results),
    )

    return QueryResponse(
        query_id=query_id,
        character_id=req.character_id,
        user_id=req.user_id,
        top_k=req.top_k,
        results=results,
    )
