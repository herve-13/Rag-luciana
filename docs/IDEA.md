rag-luciana/
├── src/
│   └── rag_luciana/
│       ├── api/
│       │   ├── main.py              # FastAPI app (POST /query)
│       │   └── schemas.py           # Pydantic: QueryRequest/Response
│       ├── ingest/
│       │   └── ingest_json.py       # CLI ingestion JSON -> DB + Qdrant
│       ├── core/
│       │   ├── chunking.py
│       │   ├── embeddings.py        # call Ollama embeddings (external)
│       │   └── retrieval.py         # search qdrant, merge, return chunks
│       ├── db/
│       │   ├── models.py            # SQLAlchemy (MariaDB)
│       │   ├── session.py
│       │   └── repo.py              # CRUD documents/chunks/conversations
│       ├── clients/
│       │   ├── qdrant_client.py
│       │   └── ollama_client.py
│       ├── settings.py              # BaseSettings (.env)
│       └── logging.py
├── migrations/                       # Alembic (recommandé)
├── tests/
│   ├── test_chunking.py
│   ├── test_ingest_idempotent.py
│   └── test_query_contract.py
├── infra/
│   └── docker-compose.yml            # MariaDB + Qdrant (ou autre)
├── scripts/
│   ├── reset_vector_index.py
│   └── reindex_from_db.py
├── pyproject.toml (ou requirements.txt)
├── .env.example
└── README.md

1) Contrat API corrigé : POST /query
Request (recommandé)

character_id obligatoire

user_id obligatoire

conversation_id recommandé (car un user peut avoir plusieurs conversations avec le même PNJ : différentes quêtes, sessions, etc.)

scope pour distinguer “mémoire privée” vs “knowledge globale du personnage”

{
  "character_id": "npc_jean",
  "user_id": "user_42",
  "conversation_id": "9c2f0b4e-....",
  "query": "Que m'a dit Jean sur la clé du hangar ?",
  "top_k": 8,
  "scope": "private",
  "filters": {
    "tags": ["hangar"],
    "kinds": ["memory", "lore"]
  },
  "return_text": true
}

Réponse
{
  "query_id": "d7d4c0c4-....",
  "character_id": "npc_jean",
  "user_id": "user_42",
  "top_k": 8,
  "results": [
    {
      "chunk_id": "ch_01HZZ....",
      "doc_id": "doc_01HYY....",
      "score": 0.83,
      "text": "…",
      "metadata": {
        "scope": "private",
        "kind": "memory",
        "conversation_id": "9c2f0b4e-....",
        "source": "messages",
        "tags": ["hangar"]
      }
    }
  ]
}


Important sécurité : idéalement user_id ne vient pas du body mais du token (JWT/API key signée). Sinon, un client peut demander /query avec le user_id de quelqu’un d’autre.

2) Stratégie d’isolement (cloisonnement)
Règle d’or

Pour tout retrieval de mémoire privée : filtre obligatoire sur :

character_id == …

user_id == …

(optionnel mais conseillé) conversation_id == …

Scopes

scope = "private" : mémoire du user avec ce personnage (isolée par user_id)

scope = "global" : lore / règles / knowledge publique du personnage (pas isolée par user)

Tu peux faire :

2 collections vectorielles (global_chunks_{character}, private_memory_{character}) → le plus sûr

ou 1 collection avec champ scope + filtres stricts → OK mais plus risqué (un oubli de filtre = fuite)

3) MariaDB : schémas corrigés (conversations PNJ)
conversations

Chaque conversation appartient à un (character_id, user_id).

CREATE TABLE conversations (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  conversation_id CHAR(36) NOT NULL,              -- uuid
  character_id    VARCHAR(64) NOT NULL,
  user_id         VARCHAR(64) NOT NULL,
  status          VARCHAR(16) NOT NULL DEFAULT 'active',
  meta_json       JSON NULL,
  created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

  UNIQUE KEY uq_conv (character_id, conversation_id),
  KEY idx_user_char (user_id, character_id, updated_at),
  KEY idx_char (character_id, updated_at)
);


Pourquoi UNIQUE(character_id, conversation_id) : conversation_id peut être UUID globalement unique, mais ce composite évite les collisions/logique multi-personnage si tu changes un jour de stratégie.

messages (append-only)

Cloisonnement + ordre strict des tours :

CREATE TABLE messages (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  message_id      CHAR(36) NOT NULL,              -- uuid
  conversation_id CHAR(36) NOT NULL,
  character_id    VARCHAR(64) NOT NULL,
  user_id         VARCHAR(64) NOT NULL,

  ts              DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  turn_index      INT NOT NULL,
  role            VARCHAR(16) NOT NULL,           -- user / character / system / tool
  content         MEDIUMTEXT NOT NULL,
  meta_json       JSON NULL,

  UNIQUE KEY uq_msg (message_id),
  UNIQUE KEY uq_turn (character_id, conversation_id, turn_index),
  KEY idx_conv_ts (character_id, conversation_id, ts),
  KEY idx_user (user_id, character_id, ts)
);

snapshots (résumé + état)
CREATE TABLE snapshots (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  snapshot_id     CHAR(36) NOT NULL,
  conversation_id CHAR(36) NOT NULL,
  character_id    VARCHAR(64) NOT NULL,
  user_id         VARCHAR(64) NOT NULL,

  ts              DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  turn_index      INT NOT NULL,
  summary         MEDIUMTEXT NOT NULL,
  state_json      JSON NULL,

  UNIQUE KEY uq_snap (snapshot_id),
  KEY idx_conv_turn (character_id, conversation_id, turn_index),
  KEY idx_user_char (user_id, character_id, ts)
);

4) MariaDB : table chunks (suite)
Table chunks

Objectif : garder le texte + metadata pour rebuild/reindex.
Le chunk doit porter le même scope que son document.

CREATE TABLE chunks (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,

  chunk_id      VARCHAR(64) NOT NULL,       -- ex: sha256(character_id|doc_id|json_path|text_hash)
  character_id  VARCHAR(64) NOT NULL,

  scope         VARCHAR(16) NOT NULL,       -- 'global' ou 'private'
  user_id       VARCHAR(64) NULL,           -- NULL si global, NON NULL si private

  doc_id        VARCHAR(64) NOT NULL,
  doc_version   INT NOT NULL,
  ordinal       INT NOT NULL,               -- ordre stable dans le doc
  json_path     VARCHAR(512) NULL,          -- ex: $.steps[3]
  kind          VARCHAR(32) NULL,           -- ex: 'lore'|'procedure'|'memory'|'fact'...

  text          MEDIUMTEXT NOT NULL,
  text_hash     CHAR(64) NOT NULL,

  lang          VARCHAR(16) NULL,
  tags_json     JSON NULL,                  -- ["hangar","key"]
  meta_json     JSON NULL,                  -- metadata libre (quest_id, location, etc.)

  created_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  UNIQUE KEY uq_chunk (character_id, chunk_id),
  KEY idx_doc (character_id, doc_id, doc_version),
  KEY idx_scope (character_id, scope, created_at),
  KEY idx_private (character_id, user_id, created_at),
  KEY idx_text_hash (character_id, text_hash)
);

Contrainte logique (à respecter côté code)

si scope='private' → user_id doit être non NULL

si scope='global' → user_id doit être NULL

MariaDB ne gère pas toujours les CHECK constraints selon versions/config, donc on l’impose dans l’app.

5) MariaDB : ingestion tracking (recommandé)
Table ingestion_runs

Trace les imports JSON (utile pour debug, reprise, métriques).

CREATE TABLE ingestion_runs (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id        VARCHAR(64) NOT NULL,
  character_id  VARCHAR(64) NOT NULL,

  scope         VARCHAR(16) NOT NULL,       -- global/private
  user_id       VARCHAR(64) NULL,           -- si private

  source_uri    VARCHAR(512) NULL,
  started_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at   DATETIME(6) NULL,
  status        VARCHAR(32) NOT NULL,       -- running/success/failed
  error         TEXT NULL,
  docs_count    INT NOT NULL DEFAULT 0,
  chunks_count  INT NOT NULL DEFAULT 0,

  UNIQUE KEY uq_run (character_id, run_id),
  KEY idx_status (character_id, status),
  KEY idx_started (character_id, started_at),
  KEY idx_private (character_id, user_id, started_at)
);

6) Vector DB (Qdrant) : collections & payload (corrigé)
Option la plus sûre : 2 collections

rag_{character_id}_global : connaissances communes du personnage

rag_{character_id}_private : mémoire privée (isolée par user)

Pourquoi c’est mieux : même si tu oublies un filtre, tu ne mélanges pas “global” et “private”.

Payload recommandé (global)
{
  "character_id": "npc_jean",
  "scope": "global",
  "doc_id": "doc_...",
  "doc_version": 3,
  "chunk_id": "ch_...",
  "kind": "lore",
  "tags": ["hangar"],
  "json_path": "$.lore[2]",
  "source_uri": "internal://lore/npc_jean.json"
}

Payload recommandé (private)
{
  "character_id": "npc_jean",
  "scope": "private",
  "user_id": "user_42",
  "conversation_id": "9c2f0b4e-....",
  "doc_id": "conv_9c2f0b4e",
  "doc_version": 1,
  "chunk_id": "ch_...",
  "kind": "memory",
  "tags": ["hangar","key"],
  "json_path": "$.messages[17]"
}

Filtrage obligatoire en /query

Si scope=private :

character_id == req.character_id

user_id == req.user_id

(optionnel) conversation_id == req.conversation_id si fourni

Si scope=global :

character_id == req.character_id

Et si scope=both (cas fréquent), tu fais deux recherches (global + private) puis tu fusionnes/rerank côté API.

7) API /query : règles de scopes (important)
Champ scope (enum)

global : cherche uniquement dans global

private : cherche uniquement dans private

both : cherche dans les deux et renvoie un mix

Stratégie recommandée en both

récupérer k1 = ceil(top_k/2) global, k2 = top_k-k1 private

concat + dédup par chunk_id

(optionnel) rerank léger

return top_k

8) “Mémoire conversationnelle” : comment la représenter en JSON (ingestion)

Comme tu ingères “uniquement JSON”, tu peux générer un JSON “document mémoire” depuis tes tables messages/snapshots (ou directement stocker les messages en JSON).

Exemple de doc mémoire (private) :

{
  "type": "conversation_memory",
  "character_id": "npc_jean",
  "user_id": "user_42",
  "conversation_id": "9c2f0b4e-....",
  "messages": [
    {"turn": 1, "role": "user", "content": "..."},
    {"turn": 2, "role": "character", "content": "..."}
  ],
  "summary": "Résumé actuel ...",
  "state": {"relationship": 2, "quest_flags": ["HANGAR_KEY_PROMISED"]}
}


Tu chunkes :

par message (ou groupes de 2–4 messages)

un chunk “summary”

éventuellement des chunks “facts” extraits

9) Checklist cloisonnement (anti-fuite)

✅ user_id obligatoire pour private

✅ Filtre vector DB appliqué avant d’obtenir les résultats

✅ Les tables messages/snapshots/chunks/documents portent character_id + scope + user_id (si private)

✅ Si tu as un token : user_id dérivé du token (pas du body)

✅ Tests : un user A ne retrouve jamais un chunk user B