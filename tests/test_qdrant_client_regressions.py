from __future__ import annotations

import uuid

from rag_luciana.clients import qdrant_client as qc


class _Collections:
    def __init__(self, names: list[str]) -> None:
        self.collections = [type("C", (), {"name": n})() for n in names]


class _FakeClientSearch:
    def __init__(self, names: list[str]) -> None:
        self._names = names
        self.query_called = False

    def get_collections(self):
        return _Collections(self._names)

    def query_points(self, **kwargs):
        self.query_called = True
        return type("R", (), {"points": [1, 2, 3]})()


class _FakeClientUpsert:
    def __init__(self) -> None:
        self.last_id = None
        self.last_vector = None

    def upsert(self, *, collection_name, points):
        self.last_id = points[0].id
        self.last_vector = points[0].vector


def test_search_vectors_returns_empty_when_collection_missing(monkeypatch):
    client = _FakeClientSearch(names=[])
    monkeypatch.setattr(qc, "get_qdrant_client", lambda: client)

    result = qc.search_vectors(
        character_id="npc_jean",
        scope="global",
        vector=[0.1, 0.2, 0.3],
        limit=5,
    )

    assert result == []
    assert client.query_called is False


def test_upsert_vector_normalizes_non_uuid_point_id(monkeypatch):
    client = _FakeClientUpsert()
    monkeypatch.setattr(qc, "get_qdrant_client", lambda: client)

    qc.upsert_vector(
        character_id="npc_jean",
        scope="global",
        point_id="fc6a06301394135e32f6ce6ad3a3a43e1330844d7c8abf9a5739cf0e7f029cee",
        vector=[0.1, 0.2, 0.3],
        payload={"chunk_id": "x"},
    )

    # Should always end as a UUID string accepted by Qdrant.
    uuid.UUID(str(client.last_id))


def test_upsert_vector_private_includes_sparse_when_enabled(monkeypatch):
    client = _FakeClientUpsert()
    monkeypatch.setattr(qc, "get_qdrant_client", lambda: client)
    monkeypatch.setattr(qc.settings, "hybrid_enabled", True)
    monkeypatch.setattr(qc.settings, "sparse_enabled", True)

    qc.upsert_vector(
        character_id="npc_jean",
        scope="private",
        point_id="point-1",
        vector=[0.1, 0.2, 0.3],
        sparse_indices=[1, 2],
        sparse_values=[0.5, 0.9],
        payload={"chunk_id": "x"},
    )

    assert isinstance(client.last_vector, dict)
    assert "dense" in client.last_vector
    assert "sparse" in client.last_vector
