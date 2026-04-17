# AGENTS

RAG Luciana is the retrieval and memory backend.

## Read First

- `../WORKFLOW.md`
- `../backend luciana/docs/agent_state/current_runtime_state.md`
- `src/rag_luciana/api/main.py`
- `src/rag_luciana/api/schemas.py`

## Key Runtime Areas

- API:
  - `src/rag_luciana/api/`
- Retrieval:
  - `src/rag_luciana/core/retrieval.py`
  - `src/rag_luciana/clients/qdrant_client.py`
- Ingest:
  - `src/rag_luciana/api/ingest_router.py`
  - `src/rag_luciana/ingest/ingest_json.py`
- Admin:
  - `src/rag_luciana/api/admin_router.py`
- DB:
  - `src/rag_luciana/db/models.py`
  - `src/rag_luciana/db/repo.py`

## Runtime Rules

- Canonical scope is `tenant_id + assistant_id + user_id`.
- Keep backend-facing contracts aligned with backend Luciana.
- Backend-active paths must not depend on `character_id`.
- Use WSL for runtime and tests.

## Validation

- Run tests in WSL only:
  - `bash ../scripts/wsl_test_rag.sh`
- Targeted examples:
  - `bash ../scripts/wsl_test_rag.sh tests/test_admin_registry_routes.py`
- Health:
  - `bash ../scripts/wsl_healthcheck.sh`

## Avoid

- Do not run `pytest` for `rag-luciana` from Windows Python.
- Do not drift backend and RAG schemas independently when contracts change.
