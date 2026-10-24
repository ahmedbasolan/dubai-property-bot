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
vercel link                                   # create or pick the project
python scripts/vendor_onnx_model.py           # bundle the embedding model (see below)
vercel env add VERCEL_SUPPORT_LARGE_FUNCTIONS # value 1, for production and preview
vercel deploy                                 # preview deployment
vercel deploy --prod                          # once the preview checks out
```

**The project's very first deployment goes to production**, even without
`--prod`, and on the Hobby plan the production domain
(`<project>.vercel.app`) is public. Only later `vercel deploy` runs are
protected previews. So make the licence decision before the first deploy.

`.vercelignore` is an allowlist: only `api/`, `src/`, `frontend/`, `data/`
(minus raw exports and intermediates), `chroma_db/`, `vendor/`,
`requirements.txt` and `vercel.json` are uploaded. The Vercel CLI does not
read `.gitignore`.

Don't connect the GitHub repository (`vercel git connect`): a push would build
without the gitignored database, vector store and model, and break the site.

## Environment variables (Vercel dashboard → Settings → Environment Variables)

| Variable | Needed | Notes |
|----------|--------|-------|
| `VERCEL_SUPPORT_LARGE_FUNCTIONS` | **yes**, `1` | The API bundle is ~514 MB, over Python's 500 MB standard limit. |
| `GROQ_API_KEY` | optional | Without a server key the chatbot answers from the data and invites visitors to add their own key. Leave it unset until the eval baseline finishes: it shares the free tier's daily quota. |
| `CHAT_RATE_LIMIT_PER_MIN` | optional | Per-IP chat limit (default 20). |
| `BAYUT_API_KEY` | optional | Live listings toggle. |

## How the API runs on a read-only filesystem

Vercel Functions can only write under `/tmp`, and on a cold start Vercel
installs the Python dependencies there (`/tmp/_vc_deps`), leaving little room.
`api/vercel_entry.py`:

- copies `chroma_db/` to `/tmp` (ChromaDB opens its store read-write);
- points ChromaDB at the embedding model bundled in `vendor/` by
  `scripts/vendor_onnx_model.py`. Letting ChromaDB download it into `/tmp`
  failed on the first deploy with `No space left on device`.

DuckDB opens read-only in place. A cold-start chat answer took about 4 s.

## Checklist after a deploy

- `/api/health` returns `default_source: "dld"`
- Dashboard, communities, map (29 markers) and trends load
- Chat answers "What rental yield can I expect in JVC?" with 7.39%

Previews are behind Vercel login; test them with `vercel curl <url>/api/health`.

## What the first deploy (2026-10-24) showed

- Services work as configured: a backend rooted at the repo root alongside
  `frontend/`, with the API on `/api/*`.
- Chat failed until the model was bundled (`No space left on device`).
- Bundling the model pushed the function past 500 MB, hence large functions.
- The first deployment went to production and is public (see above). The
  working preview was then promoted with `vercel promote <preview-url>`;
  production is https://dubai-property-bot.vercel.app.
