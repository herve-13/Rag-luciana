from __future__ import annotations

from pathlib import Path

from scripts.export_qdrant_markdown import export_markdown


class _Collections:
    def __init__(self, names: list[str]) -> None:
        self.collections = [type("C", (), {"name": n})() for n in names]


class _Point:
    def __init__(self, point_id, payload):
        self.id = point_id
        self.payload = payload


class _Client:
    def get_collections(self):
        return _Collections(["rag_global", "rag_private", "rag_other_global"])

    def scroll(self, *, collection_name, with_payload, with_vectors, limit, offset=None):
        payload = {
            "scope": "private" if collection_name.endswith("private") else "global",
            "user_id": "u1" if collection_name.endswith("private") else None,
            "doc_id": "doc-1",
            "doc_version": 1,
            "chunk_id": "chunk-1",
            "kind": "memory",
            "json_path": "$.items[0]",
            "tags": ["tag-a"],
            "source_uri": "memory://test",
            "text": f"payload for {collection_name}",
        }
        return ([_Point("p1", payload)], None)


def test_export_markdown_includes_global_and_private(monkeypatch, tmp_path: Path):
    from scripts import export_qdrant_markdown as module

    monkeypatch.setattr(module, "get_qdrant_client", lambda: _Client())
    output = tmp_path / "retrieval.md"
    export_markdown(output_path=output, include_global=True, include_private=True)
    content = output.read_text(encoding="utf-8")
    assert "## rag_global" in content
    assert "## rag_private" in content
    assert "payload for rag_private" in content
