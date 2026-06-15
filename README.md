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
backend/             FastAPI + SQLAlchemy async + Alembic + pytest (testcontainers)
frontend/            Vite + React + TS + Tailwind + shadcn/ui
docker-compose.yml   postgres:16-alpine on :5432
```

## Workflow during the interview

1. **Each feature gets its own commit.** The brief penalizes multi-feature commits.
2. **Each feature ships ≥3 non-trivial backend tests** in `tests/integration/test_<feature>.py` (and unit tests in `tests/unit/...` for service logic). Templates in `tests/integration/test_health.py` and `tests/unit/test_config.py`.
3. **UI per feature**: copy `frontend/src/features/HealthCard.tsx`, change inputs/endpoint, register in `App.tsx`'s `FEATURES` array. ~15 LOC.
4. **Backend-only features** are demoed via Swagger at <http://localhost:8000/docs>. Don't invent UI for them.

## Adding a model

```bash
# 1. Add the SQLAlchemy model in backend/app/db/models/<name>.py
# 2. Import it in backend/app/db/models/__init__.py so Alembic sees it
# 3. Generate the migration:
make migrate-new name=add_<thing>
# 4. Apply:
make migrate
```

## Conventions

- `lib/api.ts` is the only place that calls `fetch`. Components branch on `{ ok, data, error }`.
- Every `<FeatureCard>` is wrapped in `<ErrorBoundary>`. One feature crashing never blanks the demo.
- No global state; no React Query; no client-side cache. Each submit = fresh fetch.
- Backend tests follow Arrange-Act-Assert with descriptive names: `test_<thing>_<scenario>_<expected_result>`.

## Commands cheat sheet

| Command | What |
|---|---|
| `make up` / `down` | Postgres up/down |
| `make dev` | both servers in parallel |
| `make test` | pytest + coverage |
| `make migrate-new name=foo` | new alembic revision |
| `make lint` / `make fmt` | ruff |
