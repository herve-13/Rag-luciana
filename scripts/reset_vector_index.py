#!/usr/bin/env python3
"""Reset Qdrant vector collections used by RAG Luciana.

Examples:
  python scripts/reset_vector_index.py --all-rag --create
  python scripts/reset_vector_index.py --character-id npc_jean --scope global --create
  python scripts/reset_vector_index.py --all-rag --dry-run
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable

from qdrant_client import models

from chatfriends_retrieval.clients.qdrant_client import collection_name, get_qdrant_client

SCOPES = ("global", "private")


def _target_collections(character_ids: Iterable[str] | None, scope: str) -> set[str]:
    if not character_ids:
        return set()
    if scope == "both":
        return {
            collection_name(character_id, s)
            for character_id in character_ids
            for s in SCOPES
        }
    return {collection_name(character_id, scope) for character_id in character_ids}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset Qdrant collections")
    parser.add_argument(
        "--character-id",
        action="append",
        default=[],
        help="Character id to target (repeatable)",
    )
    parser.add_argument(
        "--scope",
        choices=("global", "private", "both"),
        default="both",
        help="Target scope for --character-id",
    )
    parser.add_argument(
        "--all-rag",
        action="store_true",
        help="Drop all collections prefixed with 'rag_'",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Recreate targeted collections after deletion",
    )
    parser.add_argument(
        "--vector-size",
        type=int,
        default=1024,
        help="Vector size when using --create (default: 1024)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")

    args = parser.parse_args()

    if not args.all_rag and not args.character_id:
        parser.error("Specify --all-rag or at least one --character-id")

    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}

    if args.all_rag:
        targets = {name for name in existing if name.startswith("rag_")}
    else:
        targets = _target_collections(args.character_id, args.scope)

    if not targets:
        print("No target collections found.")
        return

    for name in sorted(targets):
        if name in existing:
            if args.dry_run:
                print(f"[dry-run] delete {name}")
            else:
                client.delete_collection(name)
                print(f"deleted {name}")
        else:
            print(f"skip (missing) {name}")

    if args.create:
        for name in sorted(targets):
            if args.dry_run:
                print(f"[dry-run] create {name} size={args.vector_size}")
            else:
                client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=args.vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                print(f"created {name} size={args.vector_size}")


if __name__ == "__main__":
    main()

