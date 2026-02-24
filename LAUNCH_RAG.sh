#!/bin/bash
# Script de lancement RAG Luciana (WSL)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

# 1. Qdrant
log "Demarrage Qdrant..."
if curl -fs http://127.0.0.1:6333/healthz > /dev/null 2>&1; then
    log "Qdrant deja actif sur :6333"
else
    if [ ! -x /opt/qdrant/qdrant ]; then
        log "Installation Qdrant dans /opt/qdrant..."
        mkdir -p /opt/qdrant
        curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz \
            -o /opt/qdrant/qdrant.tar.gz
        tar -xzf /opt/qdrant/qdrant.tar.gz -C /opt/qdrant
        chmod +x /opt/qdrant/qdrant
    fi
    cd /opt/qdrant
    QDRANT__SERVICE__HTTP_PORT=6333 \
    QDRANT__SERVICE__GRPC_PORT=6334 \
    QDRANT__STORAGE__STORAGE_PATH=/opt/qdrant/storage \
    nohup ./qdrant > /opt/qdrant/qdrant.log 2>&1 &
    for i in $(seq 1 30); do
        if curl -fs http://127.0.0.1:6333/healthz > /dev/null 2>&1; then
            log "OK: Qdrant (127.0.0.1:6333)"
            break
        fi
        sleep 1
    done
    cd "$SCRIPT_DIR"
fi

# 2. API RAG Luciana
log "Demarrage API RAG Luciana..."
if curl -fs http://127.0.0.1:8002/healthz > /dev/null 2>&1; then
    log "API RAG deja active sur :8002"
else
    if [ ! -d venv_wsl ]; then
        python3 -m venv venv_wsl
    fi
    VENV_PY="$SCRIPT_DIR/venv_wsl/bin/python"
    "$VENV_PY" -m pip -q install --upgrade pip > /dev/null 2>&1 || true
    "$VENV_PY" -m pip -q install -e . > /dev/null 2>&1 || true
    nohup env PYTHONPATH="$SCRIPT_DIR/src" \
        "$VENV_PY" -m uvicorn rag_luciana.api.main:app --host 0.0.0.0 --port 8002 \
        > "$SCRIPT_DIR/rag_luciana.log" 2>&1 &
    for i in $(seq 1 45); do
        if curl -fs http://127.0.0.1:8002/healthz > /dev/null 2>&1; then
            log "OK: RAG Luciana (127.0.0.1:8002)"
            break
        fi
        sleep 1
    done
fi

# 3. Verification finale
log "Verification readyz..."
READYZ="$(curl -s http://127.0.0.1:8002/readyz || true)"
log "readyz: $READYZ"
log "Done."
