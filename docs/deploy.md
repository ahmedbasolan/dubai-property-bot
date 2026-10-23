# Deploying the live demo (Vercel)

One Vercel project runs both halves through [Services](https://vercel.com/docs/services)
(`vercel.json`):

| Service | Root | Serves |
|---------|------|--------|
| `web` | `frontend/` | Next.js app, every path except `/api/*` |
| `api` | repo root | FastAPI (`api/vercel_entry.py`), `/api/*` |

The frontend calls its own origin in production builds, so no API URL or CORS
setting is needed.

## Before the first deploy

1. **Decide on the data licence.** The deployment ships the built database
   (`data/dubai_properties.duckdb`) and vector store (`chroma_db/`), so the
   public API serves DLD-derived sales and rents. Dubai and UAE agencies
   generally allow reuse with attribution (the app credits DLD on every page
   and in chat answers), but DLD's own final licence wasn't found; see the open
   question in `docs/plans/2026-10-23-real-dld-data.md`.
2. **Build the data locally**: `make setup` (needs the exports in `data/raw/dld/`).
   The database and vector store are gitignored, which is why the deploy goes
   through the CLI from this folder rather than from a Git push.
3. **Remove `NEXT_PUBLIC_GROQ_API_KEY` from `frontend/.env.local`.** Nothing
   uses it, and any `NEXT_PUBLIC_*` value is compiled into the browser bundle.
   `.vercelignore` keeps `.env*` files out of the upload, but the line is a
   trap for a future build.

## Deploy

```bash
npm i -g vercel
vercel login
vercel link                 # create or pick the project
vercel deploy               # preview deployment
vercel deploy --prod        # once the preview checks out
```

`.vercelignore` is an allowlist: only `api/`, `src/`, `frontend/`, `data/`
(minus raw exports and intermediates), `chroma_db/`, `requirements.txt` and
`vercel.json` are uploaded. The Vercel CLI does not read `.gitignore`.

## Environment variables (Vercel dashboard → Settings → Environment Variables)

| Variable | Needed | Notes |
|----------|--------|-------|
| `GROQ_API_KEY` | optional | Without a server key the chatbot answers from the data and invites visitors to add their own key. Leave it unset until the eval baseline finishes: it shares the free tier's daily quota. |
| `CHAT_RATE_LIMIT_PER_MIN` | optional | Per-IP chat limit (default 20). |
| `BAYUT_API_KEY` | optional | Live listings toggle. |

## How the API runs on a read-only filesystem

Vercel Functions can only write under `/tmp`. `api/vercel_entry.py` copies
`chroma_db/` there and points ChromaDB's model cache at `/tmp` before importing
the app; DuckDB opens read-only in place. The first request on a cold instance
also downloads ChromaDB's ONNX embedding model (~80 MB), so expect a slow first
chat answer after idle periods.

## Checklist after a preview deploy

- `/api/health` returns `default_source: "dld"`
- Dashboard, communities, map (29 markers) and trends load
- Chat answers "What rental yield can I expect in JVC?" with 7.39%

## Verified locally / not yet verified

Verified: the API started from a folder holding only the allowlisted files,
through `api/vercel_entry.py`, with no keys; every endpoint returned 200 and
no-key chat answered from the data. `npm run build` succeeds.

Not verified until the first real deploy: Vercel accepting a backend service
rooted at the repo root alongside `frontend/`, how it treats the top-level
`api/` folder in services mode, and the function's bundle size.
