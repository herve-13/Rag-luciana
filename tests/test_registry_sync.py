from __future__ import annotations

from types import SimpleNamespace

import pytest

from chatfriends_retrieval.db import repo


@pytest.mark.asyncio
async def test_sync_assistant_registry_from_characters_bootstraps_default_tenant(monkeypatch):
    captured: dict[str, object] = {"offsets": []}

    async def fake_ensure_tenant(db, **kwargs):
        captured["tenant_id"] = kwargs["tenant_id"]
        return None

    async def fake_list_characters(db, *, limit: int, offset: int, status=None):
        captured["offsets"].append(offset)
        if offset == 0:
            return [
                SimpleNamespace(character_id="luciana", name="Luciana", description=None, status="active", meta_json={}),
                SimpleNamespace(character_id="marina", name="Marina", description=None, status="active", meta_json={}),
            ], 2
        return [], 2

    async def fake_sync_assistant_from_character(db, **kwargs):
        captured.setdefault("synced", []).append(kwargs["character"].character_id)
        return None

    async def fake_list_legacy_assistant_ids(db, **kwargs):
        return []

    monkeypatch.setattr(repo, "ensure_tenant", fake_ensure_tenant)
    monkeypatch.setattr(repo, "list_characters", fake_list_characters)
    monkeypatch.setattr(repo, "list_legacy_assistant_ids", fake_list_legacy_assistant_ids)
    monkeypatch.setattr(repo, "sync_assistant_from_character", fake_sync_assistant_from_character)

    result = await repo.sync_assistant_registry_from_characters(object(), tenant_id="tenant_ops", page_size=50)

    assert captured["tenant_id"] == "tenant_ops"
    assert captured["offsets"] == [0]
    assert captured["synced"] == ["luciana", "marina"]
    assert result == {"tenant_id": "tenant_ops", "synced_count": 2}


@pytest.mark.asyncio
async def test_sync_assistant_registry_bootstraps_from_legacy_ids(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_ensure_tenant(db, **kwargs):
        captured["tenant_id"] = kwargs["tenant_id"]
        return None

    async def fake_list_characters(db, *, limit: int, offset: int, status=None):
        return [], 0

    async def fake_list_legacy_assistant_ids(db, **kwargs):
        return ["luciana", "marina"]

    async def fake_get_assistant(db, **kwargs):
        return None

    async def fake_upsert_assistant(db, **kwargs):
        captured.setdefault("upserts", []).append(kwargs["assistant_id"])
        return None

    monkeypatch.setattr(repo, "ensure_tenant", fake_ensure_tenant)
    monkeypatch.setattr(repo, "list_characters", fake_list_characters)
    monkeypatch.setattr(repo, "list_legacy_assistant_ids", fake_list_legacy_assistant_ids)
    monkeypatch.setattr(repo, "get_assistant", fake_get_assistant)
    monkeypatch.setattr(repo, "upsert_assistant", fake_upsert_assistant)

    result = await repo.sync_assistant_registry_from_characters(object(), tenant_id="tenant_ops", page_size=50)

    assert captured["tenant_id"] == "tenant_ops"
    assert sorted(captured["upserts"]) == ["luciana", "marina"]
    assert result == {"tenant_id": "tenant_ops", "synced_count": 2}

