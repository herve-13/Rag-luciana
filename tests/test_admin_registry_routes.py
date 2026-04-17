from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_luciana.api import admin_router as admin_module
from rag_luciana.api.admin_router import router as admin_router
from rag_luciana.api.deps import _get_db, verify_admin_key


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(admin_router)

    async def fake_db():
        yield object()

    async def fake_admin():
        return None

    app.dependency_overrides[_get_db] = fake_db
    app.dependency_overrides[verify_admin_key] = fake_admin
    with TestClient(app) as test_client:
        yield test_client


def test_list_tenants_returns_registry_rows(monkeypatch, client: TestClient):
    now = _now()
    captured: dict[str, object] = {}

    async def fake_list_tenants(db, **kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                tenant_id="tenant_ops",
                name="Tenant Ops",
                description="Client principal",
                status="active",
                meta_json={"seeded": True},
                created_at=now,
                updated_at=now,
            )
        ], 1

    monkeypatch.setattr(admin_module.repo, "list_tenants", fake_list_tenants)

    response = client.get(
        "/admin/tenants",
        params={"status": "active", "limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["status"] == "active"
    assert payload["items"][0]["tenant_id"] == "tenant_ops"
    assert payload["items"][0]["name"] == "Tenant Ops"


def test_list_assistants_scoped_by_tenant(monkeypatch, client: TestClient):
    now = _now()
    captured: dict[str, object] = {}

    async def fake_list_assistants(db, **kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                tenant_id="tenant_ops",
                assistant_id="luciana",
                character_id="luciana",
                name="Luciana",
                description="Assistant principal",
                status="active",
                meta_json={"legacy_character_id": "luciana"},
                created_at=now,
                updated_at=now,
            )
        ], 1

    monkeypatch.setattr(admin_module.repo, "list_assistants", fake_list_assistants)

    response = client.get(
        "/admin/assistants",
        params={"tenant_id": "tenant_ops", "status": "active", "limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["tenant_id"] == "tenant_ops"
    assert captured["status"] == "active"
    assert payload["items"][0]["tenant_id"] == "tenant_ops"
    assert payload["items"][0]["assistant_id"] == "luciana"
    assert "character_id" not in payload["items"][0]


def test_sync_assistants_from_characters_route(monkeypatch, client: TestClient):
    captured: dict[str, object] = {}

    async def fake_sync(db, **kwargs):
        captured.update(kwargs)
        return {"tenant_id": "tenant_ops", "synced_count": 3}

    monkeypatch.setattr(
        admin_module.repo,
        "sync_assistant_registry_from_characters",
        fake_sync,
    )

    response = client.post(
        "/admin/assistants/sync-from-characters",
        params={"tenant_id": "tenant_ops"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["tenant_id"] == "tenant_ops"
    assert payload["tenant_id"] == "tenant_ops"
    assert payload["synced_count"] == 3


def test_create_character_syncs_assistant_registry(monkeypatch, client: TestClient):
    now = _now()
    captured: dict[str, object] = {}

    async def fake_get_character(db, character_id: str):
        return None

    async def fake_create_character(db, **kwargs):
        return SimpleNamespace(
            character_id=kwargs["character_id"],
            name=kwargs["name"],
            description=kwargs.get("description"),
            status="active",
            meta_json=kwargs.get("meta_json"),
            created_at=now,
            updated_at=now,
        )

    async def fake_sync_assistant_from_character(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            tenant_id=kwargs["tenant_id"],
            assistant_id=kwargs["character"].character_id,
            character_id=kwargs["character"].character_id,
        )

    monkeypatch.setattr(admin_module.repo, "get_character", fake_get_character)
    monkeypatch.setattr(admin_module.repo, "create_character", fake_create_character)
    monkeypatch.setattr(
        admin_module.repo,
        "sync_assistant_from_character",
        fake_sync_assistant_from_character,
    )

    response = client.post(
        "/admin/characters",
        json={
            "character_id": "luciana",
            "name": "Luciana",
            "description": "Assistant principal",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert captured["tenant_id"] == "herve"
    assert captured["character"].character_id == "luciana"
    assert payload["character_id"] == "luciana"
