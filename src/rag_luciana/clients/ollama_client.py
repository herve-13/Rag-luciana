"""Ollama embeddings client (async via httpx)."""

from __future__ import annotations

import httpx

from rag_luciana.logging import get_logger
from rag_luciana.settings import settings

logger = get_logger(__name__)


async def embed(text: str) -> list[float]:
    """Generate an embedding vector for the given text using Ollama."""
    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url, timeout=30.0
    ) as client:
        response = await client.post(
            "/api/embed",
            json={
                "model": settings.ollama_embed_model,
                "input": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        # Ollama /api/embed returns {"embeddings": [[...], ...]}
        return data["embeddings"][0]


async def health_check() -> bool:
    """Return True if Ollama is reachable and the embed model is available."""
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url, timeout=5.0
        ) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            model_names = [m.get("name", "") for m in data.get("models", [])]
            # Check model is loaded (with or without :latest tag)
            target = settings.ollama_embed_model
            return any(
                name == target or name.startswith(f"{target}:")
                for name in model_names
            )
    except Exception:
        return False


async def prewarm_embed_model() -> bool:
    """Force-load the embedding model in Ollama."""
    try:
        await embed("warmup")
        return True
    except Exception:
        logger.exception("Embedding prewarm failed.")
        return False
