# AuraWealth — Features Specification

> Source: `features/` (handwritten / printed brief, 5 pages, transcribed 2026-06-16).
> Numbers in `+N` are the point values from the brief. They drive prioritisation.

---

## 1. Application Overview

**AuraWealth** is a consumer-facing wealth management application that bridges
the gap between high-touch human advice and digital efficiency. It replaces
fragmented spreadsheets and manual reporting with a unified, transparent
platform for both everyday investors and their wealth managers.

### 1.1 Personas

- **Client (end investor).** The app acts as a "financial GPS": real-time,
  holistic view of net worth alongside visual progress tracking for specific
  life goals. Removes the friction of traditional banking through a secure
  concierge and **instant AI advisor access via an in-app chat interface**.

- **Advisor / Admin user.** The backend portal acts as a "command center"
  designed to scale personal service. Automates administrative burdens
  (client portfolio review, risk analysis, conversation management,
  portfolio rebalancing) and uses AI-driven insights to flag clients in
  need of attention — so advisors can manage a larger book of business
  while deepening individual relationships.

The product transforms wealth management from a series of static reports
into a collaborative, real-time partnership.

---

## 2. Feature Catalogue

Each item is tagged with its source-document point value. Items grouped by
section as in the brief.

### 2.1 Core (start here)

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| C1  | Basic AI chat interface off REPL terminal with an LLM                            | +1  |
| C2  | Basic chat client interface as a web app                                         | +2  |
| C3  | Sequential agentic workflow with at least 3 agents                               | (—) |
| C4  | System design diagram reflecting the current implementation (code + models)      | +1  |

### 2.2 Advanced Core

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| AC1 | Backend is event-driven and async                                                | +2  |
| AC2 | **Client side (0 pts gating):** multi-turn dialogue management, state across interactions | +1  |
| AC3 | Different user log-on showing different context and conversational history       | +2 / +1 |
| AC4 | Show one can ask questions against any data reflected in the UI                  | +2  |
| AC5 | **Admin side (0 pts gating):** implement risk analysis                           | (—) |
| AC6 | Implement streaming data for prices (simulated stream is fine)                   | +2  |

### 2.3 GenAI — Multi-modal

#### 2.3.1 Vision

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| V1  | Image upload; responses understand image content                                 | +1  |
| V2  | Multiple images per turn                                                         | +1  |
| V3  | >100 MB upload (incl. multiple large images) with no degradation of UX or comprehension | +3  |
| V4  | Unsupported file types — graceful handling + documented workaround               | +2  |
| V5  | Demonstrate prompt-hacking via image modality against a model **no earlier than 2025** | +2  |

#### 2.3.2 Voice

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| Vo1 | Audio upload; responses understand audio content                                 | +1  |
| Vo2 | Multiple audio files per turn                                                    | +1  |
| Vo3 | Audio file with **>4 speakers** (diarisation-aware comprehension)                | +1  |
| Vo4 | Generate a voice reply                                                           | +2  |
| Vo5 | Live user ↔ AI voice interaction                                                 | +2  |

#### 2.3.3 Structured Vision

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| SV1 | Accurate information extraction from a table with **≥ 40 cells**                 | +2  |
| SV2 | Recreate the chart as a responsive UI element                                    | +2  |
| SV3 | Use the table to synthesise data with similar distribution at **10× scale**      | +2  |
| SV4 | Extract information from a chart with **≥ 30 data points and 3 data series** (no pie chart) | +2  |

### 2.4 RAG and Vector DB

#### 2.4.1 Semantic search

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| R1  | Semantic search with **≥ 1000 chunks** spanning **>10 documents**                | (gating) |
| R2  | Semantic search across multilingual content                                      | +2  |
| R3  | Use metadata to enhance search                                                   | +2  |
| R4  | Search against the semantics of images or audio                                  | +4  |
| R5  | Show semantic clustering of the docs / data                                      | +1  |

#### 2.4.2 Keyword search

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| R6  | Keyword search with **≥ 1000 chunks** spanning **>10 documents**                 | (gating) |
| R7  | Up-weight specific keywords                                                      | +2  |

#### 2.4.3 Hybrid + reranking

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| R8  | Hybrid search using both components, integrated into a workflow                  | +2  |
| R9  | Dynamic prompt optimisation for domain query precision                           | (—) |
| R10 | Custom reranking criteria — rationale included                                   | (—) |
| R11 | Proof reranking works; metrics discussed                                         | +2  |

### 2.5 Agentic

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| A1  | 4 expert agents covering different application topics                            | (—) |
| A2  | AI agent hand-off between specialised domain expert sub-agents                   | (—) |
| A3  | Convert sequential workflow into a **hierarchical** one with a main orchestrator | (—) |
| A4  | Agents dynamically spawn ≥ 3 non-trivial sub-agents to complete tasks            | +2  |
| A5  | Self-correcting agent reasoning with confidence scoring + fallback logic         | +2  |
| A6  | Show objectively that agent performance improves with user feedback              | +3  |
| A7  | Re-implement ≥ 2 agent workflows using a **different** agentic framework        | +2  |
| A8  | Discuss pros and cons of each framework                                          | +1  |
| A9  | Web-search / grounding                                                           | +1  |
| A10 | Use **≥ 4 different models**                                                     | (—) |
| A11 | Run one of the models locally                                                    | +1  |
| A12 | Context-aware conversation memory persisting across user sessions                | +2  |
| A13 | **MCP tool call against a database**                                             | +2  |
| A14 | Customised MCP that logs `"hello world when call"` and only accepts JSONL string inputs | +2  |
| A15 | SSO and SSE set up for MCP                                                       | +3  |
| A16 | Variant: change the tool call to SQL scripts instead                             | (—) |
| A17 | Variant: change the tool call to API calls instead                               | (—) |
| A18 | Trace and monitoring                                                             | +1  |
| A19 | In-depth trace for **all** LLM interactions                                      | +2  |
| A20 | Show agent trajectory                                                            | +4  |

### 2.6 AI App Evaluation (non-trivial)

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| E1  | Initial evaluation of the core workflow                                          | +1  |
| E2  | Same for a second core workflow with a different test set                        | +1  |
| E3  | ≥ 100 test/ground-truth pairs for one eval, with proof the eval set is meaningful (distribution / edge cases) | +3  |
| E4  | Automate evaluation (minimum human tester involvement) for a core workflow       | +3  |
| E5  | Implement the exception workflow for **data drift**                              | +2  |
| E6  | Automated prompt-hacking test against ≥ 50 known malicious prompts               | +2  |
| E7  | Show an advanced evaluation technique and explain it well                        | +3  |
| E8  | Show that the system works when randomly tested                                  | (—) |

### 2.7 Scaling, Performance, Reliability

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| S1  | Real-time response generation: **<5 s time-to-first-token**                      | (gating) |
| S2  | Cache implemented + logic explained                                              | +1  |
| S3  | **<1 s TTFT across 10 semantically different queries**                           | +2  |
| S4  | Show that the client side meets these targets                                    | (—) |
| S5  | **2× throughput** improvement                                                    | (—) |
| S6  | Show baseline first                                                              | +1  |
| S7  | Proof through scaling and horizontal scaling on the client side                  | +5  |
| S8  | Message queue for one of the longer-running tasks                                | +3  |
| S9  | Crash the application and show messages are still successfully processed        | (—) |
| S10 | Scaling logic for vector and search DB / endpoints                               | +3  |
| S11 | Vector DB responds at **100 QPS** across a corpus-wide range of semantic queries | +5  |

### 2.8 AI Governance

| ID  | Feature                                                                          | Pts |
| --- | -------------------------------------------------------------------------------- | --- |
| G1  | **Guard rails:** inline guardrails against prompt hacking                        | +1  |
| G2  | Guardrails against info exfiltration                                             | +2  |
| G3  | Sensible human-in-the-loop for a sensible workflow                               | +2  |
| G4  | Meaningful exception handling (e.g. what if the human operator disapproves)      | +2  |
| G5  | Allow human operator to chat with the system to gather data or analysis          | (—) |
| G6  | Explainability for a specific AI workflow                                        | +2  |
| G7  | Agentic registration and identity                                                | +2  |

---

## 2.9 Implementation-cost & demo-ability ranking

> Point values from the brief are **ignored** here. Each row is rated on:
> **Build** (how hard to implement, S/M/L/XL) and **Demo** (how easy to show
> live in front of someone, ★ = trivial, ★★★★ = needs setup or fragile).
> Rows are roughly ordered cheapest-and-flashiest-first.

### Tier A — Trivial to build, instantly demoable (do these first)

| ID  | Feature                                              | Build | Demo | Why it's cheap |
| --- | ---------------------------------------------------- | ----- | ---- | -------------- |
| C1  | REPL chat with an LLM                                | S     | ★    | A loop + one API call. |
| C2  | Web chat UI                                          | S     | ★    | shadcn/Vercel chat starter; SSE stream. |
| C4  | System-design diagram                                | S     | ★    | Mermaid in README; reflects code that exists. |
| V1  | Single image upload + understanding                  | S     | ★    | Multimodal API accepts image directly. |
| V2  | Multiple images per turn                             | S     | ★    | Same call, list of parts. |
| Vo1 | Single audio upload + understanding                  | S     | ★    | Whisper or multimodal endpoint. |
| Vo2 | Multiple audio files                                 | S     | ★    | Trivial extension of Vo1. |
| A9  | Web-search / grounding                               | S     | ★    | One tool call to a search API. |
| A18 | Trace and monitoring                                 | S     | ★    | LangSmith / Langfuse drop-in. |
| A19 | In-depth trace for all LLM interactions              | S     | ★    | Free byproduct of A18. |
| E1  | Initial eval of one core workflow                    | S     | ★★   | 10–20 hand-written prompts + LLM-as-judge. |
| G1  | Inline guardrails against prompt hacking             | S     | ★    | Regex + system-prompt rules; demo with the canonical "ignore previous" prompt. |
| S6  | Record baseline performance                          | S     | ★    | `time` + a couple of curls; one chart. |
| AC2 | Multi-turn dialogue with state                       | S     | ★    | Persist messages keyed by session id. |
| AC3 | Different users → different context & history        | S     | ★    | Falls out of AC2 once auth exists. |

### Tier B — Small extra work, still very demoable

| ID  | Feature                                              | Build | Demo | Notes |
| --- | ---------------------------------------------------- | ----- | ---- | ----- |
| C3  | Sequential workflow with ≥ 3 agents                  | M     | ★★   | One orchestrator + three role prompts. |
| AC1 | Async/event-driven backend                           | M     | ★★   | FastAPI is already async — wire a queue or SSE. |
| AC4 | Ask questions against any data on the UI            | M     | ★★   | Ship UI state into the prompt as JSON. |
| AC6 | Streaming prices (simulated)                         | S     | ★    | Async generator + SSE; very visual. |
| V4  | Graceful unsupported file-type handling              | S     | ★★   | MIME check + friendly error; explain workaround. |
| Vo4 | Voice reply                                          | S     | ★    | TTS endpoint; plays in-browser. |
| SV1 | Extract from a 40-cell table                         | M     | ★★   | One vision call + JSON schema; commit a fixture table. |
| SV4 | Extract a chart with ≥ 30 points / 3 series          | M     | ★★   | Same prompt-and-schema pattern as SV1. |
| R1  | Semantic search ≥ 1000 chunks / >10 docs             | M     | ★★   | pgvector + a public corpus (e.g. SEC filings). |
| R5  | Semantic clustering visual                           | S     | ★★   | UMAP/t-SNE scatter — looks impressive, costs little. |
| R6  | Keyword search ≥ 1000 chunks / >10 docs              | S     | ★★   | Postgres full-text on the same corpus. |
| R8  | Hybrid search in a workflow                          | M     | ★★   | Reciprocal-rank fusion of R1+R6. |
| A1  | 4 expert agents covering different topics            | M     | ★★   | Four prompts; a thin router. |
| A2  | Agent hand-off                                       | S     | ★★   | Falls out of A1's router. |
| A3  | Hierarchical orchestrator                            | M     | ★★   | Same agents under a planner agent. |
| A10 | Use ≥ 4 different models                             | S     | ★    | Route different roles to different model IDs. |
| A12 | Memory persisting across sessions                    | M     | ★★   | Store summaries in Postgres keyed by user. |
| A13 | MCP tool call against a database                     | M     | ★★   | Already have Postgres; one MCP tool. |
| A14 | Custom MCP that logs `"hello world"` + JSONL inputs  | S     | ★★   | Tiny custom server. |
| G3  | Sensible human-in-the-loop                           | M     | ★★   | "Advisor approves rebalancing" gate. |
| G4  | Meaningful exception handling on operator disapprove | S     | ★★   | Falls out of G3. |
| G6  | Explainability for a specific workflow               | M     | ★★   | Render the trace from A18 nicely. |
| E2  | Same eval against a second workflow / test set       | S     | ★★   | Reuse E1 harness. |
| E5  | Data-drift exception workflow                        | M     | ★★   | Embedding-shift detector → alert. |
| E6  | Prompt-hacking test ≥ 50 prompts                     | S     | ★★   | Public adversarial-prompt list + assertions. |
| S2  | Cache + logic explained                              | S     | ★★   | Redis or in-memory LRU; simple chart. |
| S8  | Message queue for long-running task                  | M     | ★★   | Add Redis/RQ or arq for one job (e.g. ingestion). |

### Tier C — Worth doing if Tier A/B is solid; needs care to demo

| ID  | Feature                                              | Build | Demo |
| --- | ---------------------------------------------------- | ----- | ---- |
| V5  | Prompt-hacking via image modality                    | M     | ★★★  |
| Vo3 | Audio with > 4 speakers                              | M     | ★★★  |
| SV2 | Recreate chart as responsive UI element              | M     | ★★★  |
| SV3 | Synthesise 10× table with similar distribution       | M     | ★★   |
| R2  | Multilingual semantic search                         | S     | ★★   |
| R3  | Metadata-enhanced search                             | M     | ★★   |
| R7  | Keyword up-weighting                                 | S     | ★★   |
| R10 | Custom reranker + rationale                          | M     | ★★★  |
| R11 | Reranker proof + metrics                             | M     | ★★★  |
| A4  | Agents dynamically spawn ≥ 3 sub-agents              | M     | ★★★  |
| A5  | Self-correcting reasoning + confidence + fallback    | M     | ★★★  |
| A7  | Re-implement ≥ 2 workflows in another framework      | L     | ★★   |
| A8  | Pros/cons of each framework                          | S     | ★    |
| A11 | Run one model locally                                | M     | ★★   |
| A16 | Variant: tool call → SQL                             | S     | ★★   |
| A17 | Variant: tool call → API                             | S     | ★★   |
| A20 | Show agent trajectory                                | M     | ★★   |
| E4  | Automated eval (min human involvement)               | M     | ★★   |
| S1  | <5 s TTFT                                            | S     | ★★   |
| S3  | <1 s TTFT across 10 different queries                | M     | ★★★  |
| G2  | Guardrails against info exfiltration                 | M     | ★★★  |
| G7  | Agentic registration / identity                      | M     | ★★★  |
| AC5 | Risk analysis (admin)                                | M     | ★★   |

### Tier D — Expensive or hard to show convincingly (defer)

| ID  | Feature                                              | Build | Demo |
| --- | ---------------------------------------------------- | ----- | ---- |
| V3  | >100 MB upload, no UX hit                            | L     | ★★★  |
| Vo5 | Live voice interaction                               | L     | ★★★★ |
| R4  | Semantic search of images/audio                      | L     | ★★★  |
| R9  | Dynamic prompt optimisation                          | L     | ★★★★ |
| A6  | Prove perf improves with user feedback               | L     | ★★★★ |
| A15 | SSO + SSE for MCP                                    | L     | ★★★  |
| E3  | ≥ 100 ground-truth pairs + meaningfulness proof      | L     | ★★   |
| E7  | Advanced eval technique                              | L     | ★★★  |
| S5  | 2× throughput                                        | L     | ★★★  |
| S7  | Horizontal scaling proof, client side                | XL    | ★★★★ |
| S9  | Crash app, messages still successful                 | M     | ★★★  |
| S10 | Scaling logic for vector / search DB                 | L     | ★★★  |
| S11 | 100 QPS vector DB                                    | L     | ★★★★ |

---

## 3. Acceptance / "Definition of done" notes

- **Multi-modal demos** (V*, Vo*, SV*) require concrete artefacts — a fixed
  test image set, audio set, and table/chart pair — committed to the repo and
  referenced from the demo flow.
- **RAG corpus** must contain >10 distinct documents and ≥ 1000 chunks before
  any R* item can be claimed; this is a gate, not a feature.
- **Agentic** items A4/A5/A6 each need an artefact: spawn-tree screenshot,
  confidence-score log, before/after eval scores, respectively.
- **Evaluation** items E3 / E6 produce CSVs (or equivalent) checked in; tests
  in CI consume them.
- **Scaling** items require a baseline reading **first** (S6) — claims about
  improvement are not landable without a recorded baseline.
- **Governance** items must each show a triggering test case (a prompt that
  would have succeeded without the guardrail).

---

## 4. Open questions / clarifications needed

1. **Authoritative point totals.** Several brief items have ambiguous values
   (e.g. AC3 reads `+2 ... +1`, suggesting two sub-items). Confirm the split
   before sequencing work.
2. **"Different agentic framework" (A7).** Which two frameworks are
   acceptable? (e.g. LangGraph + CrewAI; Anthropic SDK loop + LangGraph.)
3. **Local model (A11).** Hardware target? Apple Silicon-only is fine for the
   demo machine but should be stated.
4. **Voice (Vo4/Vo5).** Acceptable latency for "live" voice — is round-trip
   <2 s sufficient?
5. **MCP (A13–A15).** Which database? Postgres (already provisioned) is the
   obvious choice; confirm.
6. **Vector DB (S11).** Target deployment — managed (Pinecone/Weaviate Cloud)
   or self-hosted (pgvector / Qdrant)? 100 QPS is achievable on either but
   the proof artefact differs.

