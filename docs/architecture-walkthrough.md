# AuraWealth — Architecture Walkthrough

> **Audience:** You. This is the document to read when you want to remember
> *why* a piece of the system looks the way it does, not what features it has.
> Scope is everything implemented through Phase 5 of the master plan; later
> phases are flagged where they introduce new structure.

---

## How to read this doc

Three layers, each goes deeper than the last:

1. **Mental models** — the few ideas that, if you hold them, the rest of the
   system explains itself.
2. **Subsystem walkthroughs** — code path + data model + decisions, one
   subsystem at a time.
3. **Why-this-not-that** — recurring trade-offs and the answers we picked.

Skim layer 1, dive into layer 2 for the part you're touching, and use layer
3 when you find yourself second-guessing a choice.

---

## Layer 1 — Mental models

### The product is two surfaces over one backend

Both **Client (Financial GPS)** and **Advisor (Command Center)** talk to the
same FastAPI service, the same Postgres tables, the same agents. The only
things that differ per role are:

- The system prompt the LLM gets.
- The UI shell (header colour, available pages, available tools).
- The agents an orchestrator may route to (some are advisor-only, e.g.
  rebalance proposal).

That's it. There is no per-role schema branching, no separate API surface,
no separate deployment.

### Streaming is the default communication mode

All long-running responses use SSE (`text/event-stream`):

- Chat token deltas (`/api/v1/chat`).
- Live price ticks (`/api/v1/prices/stream`, AC6).
- Long agent runs that publish progress to the UI.

We do not use websockets. SSE is one-way, runs over plain HTTP, survives
proxies, and FastAPI streams it natively via `StreamingResponse`. If we ever
need bidirectional, we'd add a `/ws` route alongside, not replace SSE.

### Persistence shape is "small ORM, big SQL"

Models are deliberately thin: ID, foreign keys, enums, timestamps. We don't
hide complex queries behind ORM relationships when SQL says it more clearly.
The `chunks` table will be queried with `<=>`, `<->`, and `tsvector @@`
operators directly — there's no `chunk.semantic_neighbors()` method.

This is intentional: it keeps the data layer easy to reason about, makes
performance work obvious (you can read the SQL), and keeps the model files
small enough to read at a glance.

### One LLM service, one stub fallback

`app/services/llm.py` is the *only* place that talks to OpenAI. Routers and
agents import `stream_chat`. If `OPENAI_API_KEY` is empty, the same function
yields a deterministic `[stub] echo: <last user msg>` token-by-token.

The stub is the single most important piece of test infrastructure in the
project:

- CI runs hermetically with no key, no cost, no flakes.
- Local dev works without a key for everything except actual model quality.
- Tests can assert plumbing (history was loaded, SSE was framed correctly,
  ui_context persisted) without coupling to an opaque remote service.

Eval suites (E1–E7, Phase 8) are where we actually exercise the live model.

### Tracing is free if you instrument the LLM service

Langfuse decorators wrap `stream_chat` and the agent dispatcher. Every LLM
call lands in Langfuse with prompt, response, latency, tokens, and the
parent agent run. That single integration covers A18 (tracing), A19 (full
LLM detail), and the explainability angle of G6 — open the trace in
Langfuse and the answer's provenance is right there.

### Async or it didn't happen

Every I/O path is async: SQLAlchemy 2 async engine, asyncpg driver, async
OpenAI client, FastAPI handlers. No sync database sessions, no sync
requests calls, no `time.sleep` in production code. AC1 falls out of this.

The one exception is Alembic migrations, which use `psycopg` sync — that's
the standard pattern and Alembic itself isn't on the request path.

---

## Layer 2 — Subsystem walkthroughs

### 2.1 Identity and conversation

#### Tables

```
users
  id            uuid pk
  email         varchar(255) unique
  display_name  varchar(255)
  role          enum user_role  ('client' | 'advisor')
  created_at    timestamptz default now()

chat_sessions
  id            uuid pk
  user_id       uuid fk → users.id  (idx)
  title         varchar(255) null
  created_at    timestamptz default now()
  updated_at    timestamptz default now() on update

chat_messages
  id            uuid pk
  session_id    uuid fk → chat_sessions.id  (idx)
  role          enum message_role  ('user' | 'assistant' | 'system')
  content       text
  ui_context    jsonb null   -- AC4 — see Phase 2 notes
  created_at    timestamptz default now()
```

#### Why this shape

- **Separate `chat_sessions` from `chat_messages`** instead of one flat
  table keyed by user. We need cheap "list a user's recent conversations"
  for the session picker; we'd also rather not pay full-message cost on a
  conversation index.
- **`role` is an enum, not a free string.** Catches typos at write time;
  Alembic generates a proper SQL `enum` type so values are constrained at
  the DB level too.
- **No content-search column on messages.** We'll likely add one in Phase 8
  (admin querying historical conversations), but YAGNI for now.
- **`ui_context` is jsonb on the user message, not a separate table.** It's
  per-turn ephemeral data — the JSON the user saw on screen when they sent
  the message. Putting it next to the message it pertains to keeps the
  one-row-per-turn read pattern simple. AC4 + future drift analysis (E5)
  both want it adjacent.

#### Request flow — `POST /api/v1/chat`

```
client → POST /api/v1/chat {session_id, content, ui_context?}
         │
         ▼
   load ChatSession + User
   persist user ChatMessage (so disconnects don't lose input)
   load full session history (created_at ASC)
   build LLM messages: [system_prompt(role), *history]
         │
         ▼
   StreamingResponse:
     for token in llm.stream_chat(messages):
        yield f"data: {json.dumps({'delta': token})}\n\n"
     # after stream completes
     persist assistant ChatMessage with accumulated content
     yield f"data: {json.dumps({'done': True, 'message_id': str(asst.id)})}\n\n"
```

Three subtle decisions in there:

1. **Persist user message first**, then read history including it, then
   build the LLM prompt. If the client disconnects mid-stream we still have
   their input in the DB. Reload the page → they see their question (and
   no answer); they can retry.
2. **Read history from DB, not from the request body.** Source-of-truth
   discipline — the frontend's view is allowed to drift; the DB isn't.
3. **System prompt isn't persisted as a message.** It's regenerated per
   turn from `user.role`. If we change the prompt copy, every old
   conversation gets the new system tone immediately. (If that ever turns
   out to be wrong — e.g. for reproducibility of historical answers — we
   add `system_prompt_version` on the session.)

#### REPL parity

`scripts/repl_chat.py` does the same dance but writes directly via
`AsyncSessionLocal` instead of going through HTTP. Same `stream_chat`, same
history-replay invariant, same role-aware prompt. There is no separate
"REPL service" — it's a thin runner over the shared service layer.

---

### 2.2 Portfolio (Phase 2)

#### Tables

```
accounts
  id          uuid pk
  user_id     uuid fk → users.id  (idx)
  name        varchar(255)
  kind        enum account_kind  ('cash' | 'brokerage' | 'retirement' | 'crypto')
  created_at  timestamptz default now()

positions
  id            uuid pk
  account_id    uuid fk → accounts.id  (idx)
  symbol        varchar(16)
  quantity      numeric(20, 8)
  avg_cost      numeric(20, 8)
  asset_class   enum asset_class  ('equity' | 'bond' | 'cash' | 'crypto' | 'alt')
  currency      char(3) default 'USD'
  updated_at    timestamptz

prices
  symbol  varchar(16)
  ts      timestamptz
  price   numeric(20, 8)
  pk (symbol, ts), idx (symbol, ts desc)

goals
  id              uuid pk
  user_id         uuid fk → users.id  (idx)
  name            varchar(255)
  target_amount   numeric(20, 2)
  target_date     date
  current_amount  numeric(20, 2) default 0
  created_at      timestamptz
```

#### Why this shape

- **Two-level account → position** matches how every retail brokerage
  models the world. Keeps "show me the cash account" trivial and lets
  goals reference accounts later if we want sub-bucketing.
- **`prices` is a time-series**, not a column on `positions`. Lets us
  compute P/L from any point, draw historical charts, and serve the
  AC6 ticker from the same table the dashboard reads.
- **Composite PK on `prices(symbol, ts)`** — natural key, no surrogate.
  Index `(symbol, ts desc)` makes "latest price for symbol" an O(1)
  index seek.
- **`numeric` not `float`** for everything money. We'll do arithmetic on
  these and the rounding rules of `numeric(20,8)` are predictable.
- **Risk score is a service, not a column.** It's a function of current
  positions × current prices; storing it would be a stale denormalisation.
  AC5's `compute_risk_score(positions)` is a pure function, easy to test.

#### Request flow — `GET /api/v1/portfolio?user_id=…`

The endpoint composes:

1. SELECT accounts WHERE user_id;
2. For each account, SELECT positions;
3. For each position symbol, find the latest price via
   `(SELECT price FROM prices WHERE symbol = :s ORDER BY ts DESC LIMIT 1)`
   — done as a `LATERAL` join so it's one round-trip for the whole
   portfolio.
4. Compute `market_value`, `cost_basis`, `unrealized_pl`, `allocation`
   per asset class in Python from the joined rows.

That last step (compute in Python) is intentional. The arithmetic is
trivial; doing it in SQL with window functions would be more clever and
less readable, and for portfolios under ~10000 positions the network round
trip dominates anyway.

#### AC4 — UI-state-aware chat

The frontend dashboard ships a small JSON payload with chat sends made from
the dashboard:

```json
{
  "ui_context": {
    "page": "portfolio",
    "user_id": "...",
    "totals": {"market_value": 412345.67, "unrealized_pl_pct": 8.4},
    "top_positions": [
      {"symbol": "AAPL", "weight": 0.18},
      {"symbol": "VOO",  "weight": 0.32}
    ]
  }
}
```

The chat router persists it on the user `ChatMessage` row and appends it to
the system prompt as a `## Current UI State` block. The system prompt rule
is explicit: *only ground numerical claims in this JSON; do not invent
values.*

This gives us two things:

- Genuine "ask anything against the data on the UI" without re-querying the
  DB during chat.
- A drift signal for E5 — if the model's answers stop matching the
  ui_context distribution, we flag drift.

---

### 2.3 RAG corpus (Phase 3)

#### Tables

```
documents
  id            uuid pk
  source_uri    text
  title         text
  lang          char(2) default 'en'
  doc_type      varchar(64)        -- 'whitepaper' | 'regulatory' | 'internal' | ...
  ingested_at   timestamptz
  metadata_json jsonb

chunks
  id            uuid pk
  document_id   uuid fk → documents.id  (idx)
  ord           int                -- position within the document
  content       text
  token_count   int
  metadata_json jsonb              -- {"section": "Risk", "page": 3, ...}
  embedding     vector(1536)       -- pgvector — for R1 semantic search
  content_tsv   tsvector           -- Postgres FTS — for R6 keyword search
  GIN idx on content_tsv
  IVFFLAT idx on embedding (cosine) -- swap to HNSW once IVF starts hurting

media_assets       -- R4, multimodal RAG (Phase 5)
  id            uuid pk
  kind          enum  ('image' | 'audio')
  source_uri    text
  caption       text
  transcript    text
  embedding     vector(1536)       -- caption/transcript-derived
  metadata_json jsonb
  ingested_at   timestamptz
```

#### Why one table for two indexes

`chunks` carries both `embedding` (vector) and `content_tsv` (tsvector).
Hybrid search (R8) is then two queries against the same table, fused with
reciprocal-rank fusion in application code. This avoids:

- Maintaining two stores in sync (they can never drift if they're columns
  on the same row).
- A second backup story.
- A second ops surface.

The trade is index size: GIN on tsvector + IVF on the vector column are
both substantial. For a ≥1500-chunk corpus we're well within Postgres's
comfort zone. If we hit the S11 100-QPS target and pgvector becomes the
bottleneck, we'll move *only the embedding* to Qdrant and keep tsvector +
metadata in Postgres — see "Why-this-not-that" §3.2.

#### Ingestion pipeline (`scripts/ingest_corpus.py`)

```
for each source in corpus.yaml:
    raw_text = pypdf.extract(source) | trafilatura.extract(source)
    chunks   = recursive_chunker(raw_text, target=500, overlap=50)
    embeds   = openai.embeddings.create(text-embedding-3-small, chunks)
    upsert documents row
    bulk insert chunks with embedding
    update content_tsv via trigger
```

Idempotent: a `(document_id, ord)` unique constraint on chunks means
re-running the script doesn't dupe rows; instead it ON CONFLICT updates
the embedding (useful when we change the embedding model).

#### Hybrid search (R8)

```
def hybrid_search(query, k=20):
    sem = sql_semantic(query, k=k*2)        # cosine distance
    kw  = sql_keyword(query, k=k*2)         # ts_rank_cd
    return rrf_fuse(sem, kw, k=k, c=60)
```

`rrf_fuse` is the standard reciprocal-rank-fusion: each result's RRF score
is `sum(1 / (c + rank_in_list))` across both lists. `c=60` is the literature
default. Ship a top-k cross-encoder reranker (`bge-reranker-base`, runs
locally on CPU) on top for R10/R11 — A11 (local model) gets satisfied as
a side effect.

---

### 2.4 Agentic core (Phase 5)

#### Tables

```
agent_runs
  id                 uuid pk
  session_id         uuid fk → chat_sessions.id
  root_agent         varchar(64)
  status             enum  ('running' | 'done' | 'failed')
  started_at         timestamptz
  ended_at           timestamptz null
  langfuse_trace_id  text null

agent_steps
  id              uuid pk
  run_id          uuid fk → agent_runs.id
  parent_step_id  uuid fk → agent_steps.id  null   -- self-reference
  agent_name      varchar(64)
  tool_name       varchar(64) null
  input_json      jsonb
  output_json     jsonb null
  confidence      numeric(4, 3) null
  started_at      timestamptz
  ended_at        timestamptz null
```

#### Why a self-referencing tree

A4 in the spec — "agents dynamically spawn ≥ 3 non-trivial sub-agents" —
is naturally a tree. `parent_step_id` makes it one row per step plus one
recursive CTE to render the spawn tree. We don't need a tree library; we
need PostgreSQL.

A20 (show agent trajectory) and G6 (explainability) both render from the
same `agent_steps` rows — once they're in the DB and in Langfuse, the
artefacts are essentially free.

#### Orchestrator topology

```
              ┌────────────────────┐
              │  PlannerAgent       │   ← root, decides who answers
              └──┬───┬───┬───┬─────┘
                 │   │   │   │
       ┌─────────┘   │   │   └─────────────┐
       ▼             ▼   ▼                  ▼
 PortfolioAnalyst  DocsLibrarian  MarketResearcher  RiskAdvisor
 (reads positions  (RAG over       (web search       (calls AC5
  + prices,        corpus +        Tavily/Serp,     calculator,
  AC4 grounded)    citations)      A9 grounding)    cites guidelines)
```

Hand-off (A2) is implemented via tool-call routing: each expert exposes a
`call_<expert>(...)` tool to the planner, the planner picks one (or several
in parallel), the orchestrator dispatches.

A12 (cross-session memory) plugs in here: the planner agent's first step is
to retrieve the top-k `user_memories` for the active user (cosine over the
embedding column) and prepend them to its context. The summarizer agent
fires post-session to write new memories.

---

### 2.5 LLM service

`app/services/llm.py` exposes one async function:

```python
async def stream_chat(
    messages: list[dict],
    model: str | None = None,
) -> AsyncIterator[str]:
```

The full implementation is short on purpose. Two responsibilities:

1. **Routing.** No key → stub generator. Key set → `openai.AsyncOpenAI`.
2. **Token extraction.** Walks `chunk.choices[0].delta.content` for non-None
   strings. The caller never sees raw chunks.

Things this service deliberately does not do:

- Retries — caller decides; some endpoints want fail-fast.
- Token counting — Langfuse handles it post hoc.
- Caching — that's S2's job, lives in Redis with a hash key on the
  `messages` list.
- Tool/function calling — that's the agent layer's job; the LLM service
  stays text-only and the agents own the tool-call loop.

This boundary is what makes "swap models" and "wrap with tracing" trivial:
you decorate or replace one function.

---

## Layer 3 — Why-this-not-that

### 3.1 Why FastAPI not Litestar / Sanic / Starlette directly?

FastAPI's pydantic v2 integration writes our request/response validators for
us, OpenAPI docs come for free, and Depends() is the cleanest DI pattern in
Python. Litestar is faster on benchmarks but the ecosystem (testcontainers,
Langfuse decorators, examples) is FastAPI-shaped. Starlette directly would
make us hand-roll serialisation. Sanic has weaker async-DB integration. The
~5% performance delta isn't worth the ergonomic loss for a demo this size.

### 3.2 Why pgvector and not Pinecone / Weaviate / Qdrant?

For ≤ 1M vectors and ≤ 100 QPS, pgvector with HNSW is in the green zone.
We get one DB to operate, one backup, no extra ops surface. The single
biggest gotcha is index build time — IVFFlat builds fast but recall drops
at scale; HNSW builds slow but recalls well; we'll start IVF and switch.

We split off a vector store *only* when:

- p95 latency on `chunks <-> :query` exceeds 500ms at our target QPS, or
- Index size exceeds Postgres shared_buffers comfort.

For S11 (100 QPS), we'll bench pgvector first. If it falls over, Qdrant in
docker-compose; the embedding column moves to Qdrant; tsvector + metadata
stays in Postgres; the application-side hybrid fuser doesn't change.

### 3.3 Why SSE not WebSockets?

SSE works over HTTP/1.1, survives every proxy, has automatic reconnection
in the browser, and is one-way (server → client) which is exactly what
chat-token streaming and price ticks need. WebSockets are bidirectional
and that's strictly more capability than we use. Adding bidirectional later
would mean a new endpoint, not a rewrite of the streaming layer.

### 3.4 Why Postgres enums and not lookup tables?

Enums catch typos at insert time and let us read code without joining. The
classic argument against — "enums require a migration to add a value" — is
*right* for product-level taxonomies (e.g. categories users edit) and
*wrong* for engineering-level constraints (`role`, `kind`, `status`). For
our cases the values are part of the API contract.

### 3.5 Why a stub LLM and not VCR / cassettes?

Cassettes replay real responses byte-for-byte. They're great for testing
prompt → response correctness. But for our test purposes — was history
loaded? Did SSE frame correctly? Did ui_context persist? — the *content*
of the model's answer is irrelevant. The stub keeps tests deterministic
without the cassette tax (re-record when prompts change, secret-scrub
recordings, manage cassette files).

For the eval suites (E1–E7) we *do* call the live model, but those run on
demand, not in CI.

### 3.6 Why one Postgres for Langfuse and one for the app?

Langfuse's data model and ours have nothing to do with each other; coupling
them creates a backup-shape they'd both pay for. The Langfuse Postgres is
spun up by docker-compose and gets its own volume; if we ever delete the
Langfuse stack we don't risk our chat history.

### 3.7 Why role-aware system prompt and not separate /chat/client + /chat/advisor?

The conversation model is identical across roles; only tone and tool
permissions vary. Two endpoints would force `if route == client/`
branching in every middleware (auth, rate limiting, tracing). One endpoint
+ branching at prompt-build time keeps the surface area small and the
plumbing single-purpose.

If advisors ever need fundamentally different conversation semantics —
e.g. multi-client context, batch operations — *that's* when a second
endpoint pays for itself. Not before.

### 3.8 Why TDD on the backend but smoke tests on UI components?

Backend logic (auth, persistence, history replay, LLM routing, agent
orchestration) is where bugs are *expensive* and where the answer to "did
it work?" is unambiguous. TDD pays.

UI components — visual smoke tests + integration tests on the state hook —
catch the bugs that matter at this layer (typed wrong handler, broke a
prop). Pixel-level component testing for shadcn-shaped UIs has poor
ROI: the heavy lifting is shadcn's, the dev's job is composition.

### 3.9 Why isn't there a real auth system?

This is a demo, not a product. The role switcher in localStorage *is* the
auth model — every spec item that says "different user" is satisfied by
distinct seeded emails on the backend. Rolling auth (OAuth, magic link,
session cookies) would consume a day and demonstrate nothing the spec
asks for.

If a real demo audience asked, the wire-up is small: add a `/login`
endpoint that returns a session cookie, swap localStorage for the cookie
in the API client, add `Depends(current_user)` on every router. The schema
already has `users`; nothing else changes.

### 3.10 Why pre-emptive Phase planning and not "build feature by feature"?

The spec is large enough that without a roadmap we'd thrash on what to
build next. Phasing forces every sub-spec to commit to *one* plan with
*one* set of acceptance criteria, and forces us to think about what each
phase enables for the next.

Concretely: Phase 3 (RAG corpus) gates Phase 5 (agents that cite docs);
Phase 2 (portfolio + AC4) gates the most demoable AC4 moment in Phase 5.
Without that ordering the demo wouldn't tell a coherent story.

---

## Appendix A — File map (current, Phase 1 + parts of Phase 2)

```
backend/
├── alembic/
│   ├── env.py                 — wires Settings into the migration runner
│   └── versions/
│       └── cc68bfd…           — initial users + chat tables
├── app/
│   ├── core/
│   │   ├── config.py          — typed Settings (env + .env)
│   │   └── deps.py            — get_session() request-scoped DB session
│   ├── db/
│   │   ├── base.py            — DeclarativeBase
│   │   ├── session.py         — async engine + AsyncSessionLocal
│   │   └── models/
│   │       ├── user.py
│   │       ├── chat_session.py
│   │       └── chat_message.py
│   ├── routers/
│   │   ├── health.py          — /api/v1/health
│   │   └── chat.py            — users + sessions + messages + SSE chat
│   ├── schemas/
│   │   └── chat.py            — pydantic request/response models
│   ├── services/
│   │   └── llm.py             — async stream_chat with stub fallback
│   └── main.py                — FastAPI app + CORS + router mount
├── scripts/
│   ├── repl_chat.py           — C1 REPL client
│   └── seed_demo.py           — Phase 2 demo data (when added)
└── tests/
    ├── unit/                  — pure-Python tests (config, models, llm stub)
    └── integration/           — httpx + Postgres (chat API, REPL smoke)

frontend/
└── src/
    ├── lib/
    │   ├── api.ts             — base URL helpers
    │   ├── chat-api.ts        — typed REST + SSE client
    │   └── utils.ts           — cn() + small helpers
    ├── features/
    │   └── chat/
    │       ├── useChat.ts         — state hook (user, session, messages, send)
    │       ├── ChatPanel.tsx      — top-level chat surface
    │       ├── RoleSwitcher.tsx
    │       ├── MessageList.tsx
    │       ├── Composer.tsx
    │       └── __tests__/         — vitest + RTL
    ├── components/ui/             — shadcn primitives (button, card, …)
    └── App.tsx
```

## Appendix B — Glossary of unobvious choices

- **`onupdate=func.now()`** on `chat_sessions.updated_at` — server-side, not
  Python-side. Survives any backdoor write that bypasses the ORM.
- **`uuid.uuid4` Python-side** for ids — we want the id available before
  flush so we can use it in response payloads without a round-trip.
- **`expire_on_commit=False`** on the session factory — without it,
  accessing attributes after commit triggers a re-fetch and breaks
  `await session.refresh(obj)` patterns.
- **`autoflush=False`** — explicit `flush()` is clearer when we have it,
  and prevents accidental partial writes during SELECTs.
- **`asyncpg` for app, `psycopg` for Alembic** — Alembic's lifecycle is
  sync; trying to coax it into async is more pain than `psycopg[binary]`
  in dev deps.
- **`httpx.ASGITransport`** in tests — runs FastAPI in-process without
  binding a real port. Makes `pytest -p no:cacheprovider -q` reliably
  fast.
- **`TRUNCATE … CASCADE`** between tests, not transactional rollback —
  the chat router commits its own transactions for the user message,
  so a per-test outer transaction doesn't roll those back.
