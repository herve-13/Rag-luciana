from __future__ import annotations

import pytest

from rag_luciana.ingest import ingest_json
from rag_luciana.core.sparse_embeddings import SparseEmbedding


@pytest.mark.asyncio
async def test_ingest_json_document_copies_metadata_to_vector_payload(monkeypatch):
    captured: dict = {}

    async def _fake_embed_text(text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def _fake_embed_sparse_text(text: str) -> SparseEmbedding | None:
        return SparseEmbedding(indices=[1], values=[1.0], readable_terms=[{"term": "luciana", "weight": 1.0}])

    async def _fake_upsert_chunk(*args, **kwargs):
        captured["repo_meta_json"] = kwargs.get("meta_json")

    def _fake_chunk_text(text: str, max_length: int, overlap: int) -> list[str]:
        return [text]

    def _fake_ensure_collection(character_id: str, scope: str, vector_size: int = 768) -> None:
        captured["collection"] = (character_id, scope, vector_size)

    def _fake_upsert_vector(*, payload: dict, **_kwargs) -> None:
        captured["payload"] = payload

    monkeypatch.setattr(ingest_json, "embed_text", _fake_embed_text)
    monkeypatch.setattr(ingest_json, "embed_sparse_text", _fake_embed_sparse_text)
    monkeypatch.setattr(ingest_json, "chunk_text", _fake_chunk_text)
    monkeypatch.setattr(ingest_json.repo, "upsert_chunk", _fake_upsert_chunk)
    monkeypatch.setattr(ingest_json.qc, "ensure_collection", _fake_ensure_collection)
    monkeypatch.setattr(ingest_json.qc, "upsert_vector", _fake_upsert_vector)

    count = await ingest_json.ingest_json_document(
        db=None,
        character_id="luciana",
        scope="private",
        user_id="herve",
        doc_id="mem_1",
        doc_version=1,
        source_uri="internal://memory/mem_1",
        kind="atomic_memory",
        tags=["memory", "atomic"],
        metadata={
            "memory_id": "mem_1",
            "owner": "assistant",
            "type": "fact",
            "categorie": "identite",
            "retrieval_role": "durable_user_memory",
        },
        lang=None,
        data={"retrieval_text": "Luciana est nee a Florence."},
        chunk_max_length=256,
        chunk_overlap=0,
    )

    assert count == 1
    assert captured["payload"]["memory_id"] == "mem_1"
    assert captured["payload"]["owner"] == "assistant"
    assert captured["payload"]["type"] == "fact"
    assert captured["payload"]["categorie"] == "identite"
    assert captured["payload"]["retrieval_role"] == "durable_user_memory"
    assert captured["repo_meta_json"]["memory_id"] == "mem_1"
