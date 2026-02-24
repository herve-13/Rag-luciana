# Reprise - Etat du projet

Date de sauvegarde: 2026-02-11

## Contexte

- Branche: `main`
- Dernier commit pousse: `d2cd614` (`Implement ingest endpoint and ingestion pipeline`)
- Etat local non committe:
  - `M README.md`
  - `M infra/docker-compose.yml` (Ollama retire du compose)
  - `?? docs/test-deply.md`
  - `?? venv_wsl/` (environnement local WSL, ne pas committer)

## Ce qui est deja fait

- Endpoint `/ingest` implemente (schema, routeur, pipeline JSON -> chunks -> embeddings -> SQL/Qdrant).
- Endpoint `/query` operationnel cote code.
- Docker compose local ajuste pour ne lancer que:
  - `mariadb`
  - `qdrant`
- Configuration `.env` actuelle:
  - `OLLAMA_HOST=ollama.leic.fr`
  - `OLLAMA_PORT=11434`

## Validation executee aujourd'hui

- API lancee sur `http://127.0.0.1:8000`
- `GET /healthz` -> OK
- `GET /readyz` -> `not_ready` avec:
  - `mariadb=true`
  - `qdrant=true`
  - `ollama=false`
- `POST /ingest` -> 500
- `POST /query` -> 500

Cause confirmee dans les logs:
- `httpx.ConnectError: All connection attempts failed` vers `ollama.leic.fr:11434`

## Blocage actuel

Probleme reseau vers Ollama externe depuis la machine de dev (Windows + WSL):

- `curl http://ollama.leic.fr:11434/api/tags` echoue.

Tant que ce point n'est pas resolu, `/readyz` restera non pret et `/ingest` + `/query` echoueront.

## Reprise demain (checklist rapide)

1. Verifier acces reseau Ollama:
   - `curl http://ollama.leic.fr:11434/api/tags`
2. Demarrer infra locale (WSL):
   - `docker compose -f infra/docker-compose.yml up -d --remove-orphans`
3. Lancer API (WSL, venv):
   - `source venv_wsl/bin/activate`
   - `python -m uvicorn rag_luciana.api.main:app --host 0.0.0.0 --port 8000`
4. Revalider:
   - `GET /readyz` (attendu: `ready`)
   - `POST /ingest` (attendu: 202 success)
   - `POST /query` (attendu: 200 avec resultats)

## Commandes de test (PowerShell)

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/readyz
```

```powershell
$headers = @{ 'X-Admin-Key' = 'super-secret-admin-key' }
$body = @{
  character_id='npc_jean'
  scope='global'
  doc_id='lore_001'
  doc_version=1
  source_uri='internal://lore/npc_jean.json'
  kind='lore'
  tags=@('village','hangar')
  data=@{
    title='Jean le Forgeron'
    facts=@(
      'Jean garde un double de la cle du hangar.',
      'Il ouvre son atelier a l aube.'
    )
  }
} | ConvertTo-Json -Depth 8
Invoke-WebRequest -UseBasicParsing -Method Post `
  -Uri 'http://127.0.0.1:8000/ingest' `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body $body
```

```powershell
$body = @{
  character_id='npc_jean'
  user_id='user_42'
  query='Que sait Jean sur la cle du hangar ?'
  top_k=5
  scope='global'
  return_text=$true
} | ConvertTo-Json -Depth 6
Invoke-WebRequest -UseBasicParsing -Method Post `
  -Uri 'http://127.0.0.1:8000/query' `
  -ContentType 'application/json' `
  -Body $body
```
