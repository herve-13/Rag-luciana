# RAG Luciana

Service RAG multi-personnage pour jeux vidéo — mémoire privée par joueur, knowledge globale par PNJ.

## Stack

| Composant | Techno |
|-----------|--------|
| API | FastAPI (async) |
| Base de données | MariaDB (SQLAlchemy async) |
| Vector DB | Qdrant |
| Embeddings | Ollama (externe) |

## Installation

```bash
# Cloner et installer
git clone <repo> && cd rag-luciana
pip install -e ".[dev]"

# Copier et éditer la config
cp .env.example .env
# → ajuster DB_*, QDRANT_*, OLLAMA_*, ADMIN_KEY
```

## Configuration

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DB_HOST` | `127.0.0.1` | Hôte MariaDB |
| `DB_PORT` | `3306` | Port MariaDB |
| `DB_NAME` | `rag_luciana` | Nom de la base |
| `DB_USER` | `rag` | Utilisateur DB |
| `DB_PASSWORD` | `change-me` | Mot de passe DB |
| `QDRANT_HOST` | `127.0.0.1` | Hôte Qdrant |
| `QDRANT_PORT` | `6333` | Port Qdrant |
| `OLLAMA_HOST` | `127.0.0.1` | Hôte Ollama |
| `OLLAMA_PORT` | `11434` | Port Ollama |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Modèle d'embeddings |
| `ADMIN_KEY` | `super-secret-admin-key` | Clé d'authentification admin |
| `API_PORT` | `8000` | Port de l'API |

## Lancement

```bash
# Démarrer les services (MariaDB, Qdrant, Ollama)
docker compose -f infra/docker-compose.yml up -d

# Lancer l'API
uvicorn rag_luciana.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Les tables sont créées automatiquement au démarrage. Pour la production, utiliser Alembic.

## Endpoints

### Health

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/healthz` | Liveness (toujours 200) |
| GET | `/readyz` | Readiness (MariaDB + Qdrant + Ollama) |

### Query

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/query` | — | Recherche sémantique multi-scope |

### Admin (nécessite `X-Admin-Key`)

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/admin/characters` | Créer un personnage |
| GET | `/admin/characters` | Lister (pagination + filtre status) |
| GET | `/admin/characters/{id}` | Détail |
| PATCH | `/admin/characters/{id}` | Modifier |
| DELETE | `/admin/characters/{id}` | Soft delete |
| POST | `/admin/users` | Créer un utilisateur |
| GET | `/admin/users` | Lister |
| GET | `/admin/users/{id}` | Détail |
| PATCH | `/admin/users/{id}` | Modifier |
| DELETE | `/admin/users/{id}` | Soft delete |
| GET | `/admin/conversations` | Lister (filtres multiples) |
| GET | `/admin/conversations/{id}` | Détail |
| GET | `/admin/conversations/{id}/messages` | Messages (paginés) |
| GET | `/admin/conversations/{id}/snapshots` | Snapshots (paginés) |
| POST | `/admin/conversations/{id}/close` | Fermer |
| POST | `/admin/conversations/{id}/open` | Rouvrir |
| DELETE | `/admin/conversations/{id}` | **Purge** (hard delete + Qdrant) |
| POST | `/admin/relations` | Creer/mettre a jour la relation user-agent |
| GET | `/admin/relations` | Lister les relations (filtres + pagination) |
| GET | `/admin/relations/{user_id}/{agent_id}` | Lire une relation user-agent |

### Schema relationnel user-agent (v1)

Chaque relation stocke:
- `version`
- `relation_state` (`familiarity`, `trust`, `attachment`, `tension`)
- `interaction_stats` (`total_messages`, `last_interaction`)
- `flags` (`favorite`, `blocked`)
- `meta` (JSON libre, ex. dates techniques)

## Exemples curl

### Créer un personnage

```bash
curl -s -X POST http://localhost:8000/admin/characters \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: super-secret-admin-key" \
  -d '{
    "character_id": "npc_jean",
    "name": "Jean le Forgeron",
    "description": "Forgeron du village, expert en clés et serrures."
  }' | jq
```

### Créer un utilisateur

```bash
curl -s -X POST http://localhost:8000/admin/users \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: super-secret-admin-key" \
  -d '{
    "user_id": "user_42",
    "display_name": "Joueur 42"
  }' | jq
```

### Lister les conversations (avec filtres)

```bash
curl -s "http://localhost:8000/admin/conversations?character_id=npc_jean&status=active&limit=10" \
  -H "X-Admin-Key: super-secret-admin-key" | jq
```

### Messages d'une conversation

```bash
curl -s "http://localhost:8000/admin/conversations/9c2f0b4e-xxxx/messages?limit=20" \
  -H "X-Admin-Key: super-secret-admin-key" | jq
```

### Query — scope=private

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "character_id": "npc_jean",
    "user_id": "user_42",
    "conversation_id": "9c2f0b4e-xxxx",
    "query": "Que m'\''a dit Jean sur la clé du hangar ?",
    "top_k": 5,
    "scope": "private",
    "filters": {"tags": ["hangar"]},
    "return_text": true
  }' | jq
```

### Query — scope=both

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "character_id": "npc_jean",
    "user_id": "user_42",
    "query": "Que sait Jean sur les serrures ?",
    "top_k": 8,
    "scope": "both",
    "return_text": true
  }' | jq
```

### Purger une conversation (hard delete + Qdrant)

```bash
curl -s -X DELETE http://localhost:8000/admin/conversations/9c2f0b4e-xxxx \
  -H "X-Admin-Key: super-secret-admin-key"
# → 204 No Content
# ⚠ Supprime conversation + messages + snapshots + chunks SQL
#   ET purge les vecteurs dans Qdrant (collection private, filtre conversation_id)
```

## Purge vectorielle

Lors du `DELETE /admin/conversations/{id}`, le système :

1. **SQL** : supprime en cascade `messages`, `snapshots`, `chunks` (doc_id = `conv_{id}`), puis la `conversation`
2. **Qdrant** : appelle `delete_by_filter` sur la collection `rag_{character_id}_private` avec les filtres `user_id` + `conversation_id` pour supprimer tous les vecteurs associés

En cas d'échec Qdrant, les données SQL sont quand même supprimées (logged error). Un script de réconciliation pourra être ajouté ultérieurement.

## Documentation API interactive

FastAPI génère automatiquement la doc :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
## Ingest API

### Endpoint

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | `/ingest` | `X-Admin-Key` | Ingest a JSON document (chunking + embeddings + upsert to SQL and Qdrant) |

### Example (global scope)

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: super-secret-admin-key" \
  -d '{
    "character_id": "npc_jean",
    "scope": "global",
    "doc_id": "lore_001",
    "doc_version": 1,
    "source_uri": "internal://lore/npc_jean.json",
    "kind": "lore",
    "tags": ["village", "hangar"],
    "data": {
      "title": "Jean le Forgeron",
      "facts": [
        "Jean garde un double de la cle du hangar.",
        "Il ouvre son atelier a l'aube."
      ]
    }
  }' | jq
```

### Example (private scope)

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: super-secret-admin-key" \
  -d '{
    "character_id": "npc_jean",
    "scope": "private",
    "user_id": "user_42",
    "doc_id": "conv_9c2f0b4e",
    "kind": "memory",
    "data": {
      "summary": "Le joueur a demande la cle du hangar."
    }
  }' | jq
```

## Workflow de test

Voir `docs/test-deply.md` pour la strategie de validation:
- developpement en local sous WSL Ubuntu (sans Docker)
- tests de deploiement sur machine Debian avec Docker via SSH

## Scripts utilitaires (seed/fetch relation)

Deux scripts sont disponibles pour tester sans passer par BACKEND_LUCIANA:

```bash
# 1) Seed user + agent + relation initiale depuis BACKEND_LUCIANA/data
python scripts/seed_user_agent_relation.py --user-id herve --agent-id aria

# 2) Lire ce qui est stocke en base
python scripts/get_user_agent_relation.py --user-id herve --agent-id aria
```

## Update 2026-02-13 (conversation mutation support)

Ajouts admin pour brancher BACKEND_LUCIANA en mode conversation full RAG:

- `POST /admin/conversations/upsert`
  - cree ou met a jour une conversation (status/meta)
- `POST /admin/conversations/{conversation_id}/messages`
  - append un batch de messages dans la conversation
  - gere `turn_index` en sequence
  - cree la conversation si absente

Usage cible:
- BACKEND_LUCIANA appelle ces routes pour persister chaque tour user/assistant.
- L'historique est relu via `GET /admin/conversations/{id}/messages`.
