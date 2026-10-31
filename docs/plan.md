# Niti — Phased Implementation Plan

**Autonomous Plain-Language Civic Rights & Multilingual Voice Explainer**

Stack: FastAPI + Uvicorn, Docling, LangGraph, Claude 3.5/GPT-4o, Groq Llama-3.3, Sarvam Bulbul v3, Qdrant, Next.js 14.

Python 3.11 (not 3.14 — ML libs lag). Node 22 LTS. No API keys yet → Phases 6/8/9 start with mocked providers, swap to real keys later.

## Guiding principles
- One vertical slice per phase; each must boot + pass smoke test before next.
- Stub before integrate; env-gate heavy deps (Docling, Qdrant, Sarvam).
- Commit + tag `phase-N` after every phase.
- Keep `docs/progress.md` checklist.

## Phase 0 — Repo scaffold & tooling
- Init git, `.gitignore`, `.env.example` (all keys).
- Python 3.11 venv via uv, `pyproject.toml` core deps only (fastapi, uvicorn, pydantic, pydantic-settings, httpx, python-dotenv, pytest).
- `frontend/` placeholder. `Makefile`: dev-backend, dev-frontend, test, lint.
- `backend/app/main.py` with `/health`.
Verify: uvicorn boots; `/health` 200; pytest green.

## Phase 1 — Config & API contract skeleton
- `core/config.py` (Pydantic Settings).
- `schemas.py` with PolicyExtraction, AuditResult, VoicePayload.
- Routers analyze/results/verify_citizen returning stubs + task_id.
- In-memory task store + background task stub.
Verify: curl all endpoints; OpenAPI renders.

## Phase 2 — Schema unit tests
- Validation tests for required/optional/null, citation_source_map, language_code.
- `tests/conftest.py` fixtures.
Verify: pytest tests/test_schemas.py.

## Phase 3 — Document ingestion & parsing (Docling)
- `services/parser.py`: fetch PDF (validate gov.in or allow any), Docling → markdown, persist.
- Env flag USE_DOCLING=false → pypdf fallback.
- Wire into /analyze background task.
Verify: parse one real gov.in PDF; inspect markdown tables/columns.

## Phase 4 — Hierarchical chunker + Qdrant hybrid index
- `services/chunker.py`: Section (parent)/Clause (child) chunks + metadata.
- `services/vectorstore.py`: Qdrant dense (bge-m3) + sparse (BM25), hybrid search.
- Dev mode in-memory/file Qdrant.
Verify: ingest doc, query "eligibility income" → relevant clause with citation.

## Phase 5 — LangGraph state machine skeleton
- `agent/state.py`, `graph.py` with stub nodes + conditional edge route_audit.
- Compile; expose run_analysis invoked by background task.
Verify: graph runs end-to-end on stubs.

## Phase 6 — Rule extraction node (Claude 3.5 / GPT-4o)
- `agent/nodes/extract.py`: prompt + retrieved context, structured output via Pydantic schema.
- Provider abstraction (Anthropic or OpenAI).
- Tests with fixture markdown + mocked LLM (no keys).
Verify: extract from sample; JSON validates; citation_source_map populated.

## Phase 7 — Hallucination audit node
- `agent/nodes/audit.py`: regex monetary figures/dates; cross-check; AuditResult.
- route_audit retry <2 with correction guidance; increment retry count.
Verify: injected fabricated number → audit fails → retry corrects.

## Phase 8 — Vernacular simplification (Groq Llama-3.3)
- `agent/nodes/simplify.py` + `prompts/vernacular.py`: code-mixing rules, number spelling, 3-part structure.
- Tests allowlist check.
Verify: Hindi script from extracted data readable.

## Phase 9 — Sarvam Bulbul v3 TTS
- `services/tts.py`: call Sarvam, return base64/file URL + duration.
- `synthesize_voice_node` stores audio_output_url; serve via /media.
- Mocked TTS for no-key dev.
Verify: audio generated for hi-IN; plays locally.

## Phase 10 — Citizen verification endpoint
- Deterministic eligibility matching against extracted policy.
- Return is_eligible, matched_clauses, missing_documents.
Verify: matching profile eligible; missing doc listed.

## Phase 11 — Live data endpoints (myScheme + PIB RSS)
- `services/sources.py`: fetch + normalize; TTL cache; graceful failure.
Verify: live fetch returns real entries.

## Phase 12 — Next.js frontend
- App Router, Tailwind, Lucide, Wavesurfer.
- Analyze form, results (player + rights matrix + citation drawer), verify form.
- Poll /results or SSE.
Verify: full flow in browser.

## Phase 13 — Resilience & cached fallbacks
- Cache parsed markdown + audio; fallback on network failure; timeouts/retries; UI error states.
Verify: kill network → cached demo serves.

## Phase 14 — E2E test & packaging
- E2E with 3 live gov.in PDFs; assert audit grounded.
- Docker compose (backend + qdrant + frontend) optional; README.
Verify: runbook reproduces.

## API keys
None available yet. Phases 6/8/9 implement provider interfaces with mock implementations first; real calls enabled when keys added to .env. Keep mock behind env flag `USE_MOCK_LLM`/`USE_MOCK_TTS`.
