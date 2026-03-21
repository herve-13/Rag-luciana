#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


async def _run(character_id: str | None) -> int:
    project_root = _project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from rag_luciana.clients.qdrant_client import collection_name, get_qdrant_client
    from rag_luciana.db.session import async_session_factory

    async with async_session_factory() as db:
        result_chunks = await db.execute(text("SELECT COUNT(*) FROM chunks"))
        chunks_deleted = int(result_chunks.scalar() or 0)
        result_runs = await db.execute(text("SELECT COUNT(*) FROM ingestion_runs"))
        runs_deleted = int(result_runs.scalar() or 0)
        await db.execute(text("DELETE FROM chunks"))
        await db.execute(text("DELETE FROM ingestion_runs"))
        await db.commit()

    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    targets: list[str]
    if character_id:
        targets = [collection_name(character_id, "private"), collection_name(character_id, "global")]
    else:
        targets = sorted(name for name in existing if name.startswith("rag_"))
    collections_deleted = 0
    for name in targets:
        if name in existing:
            client.delete_collection(name)
            collections_deleted += 1
            print(f"deleted_collection: {name}")

    print(f"chunks_deleted: {chunks_deleted}")
    print(f"ingestion_runs_deleted: {runs_deleted}")
    print(f"collections_deleted: {collections_deleted}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Reset simple memory storage in rag-luciana")
    parser.add_argument("--character-id", default=None, help="Optional character_id to target in Qdrant")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.character_id))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
