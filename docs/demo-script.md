# AuraWealth — Interviewer Demo Script

> **Audience:** Technical interviewer, ~30 minutes total. ~12 minutes live demo, the rest is Q&A.
> **Goal:** Show end-to-end working software across two personas, demonstrate the deliberate architecture, and prove every major spec category is wired up — even where features are minimal.

---

## 0. Pre-flight (do once before the interview)

```bash
# From repo root
docker compose up -d db redis langfuse

# Migrate + seed
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_demo
.venv/bin/python -m scripts.ingest_corpus   # populates RAG corpus

# Start backend
.venv/bin/uvicorn app.main:app --reload --port 8000 &

# Start frontend
cd ../frontend
npm run dev &
```

Open three things in advance:

1. **Browser tab A** — http://localhost:5173 (the app, on Client view)
2. **Browser tab B** — http://localhost:3000 (Langfuse, signed in)
3. **Terminal** — sized large, `cd backend` already done

Have the system-design diagram (`docs/implementation-plan.md` §2 or `docs/architecture-walkthrough.md` Layer 2) on a second screen.

---

## 1. Open with the system-design diagram (90 s)

> "Before I run anything, I want to show you the shape of the system."

```
┌────────────────────────────┐    SSE / REST     ┌──────────────────────────────┐
│  Vite + React 19 + shadcn  │ ◀──────────────▶ │  FastAPI (async)             │
│  - Chat panel              │                   │  - /chat (3-agent pipeline)  │
│  - Portfolio dashboard     │                   │  - /portfolio /risk /goals   │
│  - Image upload            │                   │  - /rag/{semantic,kw,hybrid} │
│  - Sessions sidebar        │                   │  - /uploads/{image,describe} │
└────────────────────────────┘                   │  - /prices/stream (SSE)      │
                                                  └──┬──────────────┬───────────┘
                                                     │              │
                                          ┌──────────▼─┐    ┌───────▼─────────┐
                                          │ Postgres + │    │ Redis 7         │
                                          │  pgvector  │    │ cache + queue   │
                                          │  - users   │    └─────────────────┘
                                          │  - chat_*  │
                                          │  - portfolio
                                          │  - chunks  │ ← vector + tsvector
                                          └────────────┘
                                                ▲
                                         ┌──────┴──────┐
                                         │  Langfuse   │ ← every LLM call
                                         └─────────────┘
```

**Talking points:**

- "**FastAPI async end-to-end** gives me AC1 (event-driven backend) for free, and SSE streaming without a websocket layer."
- "**Postgres with pgvector** is doing four jobs: relational data, semantic search (R1), keyword search via FTS (R6), and hybrid (R8). One DB, one backup, one ops surface."
- "**Redis** is response cache (S2) and task queue (S8)."
- "**Two pipelines, one orchestrator.** Clients hit a topic-extracting Researcher and a UI-snapshot-grounded Analyst. Advisors hit a *task-classifying* Researcher (`client-triage` / `risk-review` / `rebalancing` / …) and a *tool-calling* Analyst that hits real DB tools — `list_clients`, `get_client_portfolio`, `get_client_risk`. Spec items A1 (specialised agents), A2 (handoff), AC5 (advisor risk against the real book)."
- "**Langfuse** captures every LLM call — A18 + A19 + the explainability angle of G6 from one integration. `stream_chat` is wrapped at module load, so the chat router, REPL, and tool-calling all instrument transparently."

---

## 2. Show the live app — Client persona (3 min)

> "This is what an end investor sees. Persona is 'Financial GPS'."

**Click "New chat"** in the left rail to start clean.

**Type:**

```
Hi, my name is Sam. I just opened a Roth IRA. What should I invest in first?
```

**While it's streaming, narrate:**

- "Notice the **'Show reasoning'** disclosure under the answer — that's our 3-agent pipeline. Researcher decomposes the question into sub-topics. Analyst grounds each topic against context (UI snapshot for clients, DB tools for advisors). Writer composes the final user-facing answer. **The user never has to opt in — agentic IS the default chat.**"
- "That covers spec items C3 (sequential 3-agent workflow) and the front edge of G6 (explainability) with one design."

**After the answer streams in, click "Show reasoning"** to expand:

- Researcher: list of topics ("risk tolerance", "expense ratios", "diversification")
- Analyst: structured findings with confidence pills
- Writer: "Wrote final answer"

**Now type a follow-up:**

```
What did I just tell you my name was?
```

> "It says 'Sam' — that's AC2. Every turn replays the full ordered message history from Postgres, prepended with a role-aware system prompt. The user message is persisted **before** the LLM call, so a mid-stream disconnect never loses input."

**Click "New chat"** to demonstrate the session isolation:

> "Multiple parallel conversations per user. Sessions belong to users; messages belong to sessions. Per-session memory is full-replay; cross-session memory (A12) plugs in at the planner stage in Phase 5 — schema's already in `docs/architecture-walkthrough.md` §2.4."

---

## 3. Switch to Advisor — show portfolio + grounded chat (3 min)

**Click role switcher → "Advisor"**.

> "Same orchestrator, **different pipeline**. The Researcher swaps from a topic extractor to a task classifier — it has to decide: `client-triage` / `risk-review` / `portfolio-review` / `rebalancing` / `market-summary` / `compliance` / `general`. The Analyst swaps from a UI-snapshot reader to a **tool-using agent** with `list_clients`, `get_client_portfolio`, `get_client_risk`, and `rag_search` exposed. Histories are completely separate, keyed on user. The localStorage cache only remembers the preferred role — the server is the source of truth."

**Navigate to `/portfolio`** (header link).

Show:
- Live ticker strip (AAPL/MSFT/NVDA/VOO/BND, AC6)
- Top KPIs: total market value, P/L with live-since-open delta, risk score (AC5) with drivers
- Asset allocation donut, goals progress bars
- Accounts table with all positions

> "AC5 — risk is a **deterministic function** of positions × asset-class weights. Pure function, easy to test, not a stale denormalisation."

**Click the floating chat button (bottom-right) to open the chat drawer over the dashboard.**

**Type:**

```
What's my biggest exposure and which holding is dragging it down?
```

> "Here's AC4 — 'ask anything against the data on the UI'. There's a small `UiContextProvider` at the app root; the dashboard publishes its snapshot via `usePublishUiContext({totals, allocation, top_positions})`, and `useChat` reads the live snapshot inside its `send` callback and ships it as `ui_context` in the `/chat` body. The system prompt prepends it as a `## Current UI State` block and tells the model to ground numerical claims in that JSON only — no inventing values."

**Pull up the network tab briefly** to show the `ui_context` payload in the POST body.

> "Notice the snapshot updates whenever the portfolio refreshes — the live ticker doesn't push it on every tick (would be noisy), but reload the page or open a new chat and the freshest values are there."

---

## 3.5. Advisor agent + tools demo (90 s)

**Stay on Advisor. Open a fresh chat.** Type:

```
Summarise my book by risk level — which clients are most aggressive?
```

**While it streams, click "Show reasoning"** and narrate:

- "Researcher classified this as `task: risk-review` — that's the advisor task type, not a topic list."
- "Analyst called `list_clients()` first — see the trace event. That returned the real book from Postgres. Then per-client `get_client_risk(client_id)` calls — one per client."
- "Writer rendered the markdown table — every name, every score, every label is **straight from a tool call**. Try the same question on a stale build and you'd see invented names like 'Leo' and made-up scores. With the grounding rule + tool-calling Analyst, the answer is reproducible against the DB."

> "Spec lift in this one minute: A1 partial (specialised agents per role — `MarketAnalyst` is the missing 4th expert), A2 (Researcher → Analyst handoff with tool dispatch), AC5 (advisor risk against the real book), G1 (grounding rule baked into all three agent prompts)."

**Optional:** open `services/agents/tools.py` quickly and point at `ADVISOR_TOOL_SCHEMAS` + `TOOL_DISPATCH` — show that tools are normal async Python functions wrapping the same SQL the REST routes use. *"That's also why MCP (A13) is a 1-day add: the tool functions are already there; MCP is just a different transport over the same `TOOL_DISPATCH` map."*

---

## 4. RAG corpus — semantic + keyword + hybrid (90 s)

**Switch to terminal:**

```bash
curl -s -X POST http://localhost:8000/api/v1/rag/hybrid \
  -H 'Content-Type: application/json' \
  -d '{"query": "should I rebalance after a market drop?"}' | jq
```

Show 3-4 results with `title`, snippet, and a `score`.

> "**One row per chunk, two indexes**: `vector(1536)` for semantic (R1) and `tsvector` for keyword (R6). Hybrid (R8) is reciprocal-rank fusion across both queries against the same table — no second store. Saves a backup, saves an ops surface."

**Then narrate the limitation:**

> "Time-boxed: corpus is 6 hand-authored markdown docs ≈ 250 chunks, plus 2 multilingual stubs. Spec gates R1/R6 at ≥1000 chunks across >10 docs. Path to scale is in `docs/implementation-plan.md` §4.3 — 12 real PDFs (Vanguard, SEC, BlackRock, MAS, BaFin) via the `pypdf` + `trafilatura` + `text-embedding-3-small` ingestion pipeline. Doc list and embedding strategy already drafted."

---

## 5. Image upload — V1 / V2 / V4 (90 s)

**On the app, navigate to `/uploads`.**

Drag in `assets/fixtures/images/portfolio-snippet.png` (the seeded fixture).

Show: thumbnail appears, id badge.

**Type into the question box:**

```
Recreate this table as JSON.
```

Click "Describe these".

> "V1 single image, V2 multiple per turn — `gpt-4o` accepts the image as a base64 part directly; one call returns structured JSON. SV1 (40-cell table extraction) is the same call with a stricter schema."

**Try uploading an unsupported file** (drag in a `.txt` or `.psd`):

> "V4 — graceful unsupported-type handling. The MIME guard rejects with a 415 and a workaround hint."

---

## 6. Show the REPL alternate (60 s)

```bash
cd backend && .venv/bin/python -m scripts.repl_chat --email demo-client@aura.test --role client
```

Type:

```
> What's the difference between a Roth IRA and a 401(k)?
```

Then `/exit`.

> "Same backend service, different client. The REPL writes directly via `AsyncSessionLocal` and calls the same agent pipeline. C1 — REPL chat off an LLM."
> "Both clients fall back to a deterministic stub when `OPENAI_API_KEY` is empty. That's why the test suite runs offline — 60+ backend tests, no keys, no flakes, no cost."

---

## 7. Open Langfuse and click into a trace (60 s)

Switch to Langfuse browser tab.

> "Every LLM call is here, end-to-end. Each `stream_chat` call lands as a `generation` observation with the full prompt, the assembled response, latency, tokens. A18 + A19 + the explainability angle of G6 from one integration."
> "The wrap is in `app/services/llm.py` — `stream_chat` is replaced at module load with a Langfuse-wrapped async generator. It captures input messages, the resolved model, and the streamed output as it accumulates. When the Phase-5 planner lands, the Researcher / Analyst / Writer calls nest as child spans automatically — same trace shape, more nodes."

**Pre-demo setup (one-time):**

1. Open http://localhost:3000 → sign up → create a project.
2. Settings → API Keys → copy public + secret keys.
3. Paste into `backend/.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-…
   LANGFUSE_SECRET_KEY=sk-lf-…
   LANGFUSE_HOST=http://localhost:3000
   ```
4. Restart `uvicorn`. Send a chat message in the app. The trace appears in Langfuse within ~5 s.

If keys aren't set, the wrap is a transparent no-op — app behaviour is identical.

---

## 8. Live prices ticker (30 s — optional, only if time)

Point at the price ticker strip on the dashboard.

> "AC6 — simulated streaming prices. Deterministic random walk seeded by `(symbol, ts // 1s)` so two clients see identical numbers — good for screen sharing. Persists every 4th tick to the `prices` table so historical charts have data."

---

## 9. Show the test suite running (60 s)

```bash
cd backend && OPENAI_API_KEY="" .venv/bin/pytest -q
cd ../frontend && npm test -- --run
```

> "Backend tests with the OpenAI key blanked — forces the stub LLM. CI never depends on a remote service."
> "Multi-turn replay (`test_chat_multi_turn_replays_full_history`) and per-user isolation (`test_two_users_have_separate_histories`) are explicit assertions, not incidental — they're AC2/AC3 acceptance straight from the spec."

---

## 10. What's next — only if asked (60 s)

> "Phasing: portfolio + AC4–AC6 ✅, agentic-as-default + RAG-min + vision-min ✅, **role-split pipeline + advisor tools (A1 partial, A2, AC5) ✅**. Next is to scale the RAG corpus from 8 docs to 12 to clear the gating, add a 4th named expert (`MarketAnalyst`) + a planner above them (finishing A1, adding A3), wire MCP for the Postgres tool calls (A13 — the underlying tool functions are already in `services/agents/tools.py`), add the eval harness (E1–E3, E6), and run the S6 baseline + cache (S2). Each phase is its own bite-sized plan in `docs/superpowers/plans/`."

---

## 11. Closing

> "Three docs to dig deeper:
> - `docs/architecture-walkthrough.md` — every model field, every endpoint, every why-this-not-that decision
> - `docs/implementation-plan.md` — strategic roadmap and the master data model
> - `docs/features-spec.md` — the source brief annotated with build/demo cost"

---

## Q&A — likely questions, one-line answers

**Q: Why is agentic the default rather than a toggle?**
A: Users shouldn't pick "use the smart mode" — there's no dumb mode. Toggle UX is also impossible to scale: in Phase 5 we add a planner above the three agents and four expert sub-agents below; that can't be a feature flag, it's just chat. The trace is exposed as a "Show reasoning" disclosure on each bubble — explainability without UX cost.

**Q: Why pgvector and not Pinecone/Weaviate/Qdrant?**
A: One DB, one backup. R1+R6+R8 fit on the same row. We swap to Qdrant only if S11's 100 QPS target fails on pgvector — decision deferred to after the S6 baseline. The application-side hybrid fuser doesn't change either way.

**Q: How do you handle conversation memory across sessions (A12)?**
A: Phase 5. New table `user_memories` (id, user_id, kind, content, embedding, source_session_id). Summarizer agent fires post-session; planner retrieves top-k by similarity on session start. Schema's already in the architecture walkthrough.

**Q: Why offline stub LLM in tests?**
A: Hermetic CI — no key, no flakes, no cost. Tests assert plumbing (history loaded, SSE framed, ui_context persisted, agent stages emit in order); they don't assert semantic answer quality. Quality is what the eval suites (E1–E7) cover, on demand, against the live model.

**Q: How would you scale to 100 QPS on vector search (S11)?**
A: Three levers: (1) HNSW index instead of IVFFlat; (2) read-replica with pgbouncer; (3) move embeddings to Qdrant if Postgres can't sustain p95 < 500ms. Proof artifact is `scripts/bench_vector.py` (Phase 7).

**Q: How does the advisor approve a rebalance? (G3 / G4)**
A: Phase 6. `approvals` table — pending requests appear in advisor UI; approve triggers the action workflow; reject feeds back into the agent's failure-mode dataset (E5 drift signal).

**Q: How are agents identified (G7)?**
A: Each registered agent has a name + capability list + signed identity (HMAC of `name|caps|version`). Orchestrator only routes to agents whose signature verifies. Phase 8.

**Q: Why hand-authored markdown for the RAG corpus instead of real PDFs?**
A: Time-box. Real PDFs (Vanguard, SEC, BlackRock, MAS, BaFin — 12 docs, ≥1500 chunks) are listed in `implementation-plan.md` §4.3 with the ingestion pipeline (`pypdf` / `trafilatura` / `text-embedding-3-small`). The endpoints, the schema, and the hybrid-fusion math don't change with corpus size — scaling up is a script run.

**Q: Why is image upload on its own page rather than in chat?**
A: Phase 1 had to ship a working chat first. Phase 4 will fold the dropzone into the chat composer (drag image into composer → it goes up with the next message). The endpoint and the agent tool that consumes the result are already there; only the UI placement is pending.

**Q: What part of the spec are you most worried about?**
A: S11 (100 QPS vector DB) and Vo5 (live voice round-trip < 2s). Both are XL-build / fragile-demo. I'd run S11 against pgvector first; if it fails, switch to Qdrant in docker-compose. I'd defer Vo5 unless time permits — a recorded voice round-trip (Vo4) is already +2 points and far easier to demo without latency surprises.
