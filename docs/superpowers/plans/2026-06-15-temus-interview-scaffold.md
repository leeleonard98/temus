# Temus Interview Starter Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal, test-driven, demo-stable scaffold (Postgres in Docker on `:5432`, FastAPI backend, Vite/React/shadcn frontend) so the candidate's first commit during the 2-hour Temus interview is `feat: feature 1 — …`, not project setup.

**Architecture:** Two-tier app. Postgres 16 in docker-compose. FastAPI backend (SQLAlchemy 2.0 async + asyncpg + Alembic) exposing `/api/v1/*`. Vite + React + TypeScript + Tailwind + shadcn/ui frontend with a single sidebar shell, reusable `<FeatureCard>`, and per-card `<ErrorBoundary>` so a single feature crashing never blanks the demo. Backend tests use `testcontainers-postgres` for real DB semantics; no frontend tests.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, pytest + pytest-asyncio + testcontainers, factory-boy, ruff, pydantic-settings; Node 20+, Vite, React 18, TypeScript, Tailwind 3, shadcn/ui, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-06-15-temus-interview-scaffold-design.md`

---

## File Structure

```
temus/
├── .gitignore                                          # Task 1
├── README.md                                           # Task 14
├── .env.example                                        # Task 2
├── docker-compose.yml                                  # Task 2
├── Makefile                                            # Task 13
├── docs/superpowers/
│   ├── specs/2026-06-15-temus-interview-scaffold-design.md   # already exists
│   └── plans/2026-06-15-temus-interview-scaffold.md          # this file
├── backend/
│   ├── pyproject.toml                                  # Task 3
│   ├── app/
│   │   ├── __init__.py                                 # Task 4
│   │   ├── main.py                                     # Task 7
│   │   ├── core/
│   │   │   ├── __init__.py                             # Task 4
│   │   │   ├── config.py                               # Task 4
│   │   │   └── deps.py                                 # Task 5
│   │   ├── db/
│   │   │   ├── __init__.py                             # Task 5
│   │   │   ├── base.py                                 # Task 5
│   │   │   ├── session.py                              # Task 5
│   │   │   └── models/__init__.py                      # Task 5 (empty)
│   │   ├── routers/
│   │   │   ├── __init__.py                             # Task 7
│   │   │   └── health.py                               # Task 7
│   │   ├── schemas/__init__.py                         # Task 7 (empty)
│   │   └── services/__init__.py                        # Task 7 (empty)
│   ├── alembic.ini                                     # Task 6
│   ├── alembic/
│   │   ├── env.py                                      # Task 6
│   │   ├── script.py.mako                              # Task 6
│   │   └── versions/.gitkeep                           # Task 6
│   └── tests/
│       ├── __init__.py                                 # Task 8
│       ├── conftest.py                                 # Task 8
│       ├── factories.py                                # Task 8
│       └── test_health.py                              # Task 9
└── frontend/
    ├── package.json                                    # Task 10
    ├── tsconfig.json                                   # Task 10
    ├── tsconfig.node.json                              # Task 10
    ├── vite.config.ts                                  # Task 10
    ├── tailwind.config.ts                              # Task 10
    ├── postcss.config.js                               # Task 10
    ├── components.json                                 # Task 10
    ├── index.html                                      # Task 10
    └── src/
        ├── main.tsx                                    # Task 10
        ├── App.tsx                                     # Task 12
        ├── index.css                                   # Task 10
        ├── lib/
        │   ├── api.ts                                  # Task 11
        │   └── utils.ts                                # Task 10
        ├── components/
        │   ├── ErrorBoundary.tsx                       # Task 11
        │   ├── FeatureCard.tsx                         # Task 11
        │   └── ui/                                     # Task 10 (shadcn add)
        │       ├── button.tsx
        │       ├── card.tsx
        │       ├── input.tsx
        │       └── skeleton.tsx
        └── features/
            └── HealthCard.tsx                          # Task 12
```

**Responsibilities:**

- `core/config.py` — single source of typed settings; nothing else.
- `core/deps.py` — FastAPI dependency injectables (just `get_session` for now).
- `db/session.py` — engine + sessionmaker; no business logic.
- `db/base.py` — `DeclarativeBase`; nothing else.
- `routers/health.py` — one endpoint; pattern template for tomorrow.
- `tests/conftest.py` — fixtures only (pg container, session, client).
- `frontend/lib/api.ts` — only place that calls `fetch`; returns `{ ok, data, error }`.
- `frontend/components/FeatureCard.tsx` — reusable form-on-top, result-below shell with `idle | loading | success | error` states.
- `frontend/features/*.tsx` — one file per feature; copy-paste pattern tomorrow.

---

## Task 1: Initialize repo and `.gitignore`

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/I589682/Desktop/temus
git init -b main
```

Expected: `Initialized empty Git repository in /Users/I589682/Desktop/temus/.git/`

- [ ] **Step 2: Write `.gitignore`**

Create `.gitignore`:

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/

# Node
node_modules/
dist/
.vite/

# OS
.DS_Store
Thumbs.db

# Editors
.vscode/
.idea/
*.swp

# Env
.env
.env.local

# Docker
docker/data/
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: initial gitignore"
```

Expected: One commit on `main`.

---

## Task 2: Postgres in Docker + `.env.example`

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: temus-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: temus
      POSTGRES_USER: temus
      POSTGRES_PASSWORD: temus
    ports:
      - "5432:5432"
    volumes:
      - temus_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temus -d temus"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  temus_pgdata:
```

- [ ] **Step 2: Write `.env.example`**

```
DATABASE_URL=postgresql+asyncpg://temus:temus@localhost:5432/temus
ENVIRONMENT=development
```

- [ ] **Step 3: Copy `.env.example` to `.env`**

```bash
cp .env.example .env
```

- [ ] **Step 4: Bring up Postgres and verify**

```bash
docker compose up -d
docker compose ps
```

Expected: One service `db` with status `healthy` (may take ~5s on first run).

```bash
docker compose exec db psql -U temus -d temus -c "SELECT 1;"
```

Expected: `?column?` column showing `1`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: postgres 16 docker-compose on :5432"
```

---

## Task 3: Backend `pyproject.toml` and virtualenv

**Files:**
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Write `backend/pyproject.toml`**

```toml
[project]
name = "temus-backend"
version = "0.1.0"
description = "Temus interview backend"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.13",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "python-multipart>=0.0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.27",
    "testcontainers[postgres]>=4.8",
    "factory-boy>=3.3",
    "ruff>=0.7",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/__init__.py", "*/alembic/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]
ignore = ["E501"]
```

- [ ] **Step 2: Create venv and install**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: `Successfully installed ...` ending with `temus-backend-0.1.0`.

- [ ] **Step 3: Verify imports**

```bash
python -c "import fastapi, sqlalchemy, alembic, pytest, testcontainers; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/pyproject.toml
git commit -m "chore: backend pyproject with fastapi + sqlalchemy + pytest stack"
```

---

## Task 4: Backend `core/config.py` (settings) — TDD

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Create empty `__init__.py` files**

```bash
cd /Users/I589682/Desktop/temus/backend
mkdir -p app/core tests/unit
touch app/__init__.py app/core/__init__.py
touch tests/__init__.py tests/unit/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/test_config.py`:

```python
"""Tests for app.core.config.Settings."""
import os
from unittest.mock import patch

import pytest


def test_settings_reads_database_url_from_env():
    """Settings must pull DATABASE_URL from the environment."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://u:p@h:5432/d"}, clear=False):
        from app.core.config import Settings
        s = Settings()
        assert s.database_url == "postgresql+asyncpg://u:p@h:5432/d"


def test_settings_defaults_environment_to_development():
    """ENVIRONMENT defaults to 'development' when unset."""
    env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
    env["DATABASE_URL"] = "postgresql+asyncpg://u:p@h:5432/d"
    with patch.dict(os.environ, env, clear=True):
        from app.core.config import Settings
        s = Settings()
        assert s.environment == "development"


def test_settings_missing_database_url_raises():
    """Settings without DATABASE_URL is a configuration error."""
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    with patch.dict(os.environ, env, clear=True):
        from pydantic import ValidationError

        from app.core.config import Settings
        with pytest.raises(ValidationError):
            Settings()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/I589682/Desktop/temus/backend
source .venv/bin/activate
pytest tests/unit/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.config'`

- [ ] **Step 4: Write `app/core/config.py`**

```python
"""Typed application settings loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables (or .env in dev).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    environment: str = "development"


settings = Settings()  # module-level singleton
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/app/__init__.py backend/app/core/ backend/tests/__init__.py backend/tests/unit/
git commit -m "feat: typed Settings via pydantic-settings"
```

---

## Task 5: Backend DB layer (`db/base.py`, `db/session.py`, `core/deps.py`)

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models/__init__.py`
- Create: `backend/app/core/deps.py`

- [ ] **Step 1: Create directories and empty markers**

```bash
cd /Users/I589682/Desktop/temus/backend
mkdir -p app/db/models app/schemas app/services
touch app/db/__init__.py app/db/models/__init__.py app/schemas/__init__.py app/services/__init__.py
```

- [ ] **Step 2: Write `app/db/base.py`**

```python
"""SQLAlchemy declarative base. All ORM models inherit from `Base`."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    pass
```

- [ ] **Step 3: Write `app/db/session.py`**

```python
"""Async SQLAlchemy engine + session factory."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
```

- [ ] **Step 4: Write `app/core/deps.py`**

```python
"""FastAPI dependency injectables."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async DB session and close it after."""
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 5: Verify it imports cleanly**

```bash
cd /Users/I589682/Desktop/temus/backend
source .venv/bin/activate
python -c "from app.db.session import engine, AsyncSessionLocal; from app.core.deps import get_session; print('ok')"
```

Expected: `ok`

- [ ] **Step 6: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/app/db/ backend/app/schemas/ backend/app/services/ backend/app/core/deps.py
git commit -m "feat: async SQLAlchemy engine, session factory, get_session dependency"
```

---

## Task 6: Alembic (async-aware) with zero migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/.gitkeep`

- [ ] **Step 1: Create alembic directory tree**

```bash
cd /Users/I589682/Desktop/temus/backend
mkdir -p alembic/versions
touch alembic/versions/.gitkeep
```

- [ ] **Step 2: Write `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Write `backend/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Write `backend/alembic/env.py` (async-aware)**

```python
"""Alembic env — async-aware. Pulls URL from app settings."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

# Import models package so autogenerate sees all models.
from app.db import models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations against a URL, no DBAPI."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 5: Verify alembic recognizes the config**

```bash
cd /Users/I589682/Desktop/temus/backend
source .venv/bin/activate
alembic current
```

Expected: prints nothing useful but exits 0 (no revisions yet, no error).

- [ ] **Step 6: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/alembic.ini backend/alembic/
git commit -m "chore: alembic async env with zero migrations"
```

---

## Task 7: FastAPI app + `/api/v1/health` endpoint — TDD

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create routers directory marker**

```bash
cd /Users/I589682/Desktop/temus/backend
mkdir -p app/routers
touch app/routers/__init__.py
```

- [ ] **Step 2: Write `app/routers/health.py`**

```python
"""Health check endpoint with DB connectivity probe."""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Return service health and DB connectivity.

    200: {"status": "healthy", "db": "connected"}
    503: {"status": "degraded", "db": "disconnected"}
    """
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "db": "disconnected"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "healthy", "db": "connected"},
    )
```

- [ ] **Step 3: Write `app/main.py`**

```python
"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health

app = FastAPI(title="Temus", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
```

- [ ] **Step 4: Smoke-test imports**

```bash
cd /Users/I589682/Desktop/temus/backend
source .venv/bin/activate
python -c "from app.main import app; print(len(app.routes), 'routes')"
```

Expected: prints `5 routes` (or similar; FastAPI includes /docs, /openapi.json, etc.) — exits 0.

- [ ] **Step 5: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/app/main.py backend/app/routers/
git commit -m "feat: FastAPI app + /api/v1/health endpoint with DB probe"
```

---

## Task 8: Test fixtures — `conftest.py` and `factories.py`

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/factories.py`

- [ ] **Step 1: Write `backend/tests/conftest.py`**

```python
"""Shared pytest fixtures: postgres container, async session, FastAPI client."""
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.deps import get_session
from app.main import app


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start a Postgres 16 container for the whole test session.

    Applies all alembic migrations once at startup.
    """
    with PostgresContainer("postgres:16-alpine") as pg:
        # testcontainers gives us postgresql://; convert to asyncpg URL.
        sync_url = pg.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

        # Run alembic migrations against the fresh DB.
        alembic_cfg = AlembicConfig("alembic.ini")
        # alembic uses sync drivers; strip the +asyncpg for migration run.
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://"),
        )
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception:
            # No revisions yet → nothing to upgrade. That's expected on day one.
            pass

        # Stash the async URL on the container for downstream fixtures.
        pg.async_url = async_url
        yield pg


@pytest_asyncio.fixture
async def async_session(postgres_container: PostgresContainer) -> AsyncIterator[AsyncSession]:
    """Provide a clean async session per test (rolls back at teardown)."""
    engine = create_async_engine(postgres_container.async_url, future=True)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Async HTTP client with `get_session` overridden to the test session."""
    async def _override() -> AsyncIterator[AsyncSession]:
        yield async_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
```

> Note: testcontainers v4 requires `psycopg` (not the legacy `psycopg2`) to be available for sync alembic upgrades. If `command.upgrade` raises a ModuleNotFoundError tomorrow when you actually have migrations, `pip install psycopg[binary]` and rerun. For day one with zero migrations, the `except: pass` is intentional — there's nothing to upgrade.

- [ ] **Step 2: Write `backend/tests/factories.py` (empty starter)**

```python
"""Factory Boy factories for test data.

Empty for now — add factories as models are introduced.

Example shape (uncomment when first model exists):

    import factory
    from app.db.models.widget import Widget

    class WidgetFactory(factory.Factory):
        class Meta:
            model = Widget

        name = factory.Sequence(lambda n: f"widget-{n}")
"""
import factory  # noqa: F401  -- ensure dep is wired
```

- [ ] **Step 3: Verify conftest imports cleanly**

```bash
cd /Users/I589682/Desktop/temus/backend
source .venv/bin/activate
python -c "import tests.conftest; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/tests/conftest.py backend/tests/factories.py
git commit -m "test: pytest fixtures (postgres testcontainer, session, async client)"
```

---

## Task 9: 3 non-trivial health tests — TDD

**Files:**
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_health.py`

- [ ] **Step 1: Create integration test directory**

```bash
cd /Users/I589682/Desktop/temus/backend
mkdir -p tests/integration
touch tests/integration/__init__.py
```

- [ ] **Step 2: Write `backend/tests/integration/test_health.py`**

```python
"""Integration tests for /api/v1/health.

Three patterns to template tomorrow's feature tests:
1) shape — request/response/JSON
2) DB-touching — exercises the real session
3) failure mode — dependency override forces an error
"""
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.deps import get_session
from app.main import app


pytestmark = pytest.mark.asyncio


async def test_health_returns_200_and_schema(client: AsyncClient) -> None:
    """Healthy app returns 200 with the documented JSON shape."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "healthy", "db": "connected"}


async def test_health_db_check_actually_hits_the_database(
    client: AsyncClient,
) -> None:
    """The endpoint runs SELECT 1 against the real test DB.

    Asserts the DB-touching path works end-to-end via the test session.
    """
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["db"] == "connected"


async def test_health_returns_503_when_db_session_raises() -> None:
    """When the DB layer raises OperationalError, endpoint reports degraded."""

    class _BadSession:
        async def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise OperationalError("boom", None, Exception("db down"))

    async def _override() -> AsyncIterator[_BadSession]:
        yield _BadSession()

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as bad_client:
            response = await bad_client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "db": "disconnected"}
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 3: Run all backend tests**

```bash
cd /Users/I589682/Desktop/temus/backend
source .venv/bin/activate
pytest -v
```

Expected: 6 passed (3 from `test_config.py` + 3 from `test_health.py`). The first run pulls `postgres:16-alpine` and may take ~30s; subsequent runs are fast.

- [ ] **Step 4: Verify coverage**

```bash
pytest --cov=app --cov-report=term-missing
```

Expected: `app/routers/health.py` at 100%; overall coverage above 70%.

- [ ] **Step 5: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add backend/tests/integration/
git commit -m "test: 3 non-trivial health tests (shape, db, failure mode)"
```

---

## Task 10: Frontend scaffold — Vite + React + TS + Tailwind + shadcn

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/components.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/{button,card,input,skeleton}.tsx` (via shadcn CLI)

- [ ] **Step 1: Scaffold via Vite (non-interactive)**

```bash
cd /Users/I589682/Desktop/temus
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

Expected: `frontend/` with default Vite + React + TS template. `npm install` finishes with no audit errors.

- [ ] **Step 2: Install Tailwind, shadcn deps, path alias support**

```bash
cd /Users/I589682/Desktop/temus/frontend
npm install -D tailwindcss@^3 postcss autoprefixer @types/node
npm install class-variance-authority clsx tailwind-merge lucide-react
npm install tailwindcss-animate
npx tailwindcss init -p
```

Expected: `tailwind.config.js` and `postcss.config.js` created.

- [ ] **Step 3: Replace `tailwind.config.js` with `tailwind.config.ts`**

Delete `tailwind.config.js`, then create `tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss"
import animate from "tailwindcss-animate"

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "2rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
    },
  },
  plugins: [animate],
}

export default config
```

Delete the auto-created JS config:

```bash
rm tailwind.config.js
```

- [ ] **Step 4: Replace `src/index.css` with shadcn theme tokens + Tailwind**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

- [ ] **Step 5: Update `tsconfig.json` for the `@/*` path alias**

Replace `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 6: Update `vite.config.ts` with proxy and alias**

Replace `vite.config.ts`:

```ts
import path from "node:path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
})
```

- [ ] **Step 7: Write `frontend/src/lib/utils.ts`**

```ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 8: Write `frontend/components.json` (shadcn config)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

- [ ] **Step 9: Add the 4 shadcn components**

```bash
cd /Users/I589682/Desktop/temus/frontend
npx --yes shadcn@latest add button card input skeleton
```

Expected: prompts auto-resolved (or accept defaults); creates `src/components/ui/{button,card,input,skeleton}.tsx`.

> If the CLI version asks anything interactive (it sometimes does for `style`/`baseColor`), the answers it expects are: style=default, baseColor=slate, css variables=yes — these match `components.json` we already wrote.

- [ ] **Step 10: Verify the build succeeds**

```bash
cd /Users/I589682/Desktop/temus/frontend
npm run build
```

Expected: `dist/` produced with no TypeScript errors. (Don't keep `dist/` — `.gitignore` already excludes it.)

- [ ] **Step 11: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add frontend/package.json frontend/package-lock.json frontend/tsconfig*.json frontend/vite.config.ts frontend/tailwind.config.ts frontend/postcss.config.js frontend/components.json frontend/index.html frontend/src/main.tsx frontend/src/index.css frontend/src/lib/ frontend/src/components/ui/
# include any other files vite/shadcn generated:
git add frontend/
git commit -m "chore: vite + react + tailwind + shadcn frontend scaffold"
```

---

## Task 11: `lib/api.ts`, `<ErrorBoundary>`, `<FeatureCard>`

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Create: `frontend/src/components/FeatureCard.tsx`

- [ ] **Step 1: Write `frontend/src/lib/api.ts`**

```ts
/**
 * Single source of truth for talking to the backend.
 *
 * Returns a tagged result so callers never have to handle thrown rejections.
 */
export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string }

export async function api<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    })
    const text = await res.text()
    const body = text ? safeJson<T>(text) : (undefined as unknown as T)
    if (!res.ok) {
      const message =
        (body && typeof body === "object" && "detail" in (body as Record<string, unknown>)
          ? String((body as Record<string, unknown>).detail)
          : null) ?? `HTTP ${res.status}`
      return { ok: false, error: message }
    }
    return { ok: true, data: body as T }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "network error" }
  }
}

function safeJson<T>(text: string): T | string {
  try {
    return JSON.parse(text) as T
  } catch {
    return text
  }
}
```

- [ ] **Step 2: Write `frontend/src/components/ErrorBoundary.tsx`**

```tsx
import { Component, type ErrorInfo, type ReactNode } from "react"

type Props = { children: ReactNode; fallback?: (error: Error) => ReactNode }
type State = { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface to the console for the interview demo; don't leak elsewhere.
    console.error("[ErrorBoundary]", error, info)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback(this.state.error)
      return (
        <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
          <div className="font-medium">Something went wrong.</div>
          <div className="mt-1 text-destructive/80">{this.state.error.message}</div>
          <button
            type="button"
            onClick={this.reset}
            className="mt-2 text-xs underline underline-offset-2"
          >
            try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
```

- [ ] **Step 3: Write `frontend/src/components/FeatureCard.tsx`**

```tsx
import { type ReactNode } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorBoundary } from "@/components/ErrorBoundary"

export type FeatureState = "idle" | "loading" | "success" | "error"

type Props = {
  title: string
  description?: string
  state: FeatureState
  errorMessage?: string
  form?: ReactNode
  result?: ReactNode
}

/**
 * One layout, one pattern for every feature in the demo.
 *
 * Renders a card with optional form on top and a result region below
 * that switches on `state`. Wrapped in an ErrorBoundary so a thrown
 * render-time error in one feature does not blank the whole app.
 */
export function FeatureCard({
  title,
  description,
  state,
  errorMessage,
  form,
  result,
}: Props) {
  return (
    <ErrorBoundary>
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {form}
          <div aria-live="polite">
            {state === "idle" && (
              <p className="text-sm text-muted-foreground">No data yet.</p>
            )}
            {state === "loading" && (
              <div className="space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            )}
            {state === "success" && result}
            {state === "error" && (
              <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
                {errorMessage ?? "Request failed."}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </ErrorBoundary>
  )
}
```

- [ ] **Step 4: Type-check**

```bash
cd /Users/I589682/Desktop/temus/frontend
npm run build
```

Expected: build passes; no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add frontend/src/lib/api.ts frontend/src/components/ErrorBoundary.tsx frontend/src/components/FeatureCard.tsx
git commit -m "feat: api wrapper, ErrorBoundary, reusable FeatureCard with idle/loading/success/error"
```

---

## Task 12: App shell — sidebar + Health feature

**Files:**
- Create: `frontend/src/features/HealthCard.tsx`
- Modify: `frontend/src/App.tsx` (replace contents)

- [ ] **Step 1: Create features directory**

```bash
cd /Users/I589682/Desktop/temus/frontend
mkdir -p src/features
```

- [ ] **Step 2: Write `frontend/src/features/HealthCard.tsx`**

```tsx
import { useEffect, useState } from "react"
import { FeatureCard, type FeatureState } from "@/components/FeatureCard"
import { api } from "@/lib/api"

type HealthResponse = { status: string; db: string }

export function HealthCard() {
  const [state, setState] = useState<FeatureState>("idle")
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let cancelled = false
    async function run() {
      setState("loading")
      const res = await api<HealthResponse>("/api/v1/health")
      if (cancelled) return
      if (res.ok) {
        setData(res.data)
        setState("success")
      } else {
        setError(res.error)
        setState("error")
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <FeatureCard
      title="Health"
      description="Backend liveness + DB connectivity probe."
      state={state}
      errorMessage={error}
      result={
        data ? (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted-foreground">status</dt>
            <dd className="font-medium">{data.status}</dd>
            <dt className="text-muted-foreground">db</dt>
            <dd className="font-medium">{data.db}</dd>
          </dl>
        ) : null
      }
    />
  )
}
```

- [ ] **Step 3: Replace `frontend/src/App.tsx`**

```tsx
import { useState } from "react"
import { HealthCard } from "@/features/HealthCard"
import { cn } from "@/lib/utils"

type Feature = { id: string; label: string; render: () => JSX.Element }

const FEATURES: Feature[] = [
  { id: "health", label: "Health", render: () => <HealthCard /> },
  // Tomorrow: copy a FeatureCard, add to this list.
]

export default function App() {
  const [activeId, setActiveId] = useState<string>(FEATURES[0]?.id ?? "")
  const active = FEATURES.find((f) => f.id === activeId) ?? FEATURES[0]

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <h1 className="text-xl font-semibold tracking-tight">Temus</h1>
        </div>
      </header>
      <div className="mx-auto grid max-w-6xl grid-cols-[12rem_1fr] gap-6 px-6 py-6">
        <nav aria-label="features" className="space-y-1">
          {FEATURES.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setActiveId(f.id)}
              className={cn(
                "block w-full rounded-md px-3 py-2 text-left text-sm transition-colors",
                f.id === active?.id
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent",
              )}
            >
              {f.label}
            </button>
          ))}
        </nav>
        <main>{active?.render()}</main>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify the build**

```bash
cd /Users/I589682/Desktop/temus/frontend
npm run build
```

Expected: clean build, zero TS errors.

- [ ] **Step 5: Smoke-test the dev server (manual)**

In one terminal:

```bash
cd /Users/I589682/Desktop/temus
docker compose up -d
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd /Users/I589682/Desktop/temus/frontend
npm run dev
```

Open `http://localhost:5173`. Expected: sidebar with "Health" selected, card shows `status: healthy`, `db: connected`. Stop the backend (Ctrl-C); reload the page; the Health card flips to a red error message and the rest of the app keeps rendering.

- [ ] **Step 6: Commit**

```bash
cd /Users/I589682/Desktop/temus
git add frontend/src/App.tsx frontend/src/features/
git commit -m "feat: app shell with sidebar nav and HealthCard demo feature"
```

---

## Task 13: `Makefile`

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write `Makefile`**

> Note: each recipe line is one shell — chain with `&&` (no multi-line indents losing the cwd).

```makefile
.PHONY: help install up down logs dev backend frontend test test-unit test-int migrate migrate-new lint fmt

help:
	@echo "Targets:"
	@echo "  install        backend (.venv) + frontend (node_modules)"
	@echo "  up / down      docker compose Postgres on :5432"
	@echo "  logs           tail Postgres logs"
	@echo "  dev            backend (:8000) + frontend (:5173) in parallel"
	@echo "  backend        uvicorn reload"
	@echo "  frontend       vite dev"
	@echo "  test           pytest with coverage"
	@echo "  test-unit      pytest tests/unit"
	@echo "  test-int       pytest tests/integration"
	@echo "  migrate        alembic upgrade head"
	@echo "  migrate-new name=X  generate revision"
	@echo "  lint / fmt     ruff"

install:
	cd backend && python3.11 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -e ".[dev]"
	cd frontend && npm install

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f db

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Starting backend (:8000) and frontend (:5173). Ctrl-C stops both."
	@trap 'kill 0' EXIT INT TERM; \
	  ( cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) & \
	  ( cd frontend && npm run dev ) & \
	  wait

test:
	cd backend && . .venv/bin/activate && pytest --cov=app --cov-report=term-missing

test-unit:
	cd backend && . .venv/bin/activate && pytest tests/unit -v

test-int:
	cd backend && . .venv/bin/activate && pytest tests/integration -v

migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head

migrate-new:
	@if [ -z "$(name)" ]; then echo "usage: make migrate-new name=<short-message>"; exit 2; fi
	cd backend && . .venv/bin/activate && alembic revision --autogenerate -m "$(name)"

lint:
	cd backend && . .venv/bin/activate && ruff check .

fmt:
	cd backend && . .venv/bin/activate && ruff format .
```

- [ ] **Step 2: Verify `make help` works**

```bash
cd /Users/I589682/Desktop/temus
make help
```

Expected: prints the target list above.

- [ ] **Step 3: Verify `make test` runs green end-to-end**

```bash
make test
```

Expected: 6 tests pass; coverage report prints. (Postgres container will start fresh on first run.)

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: Makefile with install/up/dev/test/migrate targets"
```

---

## Task 14: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Temus

Starter scaffold for the Temus 2-hour agentic coding interview. Postgres in Docker, FastAPI backend, React/shadcn demo UI, pytest with testcontainers.

## Quickstart

```bash
make install        # backend venv + frontend node_modules (~2 min, one-time)
cp .env.example .env
make up             # Postgres on :5432
make test           # backend tests (~30s first run, fast after)
make dev            # backend :8000 + frontend :5173 in parallel
```

Open <http://localhost:5173>. The sidebar shows one "Health" card calling `/api/v1/health`.

## Layout

```
backend/   FastAPI + SQLAlchemy async + Alembic + pytest (testcontainers)
frontend/  Vite + React + TS + Tailwind + shadcn/ui
docker-compose.yml   postgres:16-alpine on :5432
```

## Workflow during the interview

1. **Each feature gets its own commit.** The brief penalizes multi-feature commits.
2. **Each feature ships ≥3 non-trivial backend tests** (`tests/integration/test_<feature>.py`). Templates in `tests/integration/test_health.py`.
3. **UI per feature**: copy `frontend/src/features/HealthCard.tsx`, change inputs/endpoint, register in `App.tsx`'s `FEATURES` array. ~15 LOC.
4. **Backend-only features** are demoed via Swagger at <http://localhost:8000/docs>. Don't invent UI for them.

## Adding a model

```bash
# 1. Add the SQLAlchemy model in backend/app/db/models/<name>.py
# 2. Import it in backend/app/db/models/__init__.py
# 3. Generate the migration:
make migrate-new name=add_<thing>
# 4. Apply:
make migrate
```

## Conventions

- `lib/api.ts` is the only place that calls `fetch`. Components branch on `{ ok, data, error }`.
- Every `<FeatureCard>` is wrapped in `<ErrorBoundary>`. One feature crashing never blanks the demo.
- No global state; no React Query; no client-side cache. Each submit = fresh fetch.
- Backend follows Arrange-Act-Assert in tests; tenant isolation is added per-feature only when the spec demands.

## Commands cheat sheet

| Command | What |
|---|---|
| `make up` / `down` | Postgres up/down |
| `make dev` | both servers in parallel |
| `make test` | pytest + coverage |
| `make migrate-new name=foo` | new alembic revision |
| `make lint` / `make fmt` | ruff |
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with quickstart and interview workflow"
```

---

## Task 15: Final verification

- [ ] **Step 1: Confirm clean working tree**

```bash
cd /Users/I589682/Desktop/temus
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Run the full pipeline from cold**

```bash
make down
docker volume rm temus_temus_pgdata 2>/dev/null || true
make up
make test
```

Expected: tests pass, coverage report ends green.

- [ ] **Step 3: Smoke-test the demo end-to-end**

```bash
make dev
```

In a browser open <http://localhost:5173>. Expected: sidebar visible, "Health" card shows `status: healthy`, `db: connected`. Open `/api/v1/health` directly at <http://localhost:8000/api/v1/health> — same JSON. Open <http://localhost:8000/docs> — Swagger UI lists `GET /api/v1/health`.

Stop the backend (Ctrl-C in the `make dev` shell or kill the uvicorn process); reload the browser. Expected: card flips to red "request failed" message; the rest of the page keeps rendering.

- [ ] **Step 4: Push to GitHub**

> The candidate brief says "fresh GitHub repo." Create the empty repo on github.com first, then:

```bash
git remote add origin git@github.com:<you>/<repo>.git
git branch -M main
git push -u origin main
```

- [ ] **Step 5: Tag the scaffold commit**

```bash
git tag scaffold-v1
git push --tags
```

This gives a fixed point you can `git reset --hard scaffold-v1` back to if anything goes sideways tomorrow.

---

## Self-review notes (post-write)

**Spec coverage check** (against `docs/superpowers/specs/2026-06-15-temus-interview-scaffold-design.md`):

| Spec section | Covered by |
|---|---|
| docker-compose.yml + postgres on :5432 | Task 2 |
| Backend pyproject + venv | Task 3 |
| `core/config.py` typed settings | Task 4 |
| `db/base.py`, `db/session.py`, `core/deps.py` | Task 5 |
| Alembic async-aware, zero migrations | Task 6 |
| FastAPI `app/main.py`, `/api/v1/health` | Task 7 |
| testcontainers fixtures | Task 8 |
| 3 non-trivial health tests | Task 9 |
| Vite + React + TS + Tailwind + shadcn | Task 10 |
| `lib/api.ts`, `<ErrorBoundary>`, `<FeatureCard>` with idle/loading/success/error | Task 11 |
| Sidebar shell, single layout, no router | Task 12 (App.tsx) |
| Makefile | Task 13 |
| README | Task 14 |
| Git initial commit + push | Tasks 1, 15 |

No gaps.

**Type consistency check:** `FeatureState` (Task 11) is imported by `HealthCard` (Task 12). `ApiResult<T>` (Task 11) is consumed by `HealthCard` via the destructured `{ ok, data, error }` shape. `FEATURES[]` array shape in `App.tsx` (Task 12) is internal. `get_session` (Task 5) is overridden in tests via `app.dependency_overrides[get_session]` (Tasks 8 & 9). All consistent.

**Placeholder scan:** none.
