"""High-level embedding helper (wraps the Ollama client)."""

from __future__ import annotations

from rag_luciana.clients import ollama_client


async def embed_text(text: str) -> list[float]:
    """Return the embedding vector for *text*."""
    return await ollama_client.embed(text)
