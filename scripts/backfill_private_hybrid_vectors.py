#!/usr/bin/env python3
"""Backfill private Qdrant vectors with dense+sparse data from SQL chunks."""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from chatfriends_retrieval.clients import qdrant_client as qc
from chatfriends_retrieval.core.embeddings import embed_text
from chatfriends_retrieval.core.sparse_embeddings import embed_sparse_text
from chatfriends_retrieval.db.models import Chunk
from chatfriends_retrieval.db.session import async_session_factory


async def run(*, character_id: str | None, user_id: str | None, batch_size: int, recreate: bool) -> None:
    if recreate and character_id:
        client = qc.get_qdrant_client()
        name = qc.collection_name(character_id, "private")
        existing = {c.name for c in client.get_collections().collections}
        if name in existing:
            client.delete_collection(name)
            print(f"deleted collection={name}")

    offset = 0
    total = 0
    while True:
        async with async_session_factory() as db:
            stmt = (
                select(Chunk)
                .where(Chunk.scope == "private")
                .order_by(Chunk.created_at.asc())
                .offset(offset)
                .limit(batch_size)
            )
            if character_id:
                stmt = stmt.where(Chunk.character_id == character_id)
            if user_id:
                stmt = stmt.where(Chunk.user_id == user_id)
            rows = (await db.execute(stmt)).scalars().all()

        if not rows:
            break

        for row in rows:
            text = (row.text or "").strip()
            if not text:
                continue
            dense = await embed_text(text)
            sparse = await embed_sparse_text(text)
            qc.ensure_collection(row.character_id, "private", vector_size=len(dense))
            payload = {
                "character_id": row.character_id,
                "scope": "private",
                "user_id": row.user_id,
                "doc_id": row.doc_id,
                "doc_version": row.doc_version,
                "chunk_id": row.chunk_id,
                "json_path": row.json_path,
                "kind": row.kind,
                "tags": row.tags_json or [],
                "lang": row.lang,
                "text": row.text,
            }
            if isinstance(row.meta_json, dict):
                payload.update({k: v for k, v in row.meta_json.items() if v is not None})
            if sparse and sparse.readable_terms:
                payload["sparse_terms"] = [t["term"] for t in sparse.readable_terms]
            payload = {k: v for k, v in payload.items() if v is not None}
            qc.upsert_vector(
                character_id=row.character_id,
                scope="private",
                point_id=row.chunk_id,
                vector=dense,
                sparse_indices=(sparse.indices if sparse else None),
                sparse_values=(sparse.values if sparse else None),
                payload=payload,
            )
            total += 1

        offset += len(rows)
        print(f"processed={total}")

    print(f"done total={total}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill private hybrid vectors into Qdrant.")
    parser.add_argument("--character-id", default=None)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--recreate", action="store_true", help="Delete private collection before backfill (requires --character-id).")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run(
            character_id=args.character_id,
            user_id=args.user_id,
            batch_size=max(1, int(args.batch_size)),
            recreate=bool(args.recreate),
        )
    )

