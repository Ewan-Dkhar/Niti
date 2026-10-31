# Niti

**Clear policy. Real rights. In your language.**

Niti reads an Indian government policy PDF — a gazette notification, scheme
guideline, or circular — and turns it into a plain-language brief with a voice
note, a cited rights sheet, and a rule-by-rule eligibility check. Every extracted
claim is checked against the source page it came from before it reaches the
citizen.

Built with FastAPI, LangGraph, Docling/pypdf, Qdrant, Sarvam Bulbul v3, Groq
Llama 3.3, and Next.js 14.

---

## What it does

1. **Ingest** — fetches a public PDF from a URL (25 MB limit, retries, content
   sniffing) and parses it with Docling when enabled, or pypdf as a fallback.
2. **Extract** — chunks the document hierarchically and asks Claude 3.5, GPT-4o,
   or a deterministic local extractor for a `PolicyExtraction`: beneficiaries,
   eligibility, exclusions, benefits, documents, deadlines, and a citation for
   every rule.
3. **Audit** — re-checks every amount, date, and content claim against the parsed
   text. Unsupported claims trigger up to two re-extractions with correction
   guidance. The final verdict is shown to the user; it is never hidden.
4. **Localize** — writes a three-part 60-second script in Hindi, Tamil, Bengali,
   Telugu, or English, keeping everyday administrative loanwords.
5. **Speak** — calls Sarvam Bulbul v3 and serves the WAV from `/media`, or writes
   a real playable placeholder WAV when no key is configured.
6. **Verify** — compares a citizen profile (income, occupation, state, documents)
   with the extracted rules and returns cited matches, a verdict, and missing
   documents.
7. **Discover** — serves live myScheme schemes and PIB RSS releases through one
   cached endpoint.

## Architecture

```
Browser (Next.js 14)
   │  POST /api/v1/analyze
   ▼
FastAPI ── background task ──► LangGraph
                                parse_document
                                    │
                                extract_rules ◄──── retry (max 2)
                                    │
                                audit_verification
                                    │ grounded?
                                    ▼
                                simplify_vernacular
                                    │
                                synthesize_voice ──► data/media/<task>.wav
   │  GET /api/v1/results/{id} (poll)
   ▼
ResultSheet: audit stamp, script, player, cited rights sheet, eligibility desk
```

## Quickstart

Prerequisites: **Python 3.11**, **Node 22 LTS**, **uv**.

```bash
# backend
uv sync
cp .env.example .env          # optional; mock defaults work without keys
uv run uvicorn app.main:app --reload --app-dir backend

# frontend (new terminal)
source ~/.nvm/nvm.sh && nvm use 22
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Paste a public PDF link, for example:

```
https://labour.gov.in/static/uploads/2026/06/0c9a83a81e01bef6936dc4437c7fc310.pdf
```

The pipeline takes roughly 20–60 seconds depending on document size.

### Docker

```bash
docker compose up --build
```

This starts the backend on `:8000`, the frontend on `:3000`, and a Qdrant
instance on `:6333`. The frontend image bakes `NEXT_PUBLIC_API_BASE_URL` at
build time; override it with the compose build arg if the API is not on
`localhost:8000`.

## Configuration

Copy `.env.example` to `.env`. Every flag has a safe default.

| Variable | Default | Meaning |
| --- | --- | --- |
| `USE_MOCK_LLM` | `true` | Local heuristic extraction and template scripts |
| `USE_MOCK_TTS` | `true` | Local WAV placeholder instead of Sarvam |
| `USE_DOCLING` | `false` | Docling layout parser; pypdf fallback when off |
| `OFFLINE_MODE` | `false` | Serve parsed documents only from `data/cache` |
| `EXTRACTION_PROVIDER` | `auto` | `anthropic`, `openai`, `groq`, `mock`, or auto-by-key |
| `ANTHROPIC_API_KEY` | — | Enables Claude extraction |
| `OPENAI_API_KEY` | — | Enables GPT extraction |
| `GROQ_API_KEY` | — | Enables Groq extraction & vernacular scripts |
| `SARVAM_API_KEY` | — | Enables real Bulbul v3 speech |
| `QDRANT_URL` / `QDRANT_PATH` | local path | Hybrid retrieval backend |

Mock mode is not fake policy data: the mock extractor returns sentences and
numbers that actually appear in the fetched document. The mock TTS is explicitly
labelled as a placeholder in the UI.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `POST` | `/api/v1/analyze` | Queue a document analysis (202 + `task_id`) |
| `GET` | `/api/v1/results/{task_id}` | Poll status and the final `AnalysisResult` |
| `POST` | `/api/v1/verify-citizen` | Match a profile against a completed analysis |
| `GET` | `/api/v1/sources?q=&limit=` | Live myScheme + PIB feed with per-source errors |
| `GET` | `/media/{task}.wav` | Synthesized voice note |

Interactive docs: <http://localhost:8000/docs>.

### Example

```bash
curl -s -X POST http://localhost:8000/api/v1/analyze \
  -H 'content-type: application/json' \
  -d '{
    "document_url": "https://labour.gov.in/static/uploads/2026/06/0c9a83a81e01bef6936dc4437c7fc310.pdf",
    "target_language": "hi-IN"
  }'

curl -s http://localhost:8000/api/v1/results/<task_id>
```

## Grounding rules

The audit is deliberately mechanical, not another model call:

- every number in a claim must appear in the source text;
- every date must appear verbatim (normalized whitespace);
- at least half of a claim's content words must overlap the source;
- every claim needs a citation entry;
- placeholder values such as “Not stated in document” are not treated as claims.

A failed audit sends correction guidance back to the extractor. After two
retries the result is still returned, but marked **Needs review** and the
unsupported claims are listed in the UI.

## Resilience

- PDF fetches retry transient network errors, 429, and 5xx with exponential
  backoff; 4xx fails fast.
- Parsed documents are cached by URL hash under `data/cache/`. If the source is
  unreachable, the cached parse is used and the UI says so.
- Audio is cached by text + language and reused across retries.
- myScheme/PIB feeds use a TTL cache and fall back to stale entries when a
  refresh fails; the endpoint reports partial failures instead of returning
  invented data.
- `OFFLINE_MODE=true` serves only cached parses for demos without a network.

## Verification

```bash
uv run pytest                 # offline suite (121 tests)
uv run pytest -m live         # 3 real government PDFs, full API E2E
uv run ruff check backend scripts
uv run ruff format --check backend scripts
cd frontend && npm run build  # type-check + lint + production build
```

The live suite asserts a completed analysis, a grounded audit at 100% support,
a non-empty script, and a playable WAV for each document:

- Labour Ministry gazette on EPF inspection charges
- DPIIT BHAVYA scheme guidelines
- Ministry of Textiles Tex-RAMPS SOP

## Project layout

```
backend/app/
  agent/            LangGraph state, graph, nodes (parse, extract, audit, simplify, voice)
  api/v1/           analyze, results, verify, sources
  core/             settings
  prompts/          extraction and vernacular prompts
  services/         parser, chunker, vectorstore, llm, audit, vernacular, tts,
                    eligibility, sources
  schemas.py        Pydantic API contracts
backend/tests/      offline unit/API tests + live E2E module
frontend/           Next.js App Router UI
docs/plan.md        phase blueprint
docs/progress.md    checklist and verification log
```

## Limitations

- The in-memory task store is process-local; restarting the backend loses task
  state (parsed documents and audio remain on disk).
- Eligibility matching only understands rule shapes it can parse deterministically
  (income limits, occupation targeting, state residency, explicit exclusions,
  document lists). Unparsed rules are ignored rather than guessed.
- PIB's public RSS feed currently returns Hindi releases regardless of the language
  parameter; titles are shown as published.
- The myScheme catalogue endpoint is undocumented and may move; override
  `MYSCHEME_API_URL` if it does.
- Niti is not legal advice. The UI always links back to the source document and
  tells the citizen to confirm with the issuing office.
