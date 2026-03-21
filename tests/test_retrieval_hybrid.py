from __future__ import annotations

import pytest

from rag_luciana.core import retrieval as r
from rag_luciana.core.sparse_embeddings import SparseEmbedding


class _Point:
    def __init__(self, score: float, payload: dict):
        self.score = score
        self.payload = payload


@pytest.mark.asyncio
async def test_retrieve_private_hybrid_rrf(monkeypatch):
    monkeypatch.setattr(r, "reranker_enabled", lambda: False)
    monkeypatch.setattr(r, "sparse_enabled", lambda: True)
    monkeypatch.setattr(r.settings, "reranker_candidate_multiplier", 2)
    monkeypatch.setattr(r.settings, "rrf_k_hybrid", 60)
    async def _embed_text(_q):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(r, "embed_text", _embed_text)
    
    async def _embed_sparse(_terms):
        return SparseEmbedding(
            indices=[1, 2, 3],
            values=[0.9, 0.3, 0.2],
            readable_terms=[{"term": "football", "weight": 1.0}],
        )

    monkeypatch.setattr(
        r,
        "embed_sparse_terms_weighted",
        _embed_sparse,
    )

    dense_hits = [
        _Point(
            0.88,
            {
                "chunk_id": "c1",
                "doc_id": "d1",
                "character_id": "luciana",
                "user_id": "u1",
                "text": "j'aime le football",
                "sparse_terms": ["football"],
            },
        ),
        _Point(
            0.72,
            {
                "chunk_id": "c2",
                "doc_id": "d2",
                "character_id": "luciana",
                "user_id": "u1",
                "text": "j'aime les pommes",
                "sparse_terms": ["pommes"],
            },
        ),
    ]
    sparse_hits = [
        _Point(
            0.93,
            {
                "chunk_id": "c1",
                "doc_id": "d1",
                "character_id": "luciana",
                "user_id": "u1",
                "text": "j'aime le football",
                "sparse_terms": ["football"],
            },
        ),
    ]

    monkeypatch.setattr(r.qc, "search_vectors", lambda **_kwargs: dense_hits)
    monkeypatch.setattr(r.qc, "search_sparse_vectors", lambda **_kwargs: sparse_hits)

    debug: dict = {}
    hits = await r.retrieve(
        character_id="luciana",
        query="quels sports j'aime ?",
        scope="private",
        user_id="u1",
        top_k=2,
        sparse_query={"terms": [{"term": "football", "weight": 1.0}]},
        debug_sink=debug,
    )

    assert len(hits) == 2
    assert hits[0].chunk_id == "c1"
    assert hits[0].metadata["dense_score"] == pytest.approx(0.88, rel=1e-5)
    assert hits[0].metadata["sparse_score"] == pytest.approx(0.93, rel=1e-5)
    assert hits[0].metadata["rrf_score"] > hits[1].metadata["rrf_score"]
    assert hits[0].metadata["retrieval_stage"] == "hybrid_rrf"
    assert hits[0].metadata["sparse_contrib_terms"] == ["football"]
    assert "hybrid_debug" in debug
    assert debug["hybrid_debug"]["query_sparse_terms"][0]["term"] == "football"
    assert debug["hybrid_debug"]["sparse_mode"] == "llm_terms"


@pytest.mark.asyncio
async def test_retrieve_disables_sparse_without_terms(monkeypatch):
    monkeypatch.setattr(r, "reranker_enabled", lambda: False)
    monkeypatch.setattr(r, "sparse_enabled", lambda: True)

    async def _embed_text(_q):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(r, "embed_text", _embed_text)
    async def _embed_sparse_text(_query):
        return SparseEmbedding(
            indices=[5, 7],
            values=[0.8, 0.4],
            readable_terms=[{"term": "matteo", "weight": 1.0}],
        )

    monkeypatch.setattr(r, "embed_sparse_text", _embed_sparse_text)
    monkeypatch.setattr(r, "embed_sparse_terms_weighted", _embed_sparse_text)
    monkeypatch.setattr(r.qc, "search_vectors", lambda **_kwargs: [])
    monkeypatch.setattr(r.qc, "search_sparse_vectors", lambda **_kwargs: [])

    debug: dict = {}
    hits = await r.retrieve(
        character_id="luciana",
        query="x",
        scope="private",
        user_id="u1",
        top_k=2,
        sparse_query=None,
        debug_sink=debug,
    )

    assert hits == []
    assert debug["hybrid_debug"]["sparse_mode"] == "clean_query_terms_fallback"
    assert debug["hybrid_debug"]["query_sparse_terms"][0]["term"] == "matteo"


@pytest.mark.asyncio
async def test_retrieve_rejects_non_private_scope():
    with pytest.raises(ValueError):
        await r.retrieve(
            character_id="luciana",
            query="x",
            scope="global",
            user_id="u1",
        )
