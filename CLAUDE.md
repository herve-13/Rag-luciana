# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RAG Luciana — a multi-character Retrieval-Augmented Generation service for video game NPCs with per-user memory isolation. Combines semantic vector search (Qdrant) with character-specific knowledge bases and private conversation memories, backed by MariaDB for relational data and Ollama for embeddings.

## Commands

```bash
# Install (editable + dev deps)
pip install -e ".[dev]"

# Start infrastructure (MariaDB + Qdrant)
docker compose -f infra/docker-compose.yml up -d

# Run API server (dev mode with auto-reload)
python -m uvicorn rag_luciana.api.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
pytest

# Run a single test file
pytest tests/test_chunking.py -v

# Build package
hatch build
```

Configuration: copy `.env.example` to `.env`. Key vars: `DB_*`, `QDRANT_*`, `OLLAMA_*`, `ADMIN_KEY`. Ollama is an external service (not in docker-compose).

## Architecture

### Layered structure (`src/rag_luciana/`)

- **`api/`** — FastAPI routers, Pydantic schemas, dependency injection (auth, DB sessions). Entry point: `api/main.py` creates the app with lifespan, registers 4 routers (health, query, ingest, admin), and adds request-logging middleware.
- **`core/`** — Business logic: `retrieval.py` (vector search + merge/dedup pipeline), `chunking.py` (sentence-boundary text splitting), `embeddings.py` (Ollama wrapper).
- **`db/`** — SQLAlchemy async ORM: `models.py` (8 tables), `session.py` (engine/session factory), `repo.py` (~450 lines of CRUD functions).
- **`clients/`** — External service wrappers: `qdrant_client.py` (vector DB operations), `ollama_client.py` (embedding via HTTP).
- **`ingest/`** — `ingest_json.py`: recursive JSON traversal → text extraction with JSONPath → chunking → embedding → upsert to both MariaDB and Qdrant.
- **`settings.py`** — Pydantic `BaseSettings` singleton loading from `.env`.

### Key design decisions

**Two-tier scope model:** Each character has two Qdrant collections (`rag_{character_id}_global` and `rag_{character_id}_private`). Global = shared character lore; private = per-user conversation memory. Query scope can be `global`, `private`, or `both` (blended k/2 each, merged and deduped).

**Deterministic chunk IDs:** `chunk_id = SHA256(character_id | scope | user_id | doc_id | json_path | text_hash)`. Re-ingesting the same document produces identical IDs → upsert semantics, no duplicates.

**Soft-delete vs hard-delete:** Characters and Users are soft-deleted (`deleted_at` column). Conversations can be hard-deleted (purge) which cascades in SQL and runs Qdrant filter-delete for GDPR compliance.

**Async-first:** All I/O uses async (aiomysql, httpx, SQLAlchemy asyncio). FastAPI dependencies yield async sessions with auto-commit/rollback.

### Data flow

**Ingest** (`POST /ingest`, requires `X-Admin-Key`): JSON body → recursive text extraction → sentence-aware chunking → Ollama embedding → upsert to MariaDB chunks table + Qdrant collection. Tracked by `ingestion_runs` table.

**Query** (`POST /query`, no auth): embed query via Ollama → search relevant Qdrant collections with filters (character_id, user_id, conversation_id, tags, kinds) → merge + dedup by chunk_id → return top_k scored results.

### Auth

Admin endpoints use `X-Admin-Key` header checked against `ADMIN_KEY` env var. The `/query` endpoint is public (intended for game client calls).

## Tech Stack

Python 3.11+ · FastAPI · SQLAlchemy (async) · aiomysql · MariaDB 11 · Qdrant · Ollama (nomic-embed-text, 768-dim vectors, cosine distance) · Hatch build system · structlog (JSON logging)
