#!/usr/bin/env python3
"""Export retrieval Qdrant collections to a readable Markdown file."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chatfriends_retrieval.clients.qdrant_client import get_qdrant_client


def _iter_retrieval_collection_names(*, include_global: bool, include_private: bool) -> list[str]:
    client = get_qdrant_client()
    names = [c.name for c in client.get_collections().collections if str(c.name).startswith("rag_")]
    allowed_scopes = set()
    if include_global:
        allowed_scopes.add("global")
    if include_private:
        allowed_scopes.add("private")
    return [name for name in sorted(names) if name.rsplit("_", 1)[-1] in allowed_scopes]


def _scroll_points(collection_name: str) -> list[Any]:
    client = get_qdrant_client()
    points: list[Any] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection_name,
            with_payload=True,
            with_vectors=False,
            limit=128,
            offset=offset,
        )
        points.extend(batch or [])
        if offset is None:
            break
    return points


def _markdown_for_collection(collection_name: str) -> str:
    points = _scroll_points(collection_name)
    lines = [f"## {collection_name}", ""]
    if not points:
        lines.extend(["_Aucun point_", ""])
        return "\n".join(lines)
    facts: list[str] = []
    for point in points:
        payload = dict(getattr(point, "payload", {}) or {})
        text = str(payload.get("text", "") or "").strip()
        if text:
            facts.append(text)
    if not facts:
        lines.extend(["_Aucun fait_", ""])
        return "\n".join(lines)
    for fact in facts:
        lines.append(f"- {fact}")
    lines.append("")
    return "\n".join(lines)


def export_markdown(*, output_path: Path, include_global: bool, include_private: bool) -> Path:
    collection_names = _iter_retrieval_collection_names(
        include_global=include_global,
        include_private=include_private,
    )
    lines = [
        "# ChatFriends Retrieval Qdrant Vectors Dump",
        "",
        f"- collections: {len(collection_names)}",
        "",
    ]
    for collection_name in collection_names:
        lines.append(_markdown_for_collection(collection_name))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export retrieval Qdrant vectors to Markdown.")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent.parent / "docs" / "retrieval_qdrant_vectors_dump.md"),
        help="Destination Markdown path",
    )
    parser.add_argument("--global", dest="include_global", action="store_true", default=True)
    parser.add_argument("--no-global", dest="include_global", action="store_false")
    parser.add_argument("--private", dest="include_private", action="store_true", default=True)
    parser.add_argument("--no-private", dest="include_private", action="store_false")
    args = parser.parse_args()

    path = export_markdown(
        output_path=Path(args.output),
        include_global=bool(args.include_global),
        include_private=bool(args.include_private),
    )
    print(path)


if __name__ == "__main__":
    main()

