"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── MariaDB ──────────────────────────────────────────
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "chatfriends_retrieval"
    db_user: str = "rag"
    db_password: str = "change-me"

    # ── Qdrant ───────────────────────────────────────────
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333

    # ── Ollama ───────────────────────────────────────────
    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    ollama_embed_model: str = "nomic-embed-text"
    hybrid_enabled: bool = True
    sparse_enabled: bool = True
    sparse_model: str = "Qdrant/bm25"
    sparse_top_terms_log: int = 12
    sparse_min_weight_log: float = 0.0
    prewarm_sparse_on_startup: bool = True
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rrf_k: int = 60
    rrf_k_hybrid: int = 60
    reranker_candidate_multiplier: int = 3
    reranker_device: str | None = None
    reranker_batch_size: int = 16
    reranker_max_length: int = 512
    reranker_trust_remote_code: bool = False
    prewarm_embeddings_on_startup: bool = True
    prewarm_reranker_on_startup: bool = True
    startup_prewarm_timeout_seconds: float = 20.0

    # ── API ──────────────────────────────────────────────
    api_port: int = 8000
    admin_key: str = "super-secret-admin-key"
    default_tenant_id: str = "herve"
    default_tenant_label: str = "Client Hervé"
    default_assistant_id: str = "default"
    rag_ingestion_enabled: bool = True
    qdrant_tenant_scoped_collections: bool = False

    # ── Derived ──────────────────────────────────────────
    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def ollama_base_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"


settings = Settings()
