# AGENTS.md

## Status

Greenfield repo. Phase 0 scaffold exists; application code is built incrementally. The implementation blueprint and phase plan live at `docs/plan.md` — read it before starting work.

## Before writing code

- Follow the phase order in `docs/plan.md` (Phase 0 → 14). Each phase must run and pass its verification step before starting the next one.
- Do not scaffold the whole stack up front. Build one vertical slice at a time.
- Confirm what already exists (`git status`, `find . -maxdepth 3 -type f`) before assuming structure.

## Toolchain constraints (non-obvious)

- Use **Python 3.11**. Some systems default to a newer Python (3.13/3.14), which the ML dependencies (Docling, LangGraph ecosystem, Qdrant client) do not reliably support yet.
- Use **Node 22 LTS** via nvm. A newer Node may be active by default; do not use it for the frontend.
- Use `uv` for the Python environment. `uvicorn` is not installed globally.

## API keys

Keys are not committed and may be absent in a fresh checkout. Until they are supplied:

- Implement LLM/TTS calls behind provider interfaces with working mocks.
- Gate real calls with `USE_MOCK_LLM` and `USE_MOCK_TTS` env flags (default to mock).
- Never commit `.env`; add keys only to `.env` and keep `.env.example` updated.

## Intended layout (per blueprint)

- `backend/app/main.py` → FastAPI entrypoint (`app.main:app`)
- `backend/app/agent/` → LangGraph state, graph, and nodes
- `backend/app/services/` → parser, chunker, vectorstore, TTS, live sources
- `backend/app/schemas.py` → Pydantic contracts (`PolicyExtraction`, `AuditResult`, `VoicePayload`)
- `frontend/` → Next.js 14 App Router + Tailwind
- `docs/progress.md` → phase checklist

## Data rules

- **Zero dummy data.** Final flows must hit live endpoints (`myscheme.gov.in`, PIB RSS, user-supplied `*.gov.in` PDFs). Cached local fixtures are allowed only as explicit offline fallbacks.
- Extraction must be grounded: the audit node cross-checks claims against source chunks; do not bypass it to speed up demos.

## Commands (verify against manifests once created)

- Backend: `uv run uvicorn app.main:app --reload --app-dir backend`
- Tests: `uv run pytest`
- Frontend: `npm run dev` inside `frontend/`
- If a `Makefile` exists, prefer its targets over ad-hoc commands.
