"""Ingestion pipeline: JSON payload -> chunks -> embeddings -> SQL + Qdrant."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from rag_luciana.clients import qdrant_client as qc
from rag_luciana.core.chunking import chunk_text
from rag_luciana.core.embeddings import embed_text
from rag_luciana.db import repo


@dataclass
class PreparedChunk:
    text: str
    json_path: str


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _collect_text_nodes(data: Any, path: str = "$") -> list[PreparedChunk]:
    nodes: list[PreparedChunk] = []

    if isinstance(data, dict):
        for key, value in data.items():
            child_path = f"{path}.{key}"
            nodes.extend(_collect_text_nodes(value, child_path))
        return nodes

    if isinstance(data, list):
        for idx, value in enumerate(data):
            child_path = f"{path}[{idx}]"
            nodes.extend(_collect_text_nodes(value, child_path))
        return nodes

    text = _normalize_text(data)
    if text:
        nodes.append(PreparedChunk(text=text, json_path=path))
    return nodes


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def ingest_json_document(
    db: AsyncSession,
    *,
    character_id: str,
    scope: str,
    user_id: str | None,
    doc_id: str,
    doc_version: int,
    source_uri: str | None,
    kind: str | None,
    tags: list[str] | None,
    lang: str | None,
    data: Any,
    chunk_max_length: int,
    chunk_overlap: int,
) -> int:
    """Ingest a JSON-like document and return the number of upserted chunks."""
    text_nodes = _collect_text_nodes(data)
    if not text_nodes:
        return 0

    prepared: list[PreparedChunk] = []
    for node in text_nodes:
        pieces = chunk_text(
            node.text,
            max_length=chunk_max_length,
            overlap=chunk_overlap,
        )
        for piece in pieces:
            prepared.append(PreparedChunk(text=piece, json_path=node.json_path))

    if not prepared:
        return 0

    # Infer embedding size from first chunk and ensure the target collection exists.
    first_vector = await embed_text(prepared[0].text)
    qc.ensure_collection(character_id, scope, vector_size=len(first_vector))

    for ordinal, item in enumerate(prepared):
        vector = first_vector if ordinal == 0 else await embed_text(item.text)
        text_hash = _sha256_hex(item.text)
        chunk_id = _sha256_hex(
            "|".join(
                [
                    character_id,
                    scope,
                    user_id or "",
                    doc_id,
                    item.json_path,
                    text_hash,
                ]
            )
        )

        payload = {
            "character_id": character_id,
            "scope": scope,
            "user_id": user_id,
            "doc_id": doc_id,
            "doc_version": doc_version,
            "chunk_id": chunk_id,
            "json_path": item.json_path,
            "kind": kind,
            "tags": tags or [],
            "lang": lang,
            "source_uri": source_uri,
            "text": item.text,
        }
        # Remove null values to keep payload compact and filters predictable.
        payload = {k: v for k, v in payload.items() if v is not None}

        await repo.upsert_chunk(
            db,
            chunk_id=chunk_id,
            character_id=character_id,
            scope=scope,
            user_id=user_id,
            doc_id=doc_id,
            doc_version=doc_version,
            ordinal=ordinal,
            json_path=item.json_path,
            kind=kind,
            text=item.text,
            text_hash=text_hash,
            lang=lang,
            tags_json=tags,
            meta_json={"source_uri": source_uri} if source_uri else None,
        )

        qc.upsert_vector(
            character_id=character_id,
            scope=scope,
            point_id=chunk_id,
            vector=vector,
            payload=payload,
        )

    return len(prepared)
