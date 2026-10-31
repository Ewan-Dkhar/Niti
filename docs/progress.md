# Niti — Progress

Phase plan: `/home/ewan/.opencode/plan/niti-phases.md`

- [x] Phase 0 — Repo scaffold & tooling
- [x] Phase 1 — Config & API contract skeleton
- [x] Phase 2 — Schema unit tests
- [ ] Phase 3 — Document ingestion & parsing (Docling)
- [ ] Phase 4 — Hierarchical chunker + Qdrant hybrid index
- [ ] Phase 5 — LangGraph state machine skeleton
- [ ] Phase 6 — Rule extraction node
- [ ] Phase 7 — Hallucination audit node
- [ ] Phase 8 — Vernacular simplification
- [ ] Phase 9 — Sarvam Bulbul v3 TTS
- [ ] Phase 10 — Citizen verification endpoint
- [ ] Phase 11 — Live data endpoints
- [ ] Phase 12 — Next.js frontend
- [ ] Phase 13 — Resilience & cached fallbacks
- [ ] Phase 14 — E2E test & packaging

## Verification log

- Phase 0: `uv sync` ok; `pytest` 1 passed; `GET /health` 200.
- Phase 1: `pytest` 8 passed; ruff clean; live curl verified analyze (202), results (200), verify-citizen (501 stub), OpenAPI (200).
- Phase 2: `pytest` 34 passed (26 new schema tests); ruff check/format clean; `known-first-party = ["app"]` added to ruff config.
