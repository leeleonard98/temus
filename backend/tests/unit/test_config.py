"""Unit tests for app.core.config.Settings."""
import os
from unittest.mock import patch

import pytest


def test_settings_reads_database_url_from_env() -> None:
    """Settings must pull DATABASE_URL from the environment."""
    with patch.dict(
        os.environ,
        {"DATABASE_URL": "postgresql+asyncpg://u:p@h:5432/d"},
        clear=False,
    ):
        from app.core.config import Settings

        s = Settings()
        assert s.database_url == "postgresql+asyncpg://u:p@h:5432/d"


def test_settings_defaults_environment_to_development() -> None:
    """ENVIRONMENT defaults to 'development' when unset."""
    env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
    env["DATABASE_URL"] = "postgresql+asyncpg://u:p@h:5432/d"
    with patch.dict(os.environ, env, clear=True):
        from app.core.config import Settings

        s = Settings()
        assert s.environment == "development"


def test_settings_missing_database_url_raises_validation_error() -> None:
    """Settings without DATABASE_URL is a configuration error.

    `_env_file=None` disables loading the project's .env files so this test
    truly exercises the missing-config path, not the file-fallback path.
    """
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    with patch.dict(os.environ, env, clear=True):
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None)
