from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_luciana.api import gifts_router as gifts_module
from rag_luciana.api.deps import _get_db
from rag_luciana.api.gifts_router import router as gifts_router


def _now() -> datetime:
    return datetime.now(UTC)


class _FakeDb:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def test_purchase_gift_forwards_tenant_id(monkeypatch):
    app = FastAPI()
    app.include_router(gifts_router)

    async def fake_db():
        yield _FakeDb()

    app.dependency_overrides[_get_db] = fake_db
    captured: dict[str, object] = {}

    async def fake_purchase_gift(db, **kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "bond_bonus": 2,
            "hearts_remaining": 88,
            "gift_name": "Rose",
            "category": "cute",
            "error": None,
        }

    monkeypatch.setattr(gifts_module.repo, "purchase_gift", fake_purchase_gift)

    with TestClient(app) as client:
        response = client.post(
            "/gifts/purchase",
            json={
                "tenant_id": "tenant_ops",
                "user_id": "herve",
                "assistant_id": "luciana",
                "gift_id": 4,
            },
        )

    assert response.status_code == 200
    assert captured["tenant_id"] == "tenant_ops"
    assert captured["character_id"] == "luciana"


def test_gift_history_returns_row_tenant_id(monkeypatch):
    app = FastAPI()
    app.include_router(gifts_router)

    async def fake_db():
        yield _FakeDb()

    app.dependency_overrides[_get_db] = fake_db
    now = _now()
    captured: dict[str, object] = {}

    async def fake_list_history(db, **kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                id=1,
                tenant_id="tenant_ops",
                user_id="herve",
                character_id="luciana",
                gift_id=4,
                purchased_at=now,
            )
        ]

    monkeypatch.setattr(gifts_module.repo, "list_gift_history", fake_list_history)

    with TestClient(app) as client:
        response = client.get(
            "/gifts/history/herve/assistants/luciana",
            params={"tenant_id": "tenant_ops"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert captured["tenant_id"] == "tenant_ops"
    assert payload[0]["tenant_id"] == "tenant_ops"
