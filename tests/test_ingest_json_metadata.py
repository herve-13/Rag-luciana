from __future__ import annotations

import pytest

from rag_luciana.ingest import ingest_json


@pytest.mark.asyncio
async def test_ingest_json_document_copies_metadata_to_vector_payload(monkeypatch):
    captured: dict = {}

    async def _fake_embed_text(text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def _fake_upsert_chunk(*args, **kwargs):
        captured["repo_meta_json"] = kwargs.get("meta_json")

    def _fake_ensure_collection(assistant_id: str | None = None, scope: str = "", vector_size: int = 768, tenant_id: str | None = None, **kwargs) -> None:
        captured["collection"] = (tenant_id, assistant_id or kwargs.get("character_id"), scope, vector_size)

    def _fake_upsert_vector(*, payload: dict, **_kwargs) -> None:
        captured["payload"] = payload

    monkeypatch.setattr(ingest_json, "embed_text", _fake_embed_text)
    monkeypatch.setattr(ingest_json.repo, "upsert_chunk", _fake_upsert_chunk)
    monkeypatch.setattr(ingest_json.qc, "ensure_collection", _fake_ensure_collection)
    monkeypatch.setattr(ingest_json.qc, "upsert_vector", _fake_upsert_vector)

    count = await ingest_json.ingest_json_document(
        db=None,
        tenant_id="herve",
        assistant_id="luciana",
        scope="private",
        user_id="herve",
        doc_id="mem_1",
        doc_version=1,
        source_uri="internal://simple-memory/mem_1",
        kind=None,
        tags=None,
        bucket="persona",
        subject="luciana",
        canonical=True,
        source="seed",
        metadata={"memory_id": "mem_1"},
        lang=None,
        data=["Luciana est nee a Florence."],
        chunk_max_length=256,
        chunk_overlap=0,
    )

    assert count == 1
    assert captured["collection"][0] == "herve"
    assert captured["payload"]["tenant_id"] == "herve"
    assert captured["payload"]["assistant_id"] == "luciana"
    assert captured["payload"]["memory_id"] == "mem_1"
    assert captured["payload"]["bucket"] == "persona"
    assert captured["payload"]["subject"] == "luciana"
    assert captured["repo_meta_json"]["memory_id"] == "mem_1"


@pytest.mark.asyncio
async def test_ingest_json_document_simple_records_keep_simple_metadata(monkeypatch):
    captured: dict = {}

    async def _fake_embed_text(text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def _fake_upsert_chunk(*args, **kwargs):
        captured.setdefault("repo_meta_json", []).append(kwargs.get("meta_json"))

    def _fake_ensure_collection(assistant_id: str | None = None, scope: str = "", vector_size: int = 768, tenant_id: str | None = None, **kwargs) -> None:
        captured["collection"] = (tenant_id, assistant_id or kwargs.get("character_id"), scope, vector_size)

    def _fake_upsert_vector(*, payload: dict, **_kwargs) -> None:
        captured.setdefault("payloads", []).append(payload)

    monkeypatch.setattr(ingest_json, "embed_text", _fake_embed_text)
    monkeypatch.setattr(ingest_json.repo, "upsert_chunk", _fake_upsert_chunk)
    monkeypatch.setattr(ingest_json.qc, "ensure_collection", _fake_ensure_collection)
    monkeypatch.setattr(ingest_json.qc, "upsert_vector", _fake_upsert_vector)

    count = await ingest_json.ingest_json_document(
        db=None,
        tenant_id="herve",
        assistant_id="luciana",
        scope="private",
        user_id="herve",
        doc_id="simple_1",
        doc_version=1,
        source_uri=None,
        kind=None,
        tags=None,
        bucket="persona",
        subject="luciana",
        canonical=True,
        source="seed",
        metadata=None,
        lang=None,
        data=["Luciana est nee a Florence.", "Son pere est italien."],
        chunk_max_length=256,
        chunk_overlap=0,
    )

    assert count == 2
    assert captured["collection"][0] == "herve"
    assert captured["payloads"][0]["tenant_id"] == "herve"
    assert captured["payloads"][0]["assistant_id"] == "luciana"
    assert captured["payloads"][0]["bucket"] == "persona"
    assert captured["payloads"][0]["subject"] == "luciana"
    assert captured["payloads"][0]["canonical"] is True
    assert captured["payloads"][0]["source"] == "seed"
    assert captured["repo_meta_json"][0]["bucket"] == "persona"
