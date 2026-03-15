from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Intelligence Assistant"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "postgresql+psycopg://appuser:apppass@localhost:5432/ragdb"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_fallback_models: str = "qwen2.5:0.5b,qwen2.5:3b-instruct"
    embedding_model: str = "nomic-embed-text"
    qdrant_collection: str = "document_chunks"
    file_storage_path: str = "./storage"
    max_files_per_chat: int = 4
    max_file_size_mb: int = 25
    cors_origins: str = "http://localhost:3000"
    auto_create_tables: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ollama_model_candidates(self) -> list[str]:
        models = [self.ollama_model.strip()]
        models.extend(
            [item.strip() for item in self.ollama_fallback_models.split(",") if item.strip()]
        )
        deduped: list[str] = []
        for model in models:
            if model and model not in deduped:
                deduped.append(model)
        return deduped


@lru_cache
def get_settings() -> Settings:
    return Settings()
