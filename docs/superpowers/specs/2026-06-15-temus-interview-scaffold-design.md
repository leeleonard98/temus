# Temus Interview Starter Repo — Design

**Date:** 2026-06-15
**Author:** Prepared with Claude
**Purpose:** A minimal, working, test-driven scaffold so when the Temus interview starts tomorrow (2-hour build), the first commit is "Feature 1: …" rather than "set up project."

## Context

The Temus assessment hands the candidate a fresh repo and a feature list at the start of a 2-hour timed build, followed by a 1-hour code interview. The brief penalizes:

- Critical security flaws.
- Multiple features per commit (only the highest-scoring feature counts).
- Features without ≥3 non-trivial tests (no points).
- Inability to explain your own code (>3 failures = fail).

Tomorrow's actual feature list is unknown — only the candidate brief is in hand. The hint suggests a GenAI-first design. This scaffold therefore optimizes for **flexibility, fast time-to-first-feature-commit, and a test harness that makes "≥3 non-trivial tests" cheap to write.**

## Goals

1. `make up && make test` works green on a fresh checkout in <60s.
2. Adding a new feature (model + endpoint + 3 tests) takes <10 minutes including the commit.
3. No domain assumptions baked in — empty models, empty routers (besides health).
4. UI shell is a one-page React + shadcn surface that can render whatever the spec demands.
5. Backend test infra uses real Postgres (testcontainers) so tests catch Postgres-specific issues.
6. **No frontend tests** — confirmed not needed for tomorrow's features.
7. **Frontend is demo-only and must not break.** The UI's only job is to render backend responses cleanly and consistently for the interviewer. No client-side state machines, no optimistic updates, no fancy data fetching libs — every feature is a request → render. If a feature has no obvious UI need, it stays backend-only and is demoed via Swagger `/docs`; we do not invent UI for it.

## Non-Goals

- Auth, JWT, multi-tenancy middleware (add only if tomorrow's spec demands).
- Pre-installed Anthropic / OpenAI SDKs (pip-install on demand; 30s).
- CI / GitHub Actions (interview runs locally).
- Production Dockerfiles for backend/frontend (run with hot-reload locally).
- E2E / Playwright / Storybook.
- Pre-built domain models or example feature endpoints beyond `/health`.

## Architecture

```
temus/
├── docker-compose.yml          # postgres:16-alpine on :5432
├── Makefile                    # up/down/dev/test/migrate/lint/fmt
├── README.md                   # quickstart + interview demo flow
├── .env.example                # DATABASE_URL, etc.
├── .gitignore                  # .venv, node_modules, __pycache__, .env
├── backend/
│   ├── pyproject.toml          # deps + ruff + pytest config
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app, CORS, router mount, /health
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py       # pydantic-settings
│   │   │   └── deps.py         # get_session()
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py      # async engine + sessionmaker
│   │   │   ├── base.py         # DeclarativeBase
│   │   │   └── models/__init__.py   # empty — populated tomorrow
│   │   ├── schemas/__init__.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── health.py       # GET /api/v1/health
│   │   └── services/__init__.py
│   ├── alembic/
│   │   ├── env.py              # async-aware
│   │   ├── script.py.mako
│   │   └── versions/           # empty
│   ├── alembic.ini
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py         # pg container, async_session, client fixtures
│       ├── factories.py        # empty starter (factory_boy import wired)
│       └── test_health.py      # 3 non-trivial tests
└── frontend/
    ├── package.json            # vite, react, ts, tailwind, shadcn deps
    ├── tsconfig.json
    ├── vite.config.ts          # proxy /api -> :8000
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── components.json         # shadcn config
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx             # shell: sidebar + active feature card
        ├── index.css           # tailwind directives
        ├── features/
        │   └── HealthCard.tsx  # example FeatureCard usage
        ├── components/
        │   ├── FeatureCard.tsx # reusable card w/ idle|loading|ok|err states
        │   ├── ErrorBoundary.tsx
        │   └── ui/             # shadcn: button, card, input, skeleton
        └── lib/
            ├── api.ts          # fetch wrapper -> { ok, data, error }
            └── utils.ts        # cn() helper for shadcn
```

## Components

### docker-compose.yml

Single service: `postgres:16-alpine`.

- Port `5432:5432`.
- Env: `POSTGRES_DB=temus`, `POSTGRES_USER=temus`, `POSTGRES_PASSWORD=temus` (interview-local; not secrets).
- Named volume `temus_pgdata` so data survives `down` (use `down -v` to wipe).
- Healthcheck via `pg_isready`.

### Backend boot (`app/main.py`)

```python
app = FastAPI(title="Temus")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)
app.include_router(health.router, prefix="/api/v1")
```

No startup DB-table creation — Alembic owns schema.

### Database layer

- `db/session.py` — `create_async_engine(settings.database_url)` + `async_sessionmaker(expire_on_commit=False)`.
- `db/base.py` — `class Base(DeclarativeBase): pass`.
- `core/deps.py` — `async def get_session() -> AsyncSession` yields a session per request, closes after.

### Migrations (Alembic, async-aware)

- `alembic/env.py` is configured to run async (uses `engine.connect()` inside a sync wrapper, the standard async recipe).
- `target_metadata = Base.metadata` with `models` package imported so autogenerate sees them.
- Zero starter migrations — first `make migrate-new name=initial` after defining models tomorrow.

### Frontend (`frontend/src/App.tsx`)

A single page with:

- Header: "Temus" title.
- A `<Card>` showing API health (auto-fetched on mount via `lib/api.ts`).
- Vite dev-proxies `/api` → `http://localhost:8000`, so `fetch('/api/v1/health')` Just Works in dev.
- shadcn components pre-installed: `button`, `card`, `input`. Add more on demand with `npx shadcn@latest add <name>`.

### Frontend stability rules (don't break the demo)

The UI is demo-only. To keep it stable across whatever features land tomorrow:

- **One layout, one pattern.** Every feature renders inside the same shell: a left sidebar listing features, a main pane with a `<Card>` per feature. A feature is a form-on-top, result-below pattern. No routing library — sidebar clicks toggle which `<Card>` is active via a single `useState`. No surprise refactors mid-interview.
- **No global state, no client cache.** Every feature is a fresh `fetch` on submit. No React Query, no Redux, no Zustand. State per card is local `useState`. This eliminates the entire class of "stale cache" bugs that would otherwise eat interview time.
- **An `<ErrorBoundary>` wraps each feature card.** A thrown error in one card shows a red inline message in that card and leaves the rest of the app alive. The interviewer never sees a white screen.
- **`lib/api.ts` is the only place that talks to the backend.** Single fetch wrapper that returns `{ ok, data, error }` (never throws on HTTP errors). Components branch on `ok`; they never see a raw `Response` or an unhandled rejection.
- **Loading / empty / error states are first-class.** Every card renders one of: `idle | loading | success | error`, with shadcn `<Skeleton>` for loading and a muted "No data yet" for idle. No flicker, no layout shift.
- **TypeScript strict mode on, but `any` is allowed at API boundaries.** We type request/response shapes only when it doesn't slow us down; the backend is the source of truth for correctness.
- **No new heavy deps tomorrow.** Forms use plain `<form>` + `useState`. No formik, no react-hook-form, no zod-on-frontend. If a feature needs richer interaction, add it; otherwise stay boring.

### A reusable `<FeatureCard>` component

To make tomorrow's UI work mechanical, the scaffold ships one component:

```tsx
<FeatureCard title="Feature name" description="...">
  <FeatureCard.Form onSubmit={...}>{/* inputs */}</FeatureCard.Form>
  <FeatureCard.Result>{/* result | <Skeleton/> | <ErrorMsg/> */}</FeatureCard.Result>
</FeatureCard>
```

It owns the `idle | loading | success | error` state and the `<ErrorBoundary>`. Adding a new feature's UI is: copy a `<FeatureCard>`, change the inputs, point at the new endpoint. ~15 lines per feature.

### Test harness (`backend/tests/conftest.py`)

Three fixtures, each scaled appropriately:

- **`postgres_container`** (session scope) — `PostgresContainer("postgres:16-alpine").start()`. After it's up, run `alembic upgrade head` against its URL once. Yields the container; tears down at session end.
- **`async_session`** (function scope) — opens a session inside an outer transaction; on test teardown, rolls back. Each test sees a clean DB.
- **`client`** (function scope) — `httpx.AsyncClient(transport=ASGITransport(app=app))`, with `app.dependency_overrides[get_session]` pointed at the test session.

`tests/factories.py` is empty but imports `factory` so adding a factory tomorrow is just `class FooFactory(factory.Factory): ...`.

### The 3 starter tests (`tests/test_health.py`)

These exist to **verify the harness works** and to **template the patterns** you'll reuse 10+ times tomorrow:

1. **`test_health_returns_200_and_schema`** — full request, asserts status code and JSON shape `{"status": "healthy", "db": "connected"}`.
2. **`test_health_db_check_reports_connected`** — exercises the DB path: the endpoint runs `SELECT 1` against the test session; assert `db == "connected"`.
3. **`test_health_handles_db_failure_gracefully`** — overrides `get_session` to a session whose `execute()` raises `OperationalError`; assert response is 503 with `{"status": "degraded", "db": "disconnected"}`.

These three demonstrate, in order: response-shape testing, DB-touching tests, and dependency-override-for-failure-mode testing — the three patterns that will cover ~all of tomorrow's tests.

### Makefile targets

```
make up            # docker-compose up -d
make down          # docker-compose down
make logs          # docker-compose logs -f db
make dev           # parallel: backend + frontend (uses 'concurrently' or just &)
make backend       # cd backend && uvicorn app.main:app --reload --port 8000
make frontend      # cd frontend && npm run dev
make test          # cd backend && pytest --cov=app --cov-report=term-missing
make test-unit     # cd backend && pytest tests/unit -v   (dir created when needed)
make migrate       # cd backend && alembic upgrade head
make migrate-new name=X   # cd backend && alembic revision --autogenerate -m "$name"
make lint          # cd backend && ruff check .
make fmt           # cd backend && ruff format .
make install       # cd backend && pip install -e ".[dev]" && cd ../frontend && npm install
```

## Data flow

```
Browser (localhost:5173)
    │  fetch('/api/v1/health')
    ▼
Vite dev server (proxy /api → :8000)
    ▼
FastAPI (localhost:8000)  app/routers/health.py
    │  Depends(get_session)
    ▼
SQLAlchemy AsyncSession  →  asyncpg  →  Postgres (localhost:5432, container)
```

In tests, the Vite layer is absent; httpx ASGITransport calls the FastAPI app directly, and `get_session` is overridden to point at the testcontainer Postgres.

## Error handling

- FastAPI's default 422 on Pydantic validation errors — no custom handler.
- `/api/v1/health` catches `SQLAlchemyError` from the `SELECT 1` and returns 503 + `{"status": "degraded", "db": "disconnected"}`.
- No global exception handler in the scaffold — add one tomorrow if a feature needs it.

## Configuration

`.env.example` (copy to `.env`):

```
DATABASE_URL=postgresql+asyncpg://temus:temus@localhost:5432/temus
ENVIRONMENT=development
```

`app/core/config.py` uses `pydantic-settings` to load and type-check these. `Settings` is exposed as a module-level singleton so it can be imported anywhere.

## Trade-offs

| Decision | Cost | Benefit |
|----------|------|---------|
| testcontainers Postgres | First `make test` slow (~30s for image pull) | Real Postgres semantics; JSONB/enum/array tests work |
| Alembic from day one | Slight extra step on first model | No "switch to migrations later" debt; autogenerate works |
| No GenAI deps in scaffold | 30s install if needed | Don't carry weight you may not use; spec hint is a hint, not a guarantee |
| shadcn manual `add` per component | Tiny friction tomorrow | Pre-installing 50 components bloats the repo and slows `npm install` |
| No frontend tests | Less coverage if features hit UI | Confirmed unnecessary for tomorrow's spec; saves setup time |
| No global state / no React Query | Slightly more re-fetching | Eliminates stale-cache bugs; demo never shows wrong data |
| `<ErrorBoundary>` per FeatureCard | A few lines per card | One feature crashing never blanks the whole app mid-demo |
| No auth/tenant middleware in scaffold | Must add if spec demands | Avoids dragging in opinions that may not match the spec |

## Open questions

None at this point. The scaffold is deliberately small enough that all decisions are reversible in <5 minutes tomorrow.

## Git

The scaffold is committed to `main` as a single "scaffold: initial project setup" commit before the interview, so the timer starts with the candidate already on a clean working tree. Tomorrow's commits start at "feat: feature 1 — …". Push to a fresh GitHub repo before the interview begins.

## Success criteria

- `git clone <repo>`, `make install`, `make up`, `make test` → all green in under 2 minutes (after first run, <30s).
- `make dev` brings up backend at `:8000` and frontend at `:5173`. The frontend renders the sidebar shell with one "Health" feature card showing "API: healthy" via the shared `<FeatureCard>` component.
- The three starter tests pass; coverage report shows the health endpoint at 100%.
- Adding a hypothetical "Feature 1: GET /widgets returning a list" is achievable in <10 minutes, including model + migration + endpoint + 3 backend tests + a copy-pasted `<FeatureCard>` for the sidebar + commit.
- Killing the backend mid-demo and clicking a feature card shows a red inline error in that card, not a blank app.
