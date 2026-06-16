# AuraWealth — Interviewer Demo Script

> **Audience:** Technical interviewer, ~30 minutes total. Allow 10–12 minutes for the live demo, the rest for questions.
> **Goal:** Show that the system works end-to-end across two personas, that the design choices are deliberate, and that the architecture extends to every spec category.

---

## 0. Pre-flight (do once before the interview starts)

```bash
# From repo root
docker compose up -d db redis langfuse

# Apply migrations and seed demo data
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_demo

# Start the backend
.venv/bin/uvicorn app.main:app --reload --port 8000 &

# Start the frontend
cd ../frontend
npm run dev &
```

Open three things in advance:

1. **Browser tab A** — http://localhost:5173 (the app itself, on the Client view)
2. **Browser tab B** — http://localhost:3000 (Langfuse, signed in)
3. **A terminal** — sized big, prompt cleared, `cd backend` already done

Have a second monitor or split-screen ready: you'll need the system-design diagram visible while you talk.

---

## 1. Open with the system-design diagram (90 seconds)

> "Before I run anything I want to show you the shape of the system."

Pull up `docs/implementation-plan.md` §2 (or the diagram below in this doc) and walk through it left to right.

```
┌────────────────────────────┐    SSE / REST     ┌──────────────────────────────┐
│  Vite + React 19 + shadcn  │ ◀──────────────▶ │  FastAPI (async)             │
│  - Chat panel              │                   │  - Routers                   │
│  - Role switcher           │                   │  - Agent orchestrator        │
│  - Upload (img/audio)      │                   │  - LLM service (OpenAI)      │
│  - Portfolio view          │                   │  - Tool registry / MCP       │
│  - Trace viewer            │                   │  - Streaming endpoints       │
└────────────────────────────┘                   └──────┬────────────┬──────────┘
                                                        │            │
                                            ┌───────────▼─┐    ┌─────▼──────────┐
                                            │ Postgres 16 │    │ Redis 7        │
                                            │  + pgvector │    │  cache + queue │
                                            └─────────────┘    └────────────────┘
                                                  ▲
                                            ┌─────┴────────┐
                                            │  Langfuse    │  ← every LLM call
                                            └──────────────┘
```

**Talking points (one sentence each):**

- "FastAPI is async end-to-end — that gives me AC1 (event-driven backend) for free, and lets me stream tokens to the browser over SSE without a websocket layer."
- "Postgres with the pgvector extension is doing four jobs: relational app data, semantic search, keyword search, and FTS. One database, one backup story. I only split off a vector DB if the 100-QPS S11 target forces it."
- "Redis is the response cache for S2 and the task queue for S8 long-running jobs like ingestion."
- "Langfuse self-hosted captures every LLM call — so A18, A19, and the explainability angle of G6 all come from the same instrumentation."

---

## 2. Show the live app — Client persona (3 minutes)

> "This is what an end investor sees. The persona is 'Financial GPS'."

**Click "New chat"** to make sure you start clean.

**Say:** "I'll ask it something simple first to show streaming and persistence."

**Type:**

```
Hi, my name is Sam. I just opened a Roth IRA. What's a sensible first thing to invest in?
```

— wait for the stream to finish.

**Then type a follow-up:**

```
What did I just tell you my name was?
```

**Talking points while it streams:**

- "Notice the tokens streaming in real time — that's a server-sent-events endpoint emitting `data: {delta: …}` frames. The browser parses them on the fly using the Fetch streaming API; no library."
- "When the second turn answers 'Sam', that's AC2 in action — every turn replays the full ordered message history from Postgres, prepended with a role-aware system prompt. Persist user message first so a mid-stream disconnect doesn't lose the input."

**Click "New chat"** in the left rail.

> "I can have multiple parallel conversations — useful for the demo, and the data model already supports it. Sessions belong to users; messages belong to sessions."

---

## 3. Show the same app — Advisor persona (2 minutes)

**Click the role switcher → "Advisor"** in the header.

**Talking points while it transitions:**

- "Same backend, same chat surface — but the system prompt is different. The advisor sees a 'Command Center' framing: surfacing clients who need attention, summarising risk."
- "Histories are completely separate, keyed on user. The localStorage cache only remembers your preferred role — the source of truth is always the server."

**Type:**

```
Give me a one-paragraph summary of Sam's portfolio risk.
```

— show it answering with reference to the seeded data.

**Optional** if Phase 2 is in: open `/portfolio` view briefly, point at the risk score widget.

> "AC4 — 'ask anything against the data on the UI' — works because when the chat composer is rendered on a data page, it ships the relevant UI state JSON along with the prompt. The model is told to ground numerical claims in that JSON only."

---

## 4. Show the REPL alternate (90 seconds)

Switch to the terminal.

```
.venv/bin/python -m scripts.repl_chat --email demo-client@aura.test --role client
```

Type:

```
> What's the difference between a Roth IRA and a 401(k)?
```

…then `/exit`.

**Talking points:**

- "Same backend service, different client. The REPL talks to the DB directly via the same async session factory and uses the same `stream_chat` service. That's spec item C1 — REPL chat off an LLM."
- "Both the REPL and the web client fall back to a deterministic stub if `OPENAI_API_KEY` is empty, which is what makes the test suite hermetic. 31 backend tests run offline in under 4 seconds."

---

## 5. Open Langfuse and click into a trace (90 seconds)

Switch to the Langfuse browser tab.

**Talking points:**

- "Every LLM call I just made is here, end-to-end. A18 trace and monitoring + A19 in-depth trace per call are both this single integration."
- "Click into a chat run — you can see the prompt, the response, the latency, the token counts, and how the system prompt assembled the role + history."
- "When agents come online in Phase 5, the same trace will fan out into nested spans — one per sub-agent — and that becomes G6 explainability and A20 trajectory rendering."

---

## 6. Walk through the data model (90 seconds)

Open `docs/architecture-walkthrough.md` in the editor.

**Pick three tables to discuss:**

- `users` + `chat_sessions` + `chat_messages` — explain the cardinality, why I persist user-first, why message order is `created_at ASC`.
- `documents` + `chunks` — explain that the same row carries both a `vector(1536)` for semantic search and a `tsvector` for keyword. Hybrid search (R8) is RRF fusion of two queries against the same table — no second store needed for the demo.
- `agent_runs` + `agent_steps` — explain that the parent_step_id self-reference makes A4 dynamic sub-agent spawn trees a single recursive query.

---

## 7. Show the test suite running (60 seconds)

```
cd backend && OPENAI_API_KEY="" .venv/bin/pytest -q
cd ../frontend && npm test -- --run
```

**Talking points:**

- "Backend tests run with the OpenAI key blanked — that forces the stub LLM, so CI never depends on a remote service or burns budget."
- "Multi-turn replay (`test_chat_multi_turn_replays_full_history`) and per-user isolation (`test_two_users_have_separate_histories`) are explicit assertions, not incidental — they're the AC2/AC3 acceptance criteria from the spec."

---

## 8. Discuss what's next (60 seconds — only if asked)

> "The phasing is: portfolio + AC4/AC5/AC6 next; then the RAG corpus — that's the gating feature for everything in §2.4 of the spec; then multimodal vision/audio with committed fixtures; then the agentic core with four expert agents and a hierarchical orchestrator; then performance baselines and scaling; finally evaluation and governance. Each phase is its own bite-sized plan in `docs/superpowers/plans/`."

---

## 9. Closing

> "If you want to see the design rationale in writing — every model field, every endpoint, every why-this-not-that — `docs/architecture-walkthrough.md` covers it. If you want the strategic roadmap, `docs/implementation-plan.md`. If you want the source spec annotated with build/demo cost rankings, `docs/features-spec.md`."

---

## Q&A — likely questions and one-line answers

**Q: Why pgvector and not Pinecone/Weaviate/Qdrant?**
A: One database to operate, one backup. R1 + R6 + R8 fit on the same row (`vector` + `tsvector`). Switch to Qdrant only if S11's 100 QPS target fails on pgvector — decision deferred to after the S6 baseline.

**Q: How do you handle conversation memory across sessions (A12)?**
A: Phase 5. New table `user_memories` (id, user_id, kind, content, embedding, source_session_id). On session end a summarizer agent writes facts/preferences as embeddings; on new sessions for the same user, top-k by similarity is prepended to the system prompt. Schema's already in `docs/implementation-plan.md` §3.

**Q: Why offline stub LLM in tests?**
A: Two reasons. Hermetic CI — no key, no flakes, no cost. And it forces the test assertions to focus on plumbing (was the right history loaded? did both messages persist? did SSE frames format correctly?) rather than on semantic answer quality, which is what evals (E1–E7) cover later.

**Q: How would you scale this to 100 QPS on vector search (S11)?**
A: Three levers in order: (1) HNSW index on `chunks.embedding` with `m=16, ef_construction=64`, currently default IVFFlat; (2) read-replica Postgres with pgbouncer in front; (3) move corpus to Qdrant if the read-replica path can't sustain p95 < 500ms. The proof artifact is the locust script in `scripts/bench_vector.py` (Phase 7).

**Q: How does the advisor approve a rebalance? (G3 / G4)**
A: Phase 6. `approvals` table — request lands as `status=pending`; advisor UI shows pending list; approve/reject triggers the action workflow; rejection routes to a "why did you reject?" capture and feeds back into the agent's failure-mode dataset (E5 drift). Designed but not built yet.

**Q: Where does the agent identity (G7) come from?**
A: Each registered agent has a name, a capability list, and a signed identity (HMAC of `name|capabilities|version` with a server secret). The orchestrator only routes to agents whose signature verifies. Phase 8.
