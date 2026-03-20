from __future__ import annotations

import pytest

from rag_luciana.api import query_router
from rag_luciana.api.schemas import QueryFilters, QueryRequest


@pytest.mark.asyncio
async def test_query_router_forwards_metadata_filters(monkeypatch):
    recorded: dict = {}

    async def _fake_retrieve(**kwargs):
        recorded.update(kwargs)
        return []

    monkeypatch.setattr(query_router, "retrieve", _fake_retrieve)

    req = QueryRequest(
        character_id="luciana",
        user_id="herve",
        query="florence",
        top_k=4,
        scope="private",
        filters=QueryFilters(
            kinds=["atomic_memory"],
            metadata={
                "owner": "assistant",
                "type": "fact",
                "categorie": "identite",
                "json_path": "$.retrieval_text",
            },
        ),
    )

    resp = await query_router.query(req)

    assert resp.results == []
    assert recorded["filters"] == {
        "kind": ["atomic_memory"],
        "owner": "assistant",
        "type": "fact",
        "categorie": "identite",
        "json_path": "$.retrieval_text",
    }
    assert recorded["sparse_query"] is None
