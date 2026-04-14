# rag-luciana

Service RAG dedie a Luciana.

Ce depot gere :
- l'API de retrieval
- l'API d'ingestion
- le stockage SQL de support
- l'index vectoriel Qdrant
- la recherche hybride dense + sparse

## Role dans l'architecture

- `backend luciana` orchestre le chat et appelle ce service
- `rag-luciana` ne genere pas la reponse finale
- son role est de stocker, indexer et retrouver les chunks pertinents

En pratique :
- `MariaDB` conserve les entites et traces structurees
- `Qdrant` sert au retrieval
- Ollama sert aux embeddings cote RAG si active

## Stack

- Python
- FastAPI
- SQLAlchemy
- MariaDB
- Qdrant
- Ollama / FastEmbed / reranker Hugging Face selon configuration

## Versions runtime recommandees

- Python `3.11`
- MariaDB `10.6+` ou `11.x`
- Qdrant recent

## Snapshot Git compatible

Le service est versionne par snapshot Git.

Snapshot recommande pour repartir facilement :
- tag Git: `recovery-2026-04-14`
- branche de travail: `feat/simple-memory-archive-retrieval`

Compatibilite attendue :

| Repo | Tag recommande | Branche compatible |
|---|---|---|
| `rag-luciana` | `recovery-2026-04-14` | `feat/simple-memory-archive-retrieval` |
| `Luciana_backend` | `recovery-2026-04-14` | `feat/simple-memory-archive-retrieval` |
| `Frontend-Luciana` | `recovery-2026-04-14` | `feat/simple-memory-archive-retrieval` |

## Demarrage local

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn rag_luciana.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Healthchecks directs :

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

## Endpoints principaux

- `POST /query` : retrieval prive
- `POST /ingest` : ingestion document/chunks
- `GET /healthz` : liveness
- `GET /readyz` : readiness
- `POST/GET /admin/*` : administration personnages, users, conversations, purge

## Structure utile

- `src/rag_luciana/api/` : routes FastAPI
- `src/rag_luciana/core/` : logique retrieval, rerank, sparse
- `src/rag_luciana/db/` : modeles et repository SQL
- `src/rag_luciana/ingest/` : pipeline d'ingestion
- `tests/` : tests unitaires et regressions

## Notes publication GitHub

- `.env` et cles admin doivent rester hors depot
- Les binaires lourds locaux et logs runtime sont ignores
- Ce repo suppose des services externes disponibles pour un run complet : MariaDB, Qdrant, Ollama
