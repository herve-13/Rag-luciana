"""Qdrant vector database client wrapper."""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from rag_luciana.logging import get_logger
from rag_luciana.settings import settings

logger = get_logger(__name__)


def _build_client() -> QdrantClient:
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout=10,
    )


_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return a singleton Qdrant client."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ── Collection helpers ───────────────────────────────────


def collection_name(character_id: str, scope: str) -> str:
    """Return the Qdrant collection name for a character + scope."""
    return f"rag_{character_id}_{scope}"


def ensure_collection(character_id: str, scope: str, vector_size: int = 768) -> None:
    """Create the collection if it doesn't exist."""
    client = get_qdrant_client()
    name = collection_name(character_id, scope)
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("qdrant_collection_created", collection=name)


# ── Search ───────────────────────────────────────────────


def search_vectors(
    character_id: str,
    scope: str,
    vector: list[float],
    limit: int = 10,
    filters: dict | None = None,
) -> list[models.ScoredPoint]:
    """Search a Qdrant collection with optional payload filters."""
    client = get_qdrant_client()
    name = collection_name(character_id, scope)
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        return []

    qdrant_filter = None
    if filters:
        must_conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchAny(any=value),
                    )
                )
            else:
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                )
        qdrant_filter = models.Filter(must=must_conditions)

    return client.query_points(
        collection_name=name,
        query=vector,
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    ).points


# ── Upsert ───────────────────────────────────────────────


def upsert_vector(
    character_id: str,
    scope: str,
    point_id: str,
    vector: list[float],
    payload: dict,
) -> None:
    """Upsert a single vector point."""
    client = get_qdrant_client()
    name = collection_name(character_id, scope)
    normalized_id: int | str
    if isinstance(point_id, int):
        normalized_id = point_id
    else:
        # Qdrant accepts only integer or UUID point IDs.
        try:
            normalized_id = str(uuid.UUID(str(point_id)))
        except ValueError:
            normalized_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(point_id)))
    client.upsert(
        collection_name=name,
        points=[
            models.PointStruct(
                id=normalized_id,
                vector=vector,
                payload=payload,
            )
        ],
    )


# ── Delete by filter ─────────────────────────────────────


def delete_by_filter(
    character_id: str,
    scope: str,
    filters: dict,
) -> None:
    """Delete all points matching the payload filters.

    Used when purging a conversation's private memory from Qdrant.
    """
    client = get_qdrant_client()
    name = collection_name(character_id, scope)

    must_conditions = []
    for key, value in filters.items():
        must_conditions.append(
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
        )

    client.delete(
        collection_name=name,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=must_conditions),
        ),
    )
    logger.info(
        "qdrant_vectors_deleted",
        collection=name,
        filters=filters,
    )


# ── Health ───────────────────────────────────────────────


def health_check() -> bool:
    """Return True if Qdrant is reachable."""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except (ResponseHandlingException, Exception):
        return False
