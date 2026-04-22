#!/usr/bin/env python3
"""Rebuild Qdrant vectors from the SQL chunks table.

Examples:
  python scripts/reindex_from_db.py --character-id npc_jean --scope global
  python scripts/reindex_from_db.py --character-id npc_jean --scope both --reset
  python scripts/reindex_from_db.py --limit 200 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Iterable

from sqlalchemy import select

from chatfriends_retrieval.clients import qdrant_client as qc
from chatfriends_retrieval.core.embeddings import embed_text
from chatfriends_retrieval.db.models import Chunk
from chatfriends_retrieval.db.session import async_session_factory, engine


def _source_uri(meta_json: dict | None) -> str | None:
    if not isinstance(meta_json, dict):
        return None
    src = meta_json.get("source_uri")
    return str(src) if src else None


def _scopes(arg_scope: str) -> list[str]:
    if arg_scope == "both":
        return ["global", "private"]
    return [arg_scope]


def _build_filters(character_id: str | None, scope: str, user_id: str | None):
    filters = [Chunk.scope == scope]
    if character_id:
        filters.append(Chunk.character_id == character_id)
    if scope == "private" and user_id:
        filters.append(Chunk.user_id == user_id)
    return filters


async def _iter_chunks(
    *,
    character_id: str | None,
    scope: str,
    user_id: str | None,
    limit: int | None,
) -> list[Chunk]:
    async with async_session_factory() as session:
        stmt = select(Chunk).where(*_build_filters(character_id, scope, user_id))
        stmt = stmt.order_by(Chunk.character_id.asc(), Chunk.created_at.asc())
        if limit:
            stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return list(rows)


async def reindex(
    *,
    character_id: str | None,
    scope: str,
    user_id: str | None,
    limit: int | None,
    reset: bool,
    dry_run: bool,
) -> None:
    scopes = _scopes(scope)

    if reset and not dry_run:
        client = qc.get_qdrant_client()
        existing = {c.name for c in client.get_collections().collections}
        if character_id:
            targets = {qc.collection_name(character_id, s) for s in scopes}
        else:
            targets = {name for name in existing if name.startswith("rag_")}
        for name in sorted(targets):
            if name in existing:
                client.delete_collection(name)
                print(f"deleted {name}")

    total_indexed = 0

    for target_scope in scopes:
        chunks = await _iter_chunks(
            character_id=character_id,
            scope=target_scope,
            user_id=user_id,
            limit=limit,
        )
        if not chunks:
            print(f"scope={target_scope}: no chunks")
            continue

        # Bucket by character to create one collection per character/scope.
        by_character: dict[str, list[Chunk]] = {}
        for chunk in chunks:
            by_character.setdefault(chunk.character_id, []).append(chunk)

        for cid, items in by_character.items():
            if dry_run:
                print(f"[dry-run] scope={target_scope} character={cid} chunks={len(items)}")
                total_indexed += len(items)
                continue

            first_vector = await embed_text(items[0].text)
            qc.ensure_collection(cid, target_scope, vector_size=len(first_vector))

            for idx, chunk in enumerate(items):
                vector = first_vector if idx == 0 else await embed_text(chunk.text)
                payload = {
                    "character_id": chunk.character_id,
                    "scope": chunk.scope,
                    "user_id": chunk.user_id,
                    "doc_id": chunk.doc_id,
                    "doc_version": chunk.doc_version,
                    "chunk_id": chunk.chunk_id,
                    "json_path": chunk.json_path,
                    "kind": chunk.kind,
                    "tags": chunk.tags_json or [],
                    "lang": chunk.lang,
                    "source_uri": _source_uri(chunk.meta_json),
                    "text": chunk.text,
                }
                payload = {k: v for k, v in payload.items() if v is not None}

                qc.upsert_vector(
                    character_id=chunk.character_id,
                    scope=chunk.scope,
                    point_id=chunk.chunk_id,
                    vector=vector,
                    payload=payload,
                )
                total_indexed += 1

            print(f"scope={target_scope} character={cid} indexed={len(items)}")

    print(f"done indexed={total_indexed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex vectors from SQL chunks")
    parser.add_argument("--character-id", help="Filter by character_id")
    parser.add_argument(
        "--scope",
        choices=("global", "private", "both"),
        default="both",
        help="Scope to reindex",
    )
    parser.add_argument("--user-id", help="Optional filter for private scope")
    parser.add_argument("--limit", type=int, help="Max number of chunks per scope")
    parser.add_argument("--reset", action="store_true", help="Drop collection(s) before reindex")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no write")
    args = parser.parse_args()

    async def _run() -> None:
        try:
            await reindex(
                character_id=args.character_id,
                scope=args.scope,
                user_id=args.user_id,
                limit=args.limit,
                reset=args.reset,
                dry_run=args.dry_run,
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()

