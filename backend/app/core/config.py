"""Typed application settings loaded from environment / .env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env at the repo root (one level up from backend/) AND inside backend/.
# pydantic-settings tries each in order; first hit wins. Either layout works.
_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables (or .env in dev).
    """

    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    environment: str = "development"

    # OpenAI — leave key empty to force the offline stub path (tests, no-network dev).
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Langfuse — leave keys empty to disable tracing (tests, offline dev).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"


settings = Settings()  # module-level singleton
