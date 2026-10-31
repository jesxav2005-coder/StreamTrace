from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "examate-rag"
    environment: str = "local"  # local | ci | production

    # LLM: any OpenAI-compatible API (OpenAI, Groq, OpenRouter, Gemini's OpenAI endpoint, ...)
    llm_api_key: str = ""
    llm_base_url: str = ""  # empty = the provider default (OpenAI)
    llm_primary_model: str = ""
    llm_fallback_model: str = ""  # optional; used when the primary model fails
    llm_timeout_seconds: float = 30.0

    # Price in USD per 1 million tokens. Leave at 0 for free tiers.
    primary_input_price_per_m: float = 0.0
    primary_output_price_per_m: float = 0.0
    fallback_input_price_per_m: float = 0.0
    fallback_output_price_per_m: float = 0.0

    # Postgres with the pgvector extension, used for code search
    database_url: str = ""
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768  # pgvector indexes support up to 2,000 dimensions

    # Every model call is appended here as one JSON line. Empty string = keep in memory only.
    usage_log_path: str = "logs/usage.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
