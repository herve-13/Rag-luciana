from __future__ import annotations

import pytest

from chatfriends_retrieval.api import query_router
from chatfriends_retrieval.api.schemas import QueryFilters, QueryRequest


@pytest.mark.asyncio
async def test_query_router_forwards_metadata_filters(monkeypatch):
    recorded: dict = {}

    async def _fake_retrieve(**kwargs):
        recorded.update(kwargs)
        return []

    monkeypatch.setattr(query_router, "retrieve", _fake_retrieve)

    req = QueryRequest(
        assistant_id="luciana",
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
    assert resp.tenant_id == "herve"
    assert resp.assistant_id == "luciana"
    assert recorded["tenant_id"] == "herve"
    assert recorded["filters"] == {
        "kind": ["atomic_memory"],
        "owner": "assistant",
        "type": "fact",
        "categorie": "identite",
        "json_path": "$.retrieval_text",
    }
    assert recorded["sparse_query"] is None


@pytest.mark.asyncio
async def test_query_router_forwards_simple_filters(monkeypatch):
    recorded: dict = {}

    async def _fake_retrieve(**kwargs):
        recorded.update(kwargs)
        return []

    monkeypatch.setattr(query_router, "retrieve", _fake_retrieve)

    req = QueryRequest(
        assistant_id="luciana",
        user_id="herve",
        query="qui est ton pere",
        top_k=4,
        scope="private",
        filters=QueryFilters(
            kinds=["simple_memory"],
            bucket=["persona"],
            subject="luciana",
            canonical=True,
            source=["seed", "approved"],
        ),
    )

    resp = await query_router.query(req)

    assert resp.results == []
    assert resp.tenant_id == "herve"
    assert resp.assistant_id == "luciana"
    assert recorded["tenant_id"] == "herve"
    assert recorded["filters"] == {
        "kind": ["simple_memory"],
        "bucket": ["persona"],
        "subject": "luciana",
        "canonical": True,
        "source": ["seed", "approved"],
    }
    assert recorded["sparse_query"] is None


@pytest.mark.asyncio
async def test_query_router_forwards_sparse_query(monkeypatch):
    recorded: dict = {}

    async def _fake_retrieve(**kwargs):
        recorded.update(kwargs)
        return []

    monkeypatch.setattr(query_router, "retrieve", _fake_retrieve)

    req = QueryRequest(
        assistant_id="luciana",
        user_id="herve",
        query="type d'ingenierie etudie par Matteo",
        top_k=4,
        scope="private",
        sparse_query={"terms": [{"term": "ingenierie", "weight": 1.0}, {"term": "Matteo", "weight": 0.8}]},
    )

    resp = await query_router.query(req)

    assert resp.results == []
    assert resp.tenant_id == "herve"
    assert resp.assistant_id == "luciana"
    assert recorded["tenant_id"] == "herve"
    assert recorded["sparse_query"] == {
        "terms": [
            {"term": "ingenierie", "weight": 1.0},
            {"term": "Matteo", "weight": 0.8},
        ]
    }


@pytest.mark.asyncio
async def test_query_router_returns_display_score_fields(monkeypatch):
    async def _fake_retrieve(**_kwargs):
        return [
            query_router.ChunkResult.model_construct(
                chunk_id="c1",
                doc_id="d1",
                score=0.0134,
                score_source="hybrid_rrf",
                display_score=84,
                display_band="fort",
                text="memoire",
                metadata={"dense_score": 0.45},
            )
        ]

    monkeypatch.setattr(query_router, "retrieve", _fake_retrieve)

    req = QueryRequest(
        assistant_id="luciana",
        user_id="herve",
        query="memoire",
        top_k=1,
        scope="private",
    )

    resp = await query_router.query(req)

    assert resp.tenant_id == "herve"
    assert resp.assistant_id == "luciana"
    assert resp.results[0].score_source == "hybrid_rrf"
    assert resp.results[0].display_score == 84
    assert resp.results[0].display_band == "fort"

