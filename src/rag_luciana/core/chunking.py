"""Text chunking utilities."""

from __future__ import annotations


def chunk_text(
    text: str,
    *,
    max_length: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split *text* into overlapping chunks by character count.

    Uses sentence boundaries ('. ') when possible to avoid breaking
    mid-sentence.  Falls back to hard split when a sentence is too long.
    """
    if not text or not text.strip():
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_length, text_len)

        if end < text_len:
            # Try to find a sentence boundary
            boundary = text.rfind(". ", start, end)
            if boundary > start:
                end = boundary + 1  # include the dot

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(end - overlap, start + 1)

    return chunks
