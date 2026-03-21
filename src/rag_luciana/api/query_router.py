"""Query router — POST /query."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from rag_luciana.api.schemas import ChunkResult, QueryRequest, QueryResponse
from rag_luciana.core.retrieval import retrieve
from rag_luciana.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Semantic retrieval across character knowledge / private memory."""
    if req.scope != "private":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope must be private",
        )
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
        if req.filters.bucket:
            extra_filters["bucket"] = req.filters.bucket
        if req.filters.subject:
            extra_filters["subject"] = req.filters.subject
        if req.filters.canonical is not None:
            extra_filters["canonical"] = bool(req.filters.canonical)
        if req.filters.source:
            extra_filters["source"] = req.filters.source
        if isinstance(req.filters.metadata, dict):
            for key, value in req.filters.metadata.items():
                if value is None:
                    continue
                if isinstance(value, list):
                    clean_values = [item for item in value if item not in (None, "")]
                    if clean_values:
                        extra_filters[key] = clean_values
                    continue
                if value != "":
                    extra_filters[key] = value

    debug_payload: dict = {}
    hits = await retrieve(
        character_id=req.character_id,
        query=req.query,
        scope=req.scope,
        user_id=req.user_id,
        conversation_id=req.conversation_id,
        top_k=req.top_k,
        filters=extra_filters or None,
        sparse_query=req.sparse_query.model_dump() if req.sparse_query is not None else None,
        return_text=req.return_text,
        debug_sink=debug_payload,
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

    hybrid_debug = debug_payload.get("hybrid_debug") if isinstance(debug_payload.get("hybrid_debug"), dict) else {}

    logger.info(
        "query_done",
        query_id=query_id,
        results_count=len(results),
        hybrid_debug=hybrid_debug,
    )

    return QueryResponse(
        query_id=query_id,
        character_id=req.character_id,
        user_id=req.user_id,
        top_k=req.top_k,
        results=results,
        hybrid_debug=hybrid_debug,
    )
