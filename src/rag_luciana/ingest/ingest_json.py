"""Ingestion pipeline: simple phrase records -> SQL chunks + Qdrant."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from rag_luciana.clients import qdrant_client as qc
from rag_luciana.core.embeddings import embed_text
from rag_luciana.core.sparse_embeddings import embed_sparse_text
from rag_luciana.db import repo


@dataclass
class PreparedChunk:
    text: str
    json_path: str


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.split()).strip()
    return ""


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _collect_simple_text_nodes(data: Any) -> list[PreparedChunk]:
    if isinstance(data, list):
        return [
            PreparedChunk(text=_normalize_text(item), json_path=f"$.records[{idx}]")
            for idx, item in enumerate(data)
            if _normalize_text(item)
        ]
    if isinstance(data, dict):
        retrieval_text = _normalize_text(data.get("retrieval_text"))
        if retrieval_text:
            return [PreparedChunk(text=retrieval_text, json_path="$.retrieval_text")]
    single = _normalize_text(data)
    if single:
        return [PreparedChunk(text=single, json_path="$.text")]
    return []


async def ingest_json_document(
    db: AsyncSession,
    *,
    tenant_id: str,
    assistant_id: str | None = None,
    scope: str,
    user_id: str | None,
    doc_id: str,
    doc_version: int,
    source_uri: str | None,
    kind: str | None,
    tags: list[str] | None,
    bucket: str | None,
    subject: str | None,
    canonical: bool | None,
    source: str | None,
    metadata: dict[str, Any] | None,
    lang: str | None,
    data: Any,
    chunk_max_length: int,
    chunk_overlap: int,
) -> int:
    resolved_assistant_id = str(assistant_id or "").strip()
    if not resolved_assistant_id:
        raise ValueError("assistant_id is required")
    if scope != "private":
        raise ValueError("scope must be private")
    resolved_tenant_id = str(tenant_id or "").strip()
    if not resolved_tenant_id:
        raise ValueError("tenant_id is required")
    clean_metadata = metadata if isinstance(metadata, dict) else {}
    prepared = _collect_simple_text_nodes(data)
    if not prepared:
        return 0

    first_vector = await embed_text(prepared[0].text)
    first_sparse = await embed_sparse_text(prepared[0].text)
    qc.ensure_collection(
        assistant_id=resolved_assistant_id,
        scope=scope,
        vector_size=len(first_vector),
        tenant_id=resolved_tenant_id,
    )

    for ordinal, item in enumerate(prepared):
        if ordinal == 0:
            vector = first_vector
            sparse = first_sparse
        else:
            vector = await embed_text(item.text)
            sparse = await embed_sparse_text(item.text)
        text_hash = _sha256_hex(item.text)
        chunk_id = _sha256_hex(
            "|".join(
                [
                    resolved_assistant_id,
                    scope,
                    user_id or "",
                    doc_id,
                    item.json_path,
                    text_hash,
                ]
            )
        )
        payload = {
            "tenant_id": resolved_tenant_id,
            "assistant_id": resolved_assistant_id,
            "scope": scope,
            "user_id": user_id,
            "doc_id": doc_id,
            "doc_version": doc_version,
            "chunk_id": chunk_id,
            "json_path": item.json_path,
            "lang": lang,
            "source_uri": source_uri,
            "text": item.text,
            "bucket": bucket,
            "subject": subject,
            "canonical": canonical,
            "source": source,
            **{k: v for k, v in clean_metadata.items() if v is not None},
        }
        if sparse and sparse.readable_terms:
            payload["sparse_terms"] = [t["term"] for t in sparse.readable_terms]
        payload = {k: v for k, v in payload.items() if v is not None}

        await repo.upsert_chunk(
            db,
            chunk_id=chunk_id,
            tenant_id=resolved_tenant_id,
            character_id=resolved_assistant_id,
            scope=scope,
            user_id=user_id,
            doc_id=doc_id,
            doc_version=doc_version,
            ordinal=ordinal,
            json_path=item.json_path,
            kind=(kind or "simple_memory"),
            text=item.text,
            text_hash=text_hash,
            lang=lang,
            tags_json=tags,
            meta_json=(
                {
                    k: v
                    for k, v in {
                        "source_uri": source_uri,
                        "bucket": bucket,
                        "subject": subject,
                        "canonical": canonical,
                        "source": source,
                        **clean_metadata,
                    }.items()
                    if v is not None
                }
                or None
            ),
        )
        qc.upsert_vector(
            assistant_id=resolved_assistant_id,
            scope=scope,
            tenant_id=resolved_tenant_id,
            point_id=chunk_id,
            vector=vector,
            sparse_indices=(sparse.indices if sparse else None),
            sparse_values=(sparse.values if sparse else None),
            payload=payload,
        )

    return len(prepared)
