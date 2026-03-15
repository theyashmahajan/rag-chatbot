from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://appuser:apppass@localhost:5432/ragdb"
    qdrant_url: str = "http://localhost:6333"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    qdrant_collection: str = "document_chunks"
    file_storage_path: str = "./storage"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = WorkerSettings()
