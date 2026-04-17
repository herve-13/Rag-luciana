"""Qdrant vector database client wrapper."""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException

from rag_luciana.logging import get_logger
from rag_luciana.settings import settings

logger = get_logger(__name__)


def _resolve_tenant_id(tenant_id: str | None = None) -> str:
    resolved = str(tenant_id or settings.default_tenant_id or "").strip()
    if not resolved:
        raise ValueError("tenant_id is required")
    return resolved


def _resolve_assistant_id(assistant_id: str | None = None) -> str:
    resolved = str(assistant_id or "").strip()
    if not resolved:
        raise ValueError("assistant_id is required")
    return resolved


def _base_collection_name(assistant_id: str, scope: str) -> str:
    return f"rag_{assistant_id}_{scope}"


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


def collection_name(
    assistant_id: str | None = None,
    scope: str = "",
    tenant_id: str | None = None,
) -> str:
    """Return the primary Qdrant collection name for a tenant + assistant + scope."""
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    if not settings.qdrant_tenant_scoped_collections:
        return _base_collection_name(resolved_assistant_id, scope)
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    return f"rag_{resolved_tenant_id}_{resolved_assistant_id}_{scope}"


def _collection_candidates(
    assistant_id: str | None = None,
    scope: str = "",
    tenant_id: str | None = None,
) -> list[str]:
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    primary = collection_name(resolved_assistant_id, scope, tenant_id=tenant_id)
    base_name = _base_collection_name(resolved_assistant_id, scope)
    if primary == base_name:
        return [primary]
    return [primary, base_name]


def _select_collection_name(
    *,
    client: QdrantClient,
    assistant_id: str | None = None,
    scope: str,
    tenant_id: str | None = None,
) -> tuple[str, set[str]]:
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    existing = {c.name for c in client.get_collections().collections}
    for candidate in _collection_candidates(resolved_assistant_id, scope, tenant_id=tenant_id):
        if candidate in existing:
            return candidate, existing
    return collection_name(resolved_assistant_id, scope, tenant_id=tenant_id), existing


def ensure_collection(
    assistant_id: str | None = None,
    scope: str = "",
    vector_size: int = 768,
    tenant_id: str | None = None,
) -> None:
    """Create the collection if it doesn't exist."""
    client = get_qdrant_client()
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    name = collection_name(resolved_assistant_id, scope, tenant_id=tenant_id)
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        if scope == "private" and settings.hybrid_enabled and settings.sparse_enabled:
            client.create_collection(
                collection_name=name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )
        else:
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
    assistant_id: str | None = None,
    scope: str = "",
    *,
    vector: list[float],
    limit: int = 10,
    filters: dict | None = None,
    tenant_id: str | None = None,
) -> list[models.ScoredPoint]:
    """Search a Qdrant collection with optional payload filters."""
    client = get_qdrant_client()
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    name, existing = _select_collection_name(
        client=client,
        assistant_id=resolved_assistant_id,
        scope=scope,
        tenant_id=tenant_id,
    )
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

    query_kwargs: dict = {
        "collection_name": name,
        "query": vector,
        "query_filter": qdrant_filter,
        "limit": limit,
        "with_payload": True,
    }
    if scope == "private" and settings.hybrid_enabled and settings.sparse_enabled:
        query_kwargs["using"] = "dense"
    try:
        return client.query_points(**query_kwargs).points
    except Exception:
        # Backward compatibility: old private collections may still be single dense vector.
        if query_kwargs.get("using") == "dense":
            query_kwargs.pop("using", None)
            return client.query_points(**query_kwargs).points
        raise


def search_sparse_vectors(
    assistant_id: str | None = None,
    scope: str = "",
    *,
    indices: list[int],
    values: list[float],
    limit: int = 10,
    filters: dict | None = None,
    tenant_id: str | None = None,
) -> list[models.ScoredPoint]:
    """Search sparse vector branch in a Qdrant collection."""
    if not indices or not values or len(indices) != len(values):
        return []
    client = get_qdrant_client()
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    name, existing = _select_collection_name(
        client=client,
        assistant_id=resolved_assistant_id,
        scope=scope,
        tenant_id=tenant_id,
    )
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

    try:
        return client.query_points(
            collection_name=name,
            query=models.SparseVector(indices=indices, values=values),
            using="sparse",
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        ).points
    except Exception as exc:
        logger.warning("qdrant_sparse_query_failed", collection=name, error=str(exc))
        return []


# ── Upsert ───────────────────────────────────────────────


def upsert_vector(
    assistant_id: str | None = None,
    scope: str = "",
    *,
    point_id: str,
    vector: list[float],
    payload: dict,
    sparse_indices: list[int] | None = None,
    sparse_values: list[float] | None = None,
    tenant_id: str | None = None,
) -> None:
    """Upsert a single vector point."""
    client = get_qdrant_client()
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    name, _existing = _select_collection_name(
        client=client,
        assistant_id=resolved_assistant_id,
        scope=scope,
        tenant_id=tenant_id,
    )
    normalized_id: int | str
    if isinstance(point_id, int):
        normalized_id = point_id
    else:
        # Qdrant accepts only integer or UUID point IDs.
        try:
            normalized_id = str(uuid.UUID(str(point_id)))
        except ValueError:
            normalized_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(point_id)))
    vector_payload: list[float] | dict[str, list[float] | models.SparseVector]
    if (
        scope == "private"
        and settings.hybrid_enabled
        and settings.sparse_enabled
        and sparse_indices
        and sparse_values
        and len(sparse_indices) == len(sparse_values)
    ):
        vector_payload = {
            "dense": vector,
            "sparse": models.SparseVector(indices=sparse_indices, values=sparse_values),
        }
    elif scope == "private" and settings.hybrid_enabled and settings.sparse_enabled:
        vector_payload = {"dense": vector}
    else:
        vector_payload = vector

    try:
        client.upsert(
            collection_name=name,
            points=[models.PointStruct(id=normalized_id, vector=vector_payload, payload=payload)],
        )
    except Exception:
        # Backward compatibility for old collections expecting single dense vector.
        client.upsert(
            collection_name=name,
            points=[models.PointStruct(id=normalized_id, vector=vector, payload=payload)],
        )


# ── Delete by filter ─────────────────────────────────────


def delete_by_filter(
    assistant_id: str | None = None,
    scope: str = "",
    *,
    filters: dict,
    tenant_id: str | None = None,
) -> None:
    """Delete all points matching the payload filters.

    Used when purging a conversation's private memory from Qdrant.
    """
    client = get_qdrant_client()
    resolved_assistant_id = _resolve_assistant_id(assistant_id)
    name, _existing = _select_collection_name(
        client=client,
        assistant_id=resolved_assistant_id,
        scope=scope,
        tenant_id=tenant_id,
    )

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
