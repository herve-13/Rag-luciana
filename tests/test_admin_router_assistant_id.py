from __future__ import annotations

from datetime import datetime, UTC
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chatfriends_retrieval.api import admin_router as admin_module
from chatfriends_retrieval.api.admin_router import router as admin_router
from chatfriends_retrieval.api.deps import _get_db, verify_admin_key


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


def test_list_conversations_accepts_assistant_id_query(monkeypatch, client: TestClient):
    captured: dict[str, object] = {}
    now = _now()

    async def fake_list_conversations(db, **kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                conversation_id="conv_1",
                tenant_id="tenant_ops",
                character_id="luciana",
                user_id="herve",
                status="active",
                meta_json={},
                created_at=now,
                updated_at=now,
            )
        ], 1

    monkeypatch.setattr(admin_module.repo, "list_conversations", fake_list_conversations)

    response = client.get(
        "/admin/conversations",
        params={"tenant_id": "tenant_ops", "assistant_id": "luciana", "limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["tenant_id"] == "tenant_ops"
    assert captured["character_id"] == "luciana"
    assert payload["items"][0]["tenant_id"] == "tenant_ops"
    assert payload["items"][0]["assistant_id"] == "luciana"
    assert payload["items"][0]["character_id"] == "luciana"


def test_get_relation_accepts_assistant_alias_route(monkeypatch, client: TestClient):
    now = _now()

    async def fake_get_relation(db, *, tenant_id: str, user_id: str, character_id: str):
        assert tenant_id == "tenant_ops"
        assert user_id == "herve"
        assert character_id == "luciana"
        return SimpleNamespace(
            user_id=user_id,
            tenant_id=tenant_id,
            character_id=character_id,
            version="1.0",
            relation_state_json={"trust": 0.2},
            interaction_stats_json={"total_messages": 3, "last_interaction": now},
            flags_json={"favorite": False, "blocked": False},
            meta_json={"created_at": now, "last_updated": now},
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(admin_module.repo, "get_user_agent_relation", fake_get_relation)

    response = client.get(
        "/admin/relations/herve/assistants/luciana",
        params={"tenant_id": "tenant_ops"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "tenant_ops"
    assert payload["assistant_id"] == "luciana"
    assert payload["agent_id"] == "luciana"


def test_append_messages_accepts_assistant_id_in_body(monkeypatch, client: TestClient):
    now = _now()
    create_calls: list[dict[str, object]] = []
    touch_calls: list[dict[str, object]] = []

    async def fake_get_conversation(
        db,
        conversation_id: str,
        tenant_id: str | None = None,
        character_id: str | None = None,
    ):
        assert conversation_id == "conv_1"
        assert tenant_id == "tenant_ops"
        assert character_id == "luciana"
        return SimpleNamespace(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            character_id=character_id,
            user_id="herve",
            status="active",
            meta_json={"seed": True},
        )

    async def fake_get_last_turn_index(db, *, conversation_id: str, tenant_id: str, character_id: str):
        assert conversation_id == "conv_1"
        assert tenant_id == "tenant_ops"
        assert character_id == "luciana"
        return 4

    async def fake_create_message(db, **kwargs):
        create_calls.append(kwargs)
        return SimpleNamespace(
            message_id=kwargs["message_id"],
            conversation_id=kwargs["conversation_id"],
            tenant_id=kwargs["tenant_id"],
            character_id=kwargs["character_id"],
            user_id=kwargs["user_id"],
            turn_index=kwargs["turn_index"],
            role=kwargs["role"],
            content=kwargs["content"],
            meta_json=kwargs.get("meta_json"),
            ts=kwargs.get("ts") or now,
        )

    async def fake_upsert_conversation(db, **kwargs):
        touch_calls.append(kwargs)
        return SimpleNamespace(
            conversation_id=kwargs["conversation_id"],
            tenant_id=kwargs["tenant_id"],
            character_id=kwargs["character_id"],
            user_id=kwargs["user_id"],
            status=kwargs["status"],
            meta_json=kwargs.get("meta_json"),
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(admin_module.repo, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(admin_module.repo, "get_last_turn_index", fake_get_last_turn_index)
    monkeypatch.setattr(admin_module.repo, "create_message", fake_create_message)
    monkeypatch.setattr(admin_module.repo, "upsert_conversation", fake_upsert_conversation)

    response = client.post(
        "/admin/conversations/conv_1/messages",
        json={
            "conversation_id": "conv_1",
            "tenant_id": "tenant_ops",
            "assistant_id": "luciana",
            "user_id": "herve",
            "messages": [{"role": "assistant", "content": "Salut."}],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert create_calls[0]["tenant_id"] == "tenant_ops"
    assert create_calls[0]["character_id"] == "luciana"
    assert touch_calls[-1]["tenant_id"] == "tenant_ops"
    assert touch_calls[-1]["character_id"] == "luciana"
    assert payload["items"][0]["tenant_id"] == "tenant_ops"
    assert payload["items"][0]["assistant_id"] == "luciana"
    assert payload["items"][0]["character_id"] == "luciana"


def test_upsert_media_asset_accepts_assistant_id_in_body(monkeypatch, client: TestClient):
    captured: dict[str, object] = {}
    now = _now()

    async def fake_upsert_media_asset(db, **kwargs):
        captured.update(kwargs)
        return {
            "id": 7,
            "tenant_id": kwargs["tenant_id"],
            "character_id": kwargs["character_id"],
            "file_url": kwargs["file_url"],
            "title": kwargs.get("title"),
            "description": kwargs.get("description"),
            "required_relationship_level": kwargs.get("required_relationship_level", 1),
            "content_intensity": kwargs.get("content_intensity", "SOFT"),
            "purchase_hearts_cost": kwargs.get("purchase_hearts_cost", 0),
            "relation_gain_bonus": kwargs.get("relation_gain_bonus", 0),
            "is_purchasable": kwargs.get("is_purchasable", False),
            "media_kind": kwargs.get("media_kind", "photo"),
            "sort_order": kwargs.get("sort_order", 0),
            "is_active": kwargs.get("is_active", True),
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(admin_module.repo, "upsert_media_asset", fake_upsert_media_asset)

    response = client.post(
        "/admin/media/assets",
        json={
            "tenant_id": "tenant_ops",
            "assistant_id": "luciana",
            "file_url": "/media/test.png",
            "title": "Test",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert captured["tenant_id"] == "tenant_ops"
    assert captured["character_id"] == "luciana"
    assert payload["tenant_id"] == "tenant_ops"
    assert payload["assistant_id"] == "luciana"
    assert payload["character_id"] == "luciana"


def test_upsert_media_asset_accepts_audio_media_kind(monkeypatch, client: TestClient):
    captured: dict[str, object] = {}
    now = _now()

    async def fake_upsert_media_asset(db, **kwargs):
        captured.update(kwargs)
        return {
            "id": 8,
            "tenant_id": kwargs["tenant_id"],
            "character_id": kwargs["character_id"],
            "file_url": kwargs["file_url"],
            "title": kwargs.get("title"),
            "description": kwargs.get("description"),
            "required_relationship_level": kwargs.get("required_relationship_level", 1),
            "content_intensity": kwargs.get("content_intensity", "SOFT"),
            "purchase_hearts_cost": kwargs.get("purchase_hearts_cost", 0),
            "relation_gain_bonus": kwargs.get("relation_gain_bonus", 0),
            "is_purchasable": kwargs.get("is_purchasable", False),
            "media_kind": kwargs.get("media_kind", "audio"),
            "sort_order": kwargs.get("sort_order", 0),
            "is_active": kwargs.get("is_active", True),
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(admin_module.repo, "upsert_media_asset", fake_upsert_media_asset)

    response = client.post(
        "/admin/media/assets",
        json={
            "tenant_id": "tenant_ops",
            "assistant_id": "mozart",
            "file_url": "source/audio/requiem.mp3",
            "title": "Requiem",
            "media_kind": "audio",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert captured["tenant_id"] == "tenant_ops"
    assert captured["character_id"] == "mozart"
    assert captured["media_kind"] == "audio"
    assert payload["media_kind"] == "audio"


def test_delete_vectors_accepts_assistant_id_in_body(monkeypatch, client: TestClient):
    captured: dict[str, object] = {}

    def fake_delete_by_filter(*, tenant_id: str | None = None, character_id: str, scope: str, filters: dict):
        captured["tenant_id"] = tenant_id
        captured["character_id"] = character_id
        captured["scope"] = scope
        captured["filters"] = filters

    monkeypatch.setattr(admin_module, "delete_by_filter", fake_delete_by_filter)

    response = client.post(
        "/admin/vectors/delete",
        json={
            "assistant_id": "luciana",
            "scope": "private",
            "filters": {"user_id": "herve", "doc_id": "mem_1"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["tenant_id"] == "herve"
    assert captured["character_id"] == "luciana"
    assert payload["tenant_id"] == "herve"
    assert payload["assistant_id"] == "luciana"
    assert payload["character_id"] == "luciana"

