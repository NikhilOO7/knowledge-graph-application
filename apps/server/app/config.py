"""Centralised application configuration, loaded from environment / .env."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    port: int = 3000
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"

    # PostgreSQL
    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5433/knowledge_graph"
    )

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Context bucket routing
    bucket_match_threshold: float = 0.78

    # Extraction
    chunk_size: int = 2000
    chunk_overlap: int = 200

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_is_configured(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return True  # ollama assumed reachable locally


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
