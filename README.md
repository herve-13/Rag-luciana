# rag-luciana

Service RAG dédié à Luciana.

Ce dépôt gère :
- l'API de retrieval,
- l'API d'ingestion,
- le stockage SQL de support,
- l'index vectoriel Qdrant,
- la recherche hybride dense + sparse.

## Rôle dans l'architecture

- `backend luciana` orchestre le chat et appelle ce service.
- `rag-luciana` ne génère pas la réponse finale.
- son rôle est de stocker, indexer et retrouver les chunks pertinents.

En pratique :
- `MariaDB` conserve les entités et traces structurées,
- `Qdrant` sert au retrieval,
- Ollama sert aux embeddings côté RAG si activé.

## Stack

- Python
- FastAPI
- SQLAlchemy
- MariaDB
- Qdrant
- Ollama / FastEmbed / reranker Hugging Face selon configuration

## Démarrage local

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn rag_luciana.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Healthchecks :

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

## Endpoints principaux

- `POST /query` : retrieval privé
- `POST /ingest` : ingestion document/chunks
- `GET /healthz` : liveness
- `GET /readyz` : readiness
- `POST/GET /admin/*` : administration personnages, users, conversations, purge

## Structure utile

- `src/rag_luciana/api/` : routes FastAPI
- `src/rag_luciana/core/` : logique retrieval, rerank, sparse
- `src/rag_luciana/db/` : modèles et repository SQL
- `src/rag_luciana/ingest/` : pipeline d'ingestion
- `tests/` : tests unitaires et régressions

## Notes publication GitHub

- `.env` et clés admin doivent rester hors dépôt.
- Les binaires lourds locaux et logs runtime sont ignorés.
- Ce repo suppose des services externes disponibles pour un run complet : MariaDB, Qdrant, Ollama.
