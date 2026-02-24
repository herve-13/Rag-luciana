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
    db_name: str = "rag_luciana"
    db_user: str = "rag"
    db_password: str = "change-me"

    # ── Qdrant ───────────────────────────────────────────
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333

    # ── Ollama ───────────────────────────────────────────
    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    ollama_embed_model: str = "nomic-embed-text"

    # ── API ──────────────────────────────────────────────
    api_port: int = 8000
    admin_key: str = "super-secret-admin-key"

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
