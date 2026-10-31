# Niti — Progress

Phase plan: `/home/ewan/.opencode/plan/niti-phases.md`

- [x] Phase 0 — Repo scaffold & tooling
- [x] Phase 1 — Config & API contract skeleton
- [x] Phase 2 — Schema unit tests
- [x] Phase 3 — Document ingestion & parsing (Docling)
- [x] Phase 4 — Hierarchical chunker + Qdrant hybrid index
- [x] Phase 5 — LangGraph state machine skeleton
- [x] Phase 6 — Rule extraction node
- [x] Phase 7 — Hallucination audit node
- [x] Phase 8 — Vernacular simplification
- [x] Phase 9 — Sarvam Bulbul v3 TTS
- [x] Phase 10 — Citizen verification endpoint
- [ ] Phase 11 — Live data endpoints
- [ ] Phase 12 — Next.js frontend
- [ ] Phase 13 — Resilience & cached fallbacks
- [ ] Phase 14 — E2E test & packaging

## Verification log

- Phase 0: `uv sync` ok; `pytest` 1 passed; `GET /health` 200.
- Phase 1: `pytest` 8 passed; ruff clean; live curl verified analyze (202), results (200), verify-citizen (501 stub), OpenAPI (200).
- Phase 2: `pytest` 34 passed (26 new schema tests); ruff check/format clean; `known-first-party = ["app"]` added to ruff config.
- Phase 3: `pytest` 47 passed; ruff clean; live `labour.gov.in` gazette parsed with pypdf (2 pages) and Docling (2 pages, 4,463 chars).
- Phase 4: `pytest` 56 passed; ruff clean; live gazette chunked into 10 chunks and queried with multilingual-e5-large + BM25; "provident fund" returned the EPF inspection-charge table with page/clause citations.
- Phase 5: `pytest` 62 passed; ruff clean; live graph run completed parse → extract → audit → simplify → voice with the expected stub state.
- Phase 6: `pytest` 71 passed; ruff clean; mock provider extracted grounded fields + citations from the live gazette; Anthropic/OpenAI providers compile and are selected by key.
- Phase 7: `pytest` 77 passed; ruff clean; fabricated amount/date/claim and missing-citation cases flagged; retry counter + correction guidance routed back to extraction.
- Phase 8: `pytest` 86 passed; ruff clean; localized scripts generated for hi/ta/bn/te/en; mock provider also accepted as the graph's simplify step.
- Phase 9: `pytest` 95 passed; ruff clean; mock WAV generated and written to `data/media/<task>.wav`; `/media` mounted; results endpoint now returns completed `AnalysisResult` with script, duration, and audio URL.
- Phase 10: `pytest` 104 passed; ruff clean; live gazette task returned a playable 51s WAV (`/media/<task>.wav`) and `/verify-citizen` matched cited clauses with document gap reporting.
