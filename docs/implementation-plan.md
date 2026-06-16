# AuraWealth — Master Implementation Plan

> **Source spec:** `docs/features-spec.md` (5-page brief, Tier A/B/C/D rankings).
> **Status doc:** strategic roadmap. Per-phase task plans live in
> `docs/superpowers/plans/YYYY-MM-DD-<phase>.md` and are the file an executing
> agent reads.

---

## 1. Goal

Ship a demoable wealth-management AI app that scores as many spec points as
possible per build hour. We optimise for **Tier A first, then B**, treating
Tier C as a stretch and Tier D as deferred.

The demo has two personas:

- **Client** — end investor, "Financial GPS" experience.
- **Advisor** — admin, "Command Center" over a book of clients.

Both share the same backend; role determines system prompts, UI surface, and
which agents are available.

---

## 2. Architecture

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
                                            │  - users    │    │  - LLM cache   │
                                            │  - sessions │    │  - RQ/arq jobs │
                                            │  - messages │    │  - rate limits │
                                            │  - portfolio│    └────────────────┘
                                            │  - corpus   │
                                            │  - embeds   │
                                            └─────────────┘
                                                  ▲
                                            ┌─────┴────────┐
                                            │  Langfuse    │
                                            │  (own pg)    │ ← every LLM call
                                            └──────────────┘
```

### Why these choices

- **FastAPI async** — gives AC1 (event-driven backend) for free, plus native
  SSE streaming for AC6 and chat.
- **Postgres + pgvector single instance** — covers R1 (semantic search), R6
  (keyword search via Postgres FTS), R8 (hybrid), and the relational app data
  in one DB. No second vector store needed until S11 (100 QPS) forces it.
- **Redis** — S2 cache, S8 message queue, rate limiting (G2 exfiltration
  guard hook).
- **Langfuse self-hosted** — A18 + A19 + G6 explainability, free.
- **Vite + shadcn** — already scaffolded; matches the spec's "demo-friendly"
  bias.

### Concurrency model

- Chat requests are SSE-streamed.
- Long-running tasks (corpus ingestion, eval runs, image OCR pipelines) go
  through an **arq** Redis queue (S8). Agent runs that exceed ~10 s push to
  the queue and the UI subscribes via SSE for progress.

---

## 3. Data Model

All UUID PKs, all timestamps `timestamptz`. Enum columns are SQL enums (named
explicitly so Alembic generates clean migrations).

### Identity & conversation

```
users
  id pk, email unique, display_name, role (client|advisor), created_at

chat_sessions
  id pk, user_id fk, title, created_at, updated_at

chat_messages
  id pk, session_id fk (idx), role (user|assistant|system|tool),
  content text, tool_call_json jsonb null, attachments_json jsonb null,
  created_at

# Cross-session memory (A12)
user_memories
  id pk, user_id fk (idx), kind (fact|preference|summary),
  content text, embedding vector(1536), source_session_id fk null, created_at
```

### Portfolio (drives AC4 "ask anything on the UI", AC5 risk, G3 HITL)

```
accounts
  id pk, user_id fk, name, type (cash|brokerage|retirement|crypto), created_at

positions
  id pk, account_id fk, symbol, quantity numeric, avg_cost numeric,
  asset_class (equity|bond|cash|crypto|alt), currency, updated_at

prices              # AC6 streaming source
  symbol pk-part, ts pk-part, price numeric

goals
  id pk, user_id fk, name, target_amount, target_date, current_amount, created_at
```

### RAG corpus (R1–R11)

```
documents
  id pk, source_uri, title, lang (default 'en'), doc_type, ingested_at,
  metadata_json jsonb

chunks
  id pk, document_id fk (idx), ord int, content text, token_count int,
  metadata_json jsonb,
  embedding vector(1536),               -- R1
  content_tsv tsvector                  -- R6 (Postgres FTS, GIN-indexed)

# R4 multimodal RAG
media_assets
  id pk, kind (image|audio), source_uri, caption text, transcript text,
  embedding vector(1536), metadata_json jsonb, ingested_at
```

### Agent tracing (A18–A20, lightweight beyond Langfuse)

```
agent_runs
  id pk, session_id fk, root_agent, status (running|done|failed),
  started_at, ended_at, langfuse_trace_id

agent_steps
  id pk, run_id fk, parent_step_id fk null, agent_name,
  tool_name nullable, input_json, output_json, confidence numeric null,
  started_at, ended_at
```

### Eval (E1–E7)

```
eval_suites
  id pk, name, description, kind (golden|adversarial|drift), created_at

eval_cases
  id pk, suite_id fk, prompt_json, expected_json, tags text[]

eval_runs
  id pk, suite_id fk, model, started_at, ended_at, summary_json

eval_results
  id pk, run_id fk, case_id fk, score numeric, passed bool, output_json,
  judge_rationale text
```

### Approvals (G3 / G4 human-in-the-loop)

```
approvals
  id pk, requested_by_session_id fk, action_kind (rebalance|trade|allocation),
  payload_json, status (pending|approved|rejected|expired),
  decided_by_user_id fk null, decided_at, rationale text
```

---

## 4. Demo Asset Preparation

The spec's acceptance notes are explicit: **multi-modal items require
committed fixtures**, the **RAG corpus must hit ≥1000 chunks across >10
documents** before any R* item can be claimed. Preparing these is its own
workstream, run in parallel with Tier A coding.

### 4.1 Image fixtures (V1–V5, SV1–SV4)

Live under `assets/fixtures/images/`. Each comes with a sidecar
`<name>.expected.json` describing the ground-truth answer for evals.

| File | Purpose | Spec items | Notes |
|------|---------|------------|-------|
| `portfolio-statement.png` | Synthetic broker statement, 8 holdings | V1, V2 | Invent the holdings; not real data |
| `pie-allocation.png` | Asset allocation pie | V1 | Demo chart for "what's my mix?" |
| `40cell-table.png` | 8 rows × 5 cols holdings table | SV1 | Symbol, qty, price, mkt val, % wt |
| `chart-30pts-3series.png` | 3 portfolios over 30 dates | SV4 | Equity / 60-40 / cash |
| `chart-recreate-source.png` | Same chart for SV2 recreation | SV2 | Render via Chart.js in UI |
| `bigtable-source.png` | Source table for SV3 10× synth | SV3 | 20 rows seed → 200 rows synth |
| `unsupported.psd` | Adobe file | V4 | Triggers graceful-handling path |
| `prompt-inject.png` | Image with embedded "ignore previous instructions" text | V5 | Adversarial test |
| `large/img-30mb-{1..4}.png` | 4 large images, ~30 MB each | V3 | Streamed upload + chunked OCR |

**How to make them quickly:** matplotlib for charts, Pillow + reportlab for
the statement. Script: `scripts/build_image_fixtures.py`. Each fixture
deterministic; rerun to regenerate.

### 4.2 Audio fixtures (Vo1–Vo5)

Under `assets/fixtures/audio/`.

| File | Purpose | Spec items |
|------|---------|------------|
| `client-question.m4a` | 15 s "what's my exposure to tech?" | Vo1 |
| `q1-q3.zip` of three short clips | Multi-file turn | Vo2 |
| `roundtable-5speakers.wav` | Synthesized 5-speaker convo (use 5 different TTS voices stitched) | Vo3 |
| Generated TTS reply | Vo4 |
| Live mic loop (browser MediaRecorder → Whisper → TTS) | Vo5 |

`scripts/build_audio_fixtures.py` stitches TTS clips with `pydub`.

### 4.3 RAG corpus (R1, R6 — gating)

Target: **≥1500 chunks across 12 documents**, mixed types so R3 metadata
filters and R2 multilingual have something to bite on.

Source list (all freely redistributable):

| Document | Type | Lang | Why |
|----------|------|------|-----|
| Vanguard *Principles for Investing Success* (PDF) | whitepaper | en | Core investing concepts |
| Bogleheads' Wiki — *Three-fund portfolio* | web | en | RAG-friendly explainer |
| SEC Investor Bulletin — *Mutual Funds and ETFs* | gov pub | en | Regulator voice |
| Federal Reserve Beige Book (latest) | gov pub | en | Macro context |
| BlackRock *2026 Investment Outlook* | report | en | Forward-looking |
| MSCI *Index methodology* | technical | en | Niche jargon for hybrid search |
| MAS *Guidelines on Standards of Conduct* (Singapore) | regulatory | en | Local angle |
| 银保监会 retail investor guide (excerpt) | regulatory | zh | R2 multilingual |
| BaFin *Verbraucherinformation* | regulatory | de | R2 multilingual |
| Synthetic *AuraWealth advisor playbook* (we author) | internal | en | Domain-specific, ungoogleable — proves retrieval |
| Synthetic *Risk-tolerance questionnaire methodology* | internal | en | AC5 risk inputs |
| Synthetic *Rebalancing protocol v2* | internal | en | Drives G3 advisor approvals |

**Pipeline:** `scripts/ingest_corpus.py`
1. Download / read PDF or HTML.
2. Extract text with `pypdf` / `trafilatura`.
3. Chunk (recursive, 500-token target, 50-token overlap).
4. Embed with `text-embedding-3-small` (1536-dim, cheap).
5. Upsert into `documents` + `chunks`.
6. Update `tsvector` via Postgres trigger.

Target ≥1500 chunks; hard-gate the build if below 1000.

### 4.4 Eval data (E1–E3, E6)

- `assets/eval/portfolio-qa.jsonl` — ≥120 (prompt, expected) pairs covering
  the 8 personas × 15 question templates. Hand-curated 30, LLM-augmented 90,
  human-spotchecked.
- `assets/eval/adversarial-prompts.jsonl` — ≥60 known prompt-injection
  attempts (reuse public lists: `tatsu-lab/alpaca-eval`, the OWASP LLM Top
  10 examples).
- `assets/eval/drift-baseline.parquet` — embedding distribution of week-1
  questions, used by E5.

---

## 5. Phasing

Each phase ends with a working, demoable cut. Phase plans (with bite-sized
TDD tasks) live in `docs/superpowers/plans/`.

### Phase 1 — Chat foundation (in flight)

**Plan file:** `docs/superpowers/plans/2026-06-16-phase1-chat-foundation.md`
**Spec coverage:** C1, C2, AC2, AC3 (partial), C4 (diagram).
**Demo:** open the web app as Client, chat. Switch to Advisor, chat with
different history. Run `python -m scripts.repl_chat --role client` for the
REPL alternate.

Deliverables:
- `users`, `chat_sessions`, `chat_messages` ORM + migration.
- `POST /api/v1/chat` SSE streaming, role-aware system prompts.
- REPL chat client with `--role` flag.
- Web chat panel + role switcher.
- System diagram in this doc + README.

### Phase 2 — Streaming data + portfolio + AC4

**Spec coverage:** AC1 (formalised), AC4, AC5, AC6.
**Demo:** dashboard with live ticker; ask "what's my YTD return?" and the
answer is grounded in the rendered numbers.

- Portfolio + accounts + positions + prices schema.
- Seed data for both demo users (different portfolios, different goals).
- `GET /api/v1/portfolio` + `GET /api/v1/prices/stream` (SSE, simulated tick).
- Frontend portfolio dashboard (Chart.js).
- AC4: pass current UI state JSON into chat system prompt.
- AC5: deterministic risk-score calculator + advisor view.

### Phase 3 — RAG corpus + hybrid search

**Spec coverage:** R1, R5, R6, R8, R10, R11.
**Demo:** semantic search bar in advisor view; chat queries cite document
chunks.

- Asset prep (§4.3) — corpus committed, ingestion script idempotent.
- `documents`, `chunks`, embeddings.
- `/api/v1/rag/semantic`, `/keyword`, `/hybrid` (RRF fusion).
- Reranker (cross-encoder via local `bge-reranker-base` for A11 +
  R10/R11).
- UMAP scatter for R5 (compute offline, ship as static JSON + UI).
- E1: 50-pair golden eval over the corpus, LLM-as-judge.

### Phase 4 — Multi-modal vision + audio (Tier A/B slice)

**Spec coverage:** V1, V2, V4, Vo1, Vo2, Vo4, SV1, SV4.
**Demo:** drop the 40-cell table screenshot, get JSON; drop a voice memo,
get a voice reply.

- Asset prep (§4.1, §4.2).
- Upload endpoint with MIME guard (V4) + size cap.
- Vision call: `gpt-4o` with image parts + structured JSON output schema.
- Audio: Whisper transcription + chat; TTS reply via `tts-1`.
- Frontend file dropzone + audio recorder.

### Phase 5 — Agentic core

**Spec coverage:** C3, A1–A3, A9, A10, A18, A19, G6.
**Demo:** ask a complex question, watch the orchestrator delegate; click a
trace link, see Langfuse render the run.

- Orchestrator + 4 expert agents:
  - **PortfolioAnalyst** (reads portfolio tables, AC4)
  - **MarketResearcher** (web search via Tavily/SerpAPI, A9)
  - **DocsLibrarian** (RAG over corpus)
  - **RiskAdvisor** (calls AC5 logic + cites guidelines)
- Hand-off via tool-call routing (A2).
- Hierarchical wrapper (A3) — same agents under a planner.
- Langfuse decorators on every LLM call.
- Trace viewer page in advisor portal (G6).

### Phase 6 — MCP + tool variants

**Spec coverage:** A13, A14, A16, A17, G7.
**Demo:** advisor types "rebalance to 60/40 for client X", MCP tool routes
through Postgres → SQL variant → API variant; log line `"hello world when
call"` appears for the custom MCP.

- MCP server in `backend/mcp/` exposing `query_portfolio`, `propose_trade`.
- Custom MCP that only accepts JSONL inputs (A14).
- Variants A16 (raw SQL) and A17 (HTTP API) of the same tool.
- Approvals table + advisor approval UI (G3, G4).

### Phase 7 — Performance + scaling

**Spec coverage:** S1, S2, S3, S6, S8, S9.
**Demo:** baseline chart, then post-cache chart; kill the worker mid-job,
show retry.

- Baseline harness: `scripts/bench_ttft.py` records p50/p95.
- Redis response cache (S2).
- arq queue for ingestion + eval (S8).
- Worker crash test (S9) with checkpointed state.
- TTFT optimisations: prompt caching, model selection per role.

### Phase 8 — Eval + governance

**Spec coverage:** E1–E6, G1, G2, G6, G7.
**Demo:** CI runs the eval suite on every PR; injection attempts blocked
with a visible reason.

- E1/E2: LLM-as-judge over golden sets.
- E3: 100+ pair set with distribution analysis notebook.
- E5: drift detector — embedding KS-test on weekly question stream.
- E6: 50+ adversarial prompts, automated.
- G1: regex + system-prompt guard (prompt injection).
- G2: PII filter on outbound responses.
- G7: each agent gets a signed identity + capability list.

### Phase 9 — Stretch (Tier C/D)

Only after Phases 1–8 ship. Cherry-pick by point-per-hour:
- A4 sub-agent spawn tree
- A5 self-correcting loop with confidence
- A11 local model (Ollama, llama-3.1-8b)
- V5 image-modality prompt injection
- SV2 chart recreation in UI
- R2 multilingual demonstration
- E7 advanced eval (e.g. pairwise preference + Bradley-Terry)

---

## 6. What's NOT in scope

Per YAGNI:
- No real broker integration. Synthetic data only.
- No real auth (OAuth, magic links). Role switcher in `localStorage` is the
  demo's "auth".
- No multi-tenancy. One Postgres, one app.
- No mobile app.
- No production deployment story beyond `docker compose up`.

---

## 7. Cross-cutting decisions to lock in

These are answers to the spec's §4 open questions. Locking them here so the
phase plans don't re-ask:

1. **Point splits** — assume the higher value where ambiguous (e.g. AC3 → +2).
2. **A7 frameworks** — Anthropic SDK loop (existing) + LangGraph
   (re-implementation).
3. **A11 local model** — Apple Silicon, Ollama, `llama-3.1-8b-instruct`.
4. **Voice latency target** — round-trip < 2 s for Vo5.
5. **MCP database** — Postgres (already provisioned).
6. **Vector DB for S11** — pgvector for the demo; if 100 QPS isn't met, fall
   back to Qdrant in `docker-compose.yml`. Decide after S6 baseline.

---

## 8. Risk register

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OpenAI rate limits on demo day | M | Stub fallback already in LLM service; cache (S2) reduces calls |
| pgvector slow at 100 QPS (S11) | M | Defer to Qdrant if baseline fails; pre-warm index |
| Multi-speaker audio (Vo3) hard to validate | L | Synthesize fixture deterministically; ground-truth diarisation in JSON |
| Trace viewer (G6) eats time | M | Use Langfuse iframe — don't build a custom viewer |
| Eval set hand-curation drag | H | LLM-augment 90% of E3, hand-spotcheck 10% |

---

## 9. How to read the rest of the docs

- `docs/features-spec.md` — the source of truth for what we're building.
- `docs/implementation-plan.md` (this file) — the strategic roadmap.
- `docs/superpowers/plans/` — per-phase, bite-sized executable plans.
- `docs/superpowers/specs/` — design docs for any phase that needed
  brainstorming before planning.
