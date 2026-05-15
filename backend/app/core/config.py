from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_port: int = 8000
    app_secret_key: str = "change-me"

    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""

    # ── Google OAuth ─────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── Groq ─────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Gemini ───────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # ── Web Search ───────────────────────────────────────────────────────────
    tavily_api_key: str = ""
    tavily_daily_limit: int = 900           # switch to Brave before hitting 1000
    brave_search_api_key: str = ""

    # ── Embeddings ───────────────────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── RAG ──────────────────────────────────────────────────────────────────
    semantic_chunk_threshold: float = 0.75
    max_chunk_size: int = 800
    chunk_overlap: int = 100
    rag_top_k: int = 8

    # ── Student Portal ───────────────────────────────────────────────────────
    portal_enabled: bool = False
    portal_url: str = "https://studentportal.diu.edu.bd"

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # ── Computed helpers ─────────────────────────────────────────────────────
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def groq_api_keys(self) -> list[str]:
        keys = [self.groq_api_key, self.groq_api_key_2, self.groq_api_key_3]
        return [k for k in keys if k]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
