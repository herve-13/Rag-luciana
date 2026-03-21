"""Ingest router - POST /ingest."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from rag_luciana.api.deps import AdminAuth, DbSession
from rag_luciana.api.schemas import IngestRequest, IngestResponse
from rag_luciana.db import repo
from rag_luciana.ingest.ingest_json import ingest_json_document
from rag_luciana.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["ingest"], dependencies=[AdminAuth])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(req: IngestRequest, db: DbSession) -> IngestResponse:
    if req.scope != "private":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope must be private",
        )
    run_id = str(uuid.uuid4())

    await repo.create_ingestion_run(
        db,
        run_id=run_id,
        character_id=req.character_id,
        scope=req.scope,
        user_id=req.user_id,
        source_uri=req.source_uri,
        docs_count=1,
    )

    try:
        chunks_count = await ingest_json_document(
            db,
            character_id=req.character_id,
            scope=req.scope,
            user_id=req.user_id,
            doc_id=req.doc_id,
            doc_version=req.doc_version,
            source_uri=req.source_uri,
            kind=req.kind,
            tags=req.tags,
            bucket=req.bucket,
            subject=req.subject,
            canonical=req.canonical,
            source=req.source,
            metadata=req.metadata,
            lang=req.lang,
            data=req.data,
            chunk_max_length=req.chunk_max_length,
            chunk_overlap=req.chunk_overlap,
        )
        await repo.finish_ingestion_run(
            db,
            run_id=run_id,
            character_id=req.character_id,
            status="success",
            chunks_count=chunks_count,
        )
        logger.info(
            "ingest_success",
            run_id=run_id,
            character_id=req.character_id,
            scope=req.scope,
            chunks_count=chunks_count,
        )
        return IngestResponse(
            run_id=run_id,
            character_id=req.character_id,
            scope=req.scope,
            user_id=req.user_id,
            doc_id=req.doc_id,
            doc_version=req.doc_version,
            status="success",
            chunks_count=chunks_count,
        )
    except Exception as exc:
        await repo.finish_ingestion_run(
            db,
            run_id=run_id,
            character_id=req.character_id,
            status="failed",
            chunks_count=0,
            error=str(exc)[:2000],
        )
        # Persist failed run tracking even though the request returns an error.
        await db.commit()
        logger.error(
            "ingest_failed",
            run_id=run_id,
            character_id=req.character_id,
            scope=req.scope,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ingestion failed. Check server logs for details.",
        )
