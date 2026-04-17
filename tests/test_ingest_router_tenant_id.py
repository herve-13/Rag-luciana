from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_luciana.api import ingest_router as ingest_module
from rag_luciana.api.deps import _get_db, verify_admin_key
from rag_luciana.api.ingest_router import router as ingest_router


def test_ingest_forwards_tenant_id_to_storage(monkeypatch):
    app = FastAPI()
    app.include_router(ingest_router)

    async def fake_db():
        yield object()

    async def fake_admin():
        return None

    app.dependency_overrides[_get_db] = fake_db
    app.dependency_overrides[verify_admin_key] = fake_admin

    captured: dict[str, object] = {}

    async def fake_create_ingestion_run(db, **kwargs):
        captured["create_run"] = kwargs

    async def fake_finish_ingestion_run(db, **kwargs):
        captured["finish_run"] = kwargs

    async def fake_ingest_json_document(db, **kwargs):
        captured["ingest"] = kwargs
        return 3

    monkeypatch.setattr(ingest_module.repo, "create_ingestion_run", fake_create_ingestion_run)
    monkeypatch.setattr(ingest_module.repo, "finish_ingestion_run", fake_finish_ingestion_run)
    monkeypatch.setattr(ingest_module, "ingest_json_document", fake_ingest_json_document)

    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            json={
                "tenant_id": "tenant_ops",
                "assistant_id": "luciana",
                "user_id": "herve",
                "scope": "private",
                "doc_id": "mem_001",
                "doc_version": 1,
                "kind": "simple_memory",
                "data": {"retrieval_text": "memoire test"},
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert captured["create_run"]["tenant_id"] == "tenant_ops"
    assert captured["create_run"]["character_id"] == "luciana"
    assert captured["ingest"]["tenant_id"] == "tenant_ops"
    assert captured["ingest"]["assistant_id"] == "luciana"
    assert captured["finish_run"]["tenant_id"] == "tenant_ops"
    assert captured["finish_run"]["character_id"] == "luciana"
    assert payload["tenant_id"] == "tenant_ops"
    assert payload["assistant_id"] == "luciana"
    assert payload["chunks_count"] == 3
