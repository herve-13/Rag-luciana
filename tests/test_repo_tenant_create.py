from __future__ import annotations

import pytest

from chatfriends_retrieval.db import repo


class _DummyDb:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_create_tenant_sets_label_from_name():
    db = _DummyDb()

    tenant = await repo.create_tenant(
        db,
        tenant_id="sportif",
        name="Sportif",
        description="Client Sportif",
        status="active",
        meta_json={"default_assistant_id": "zidane"},
    )

    assert db.flushed is True
    assert db.added == [tenant]
    assert tenant.tenant_id == "sportif"
    assert tenant.label == "Sportif"
    assert tenant.name == "Sportif"

