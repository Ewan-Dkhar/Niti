# Niti frontend

Next.js 14 App Router + Tailwind portal for the Niti policy explainer.

## Run locally

Use Node 22 LTS:

```bash
source ~/.nvm/nvm.sh
nvm use 22
npm install
cp .env.example .env.local   # only if the API is not on localhost:8000
npm run dev
```

The backend should be running at `http://localhost:8000`:

```bash
cd ..
uv run uvicorn app.main:app --reload --app-dir backend
```

Open `http://localhost:3000`.

## What the page does

- **Document intake** posts a public PDF URL and a language to `/api/v1/analyze`.
- The page polls `/api/v1/results/{task_id}` every 1.5s until the pipeline finishes.
- The result sheet shows the grounding verdict, the plain-language script, a
  waveform player for `/media/<task>.wav`, the cited rights sheet, and an
  eligibility checker that calls `/api/v1/verify-citizen`.
- The live-sources section reads `/api/v1/sources` (myScheme + PIB RSS).
- Citation chips open a source drawer with the extracted statement, its page and
  clause, and a link back to the original document.

## Design notes

The visual language borrows from a government noticeboard: ruled paper, a dark
teal seal, a red review stamp, and a serif masthead. Fraunces carries the
headlines, IBM Plex Sans the body, IBM Plex Mono the citations; Noto Sans
Devanagari/Tamil/Bengali/Telugu keep Indian-language scripts readable.

The one deliberate flourish is the rotated stamp that appears while a document
is being read and again as the eligibility verdict. Everything else stays flat,
ruled, and quiet.

## Scripts

```bash
npm run dev     # development server
npm run build   # production build (also type-checks and lints)
npm run start   # serve the production build
npm run lint    # eslint
```

`next.config.mjs` sets `output: "standalone"` for the Docker image, which also
copies `.next/static` and `public/` into the runner stage. Next 14 prints a
harmless warning when you use `npm run start` with that setting; serving the
standalone build directly (`node .next/standalone/server.js`) is the deployment
path used by `frontend/Dockerfile`.
