# Code Review — Dubai Property Investment Assistant

Reviewed at `cf57bf9` ("Extract SQL filters deterministically from natural-language
queries"), 30 commits, working tree clean. Method: read the backend, infra, frontend,
eval harness and data; ran `pytest` (57 then), `eslint`, `tsc`, and exercised the REST
API directly against the local DuckDB file.

Status legend: **Fixed** = addressed on branch `review-fixes`; **Open** = still true.

## Summary

The project demonstrates good judgment about retrieval and failure modes: the
deterministic filter extractor with its "never narrow on a guess" rule, the
retrieval-starvation fix, and the coverage manifest are stronger than most
portfolio RAG projects. It was weaker as a shipped artefact: the Docker path did
not build, two data sources contradicted each other in the same UI, and several
user-visible bugs were one-line fixes.

## Verified defects

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | High | `GET /api/transactions` returned 40 of 73 rows because it reused the LLM's context sample, and reported the sample size as `total`. | Fixed — `list_transactions()` with `LIMIT/OFFSET` and a real `COUNT(*)`; 10 contract tests. |
| 2 | High | `MockDataProvider.get_transactions()` raised `BinderException: Referenced column "net_yield_pct" not found` — it ordered the base table by a view-only column. | Fixed — queries `v_net_yield` joined to `transactions` for `amenities`; columns qualified. |
| 3 | High | `/api/transactions/{id}` returned HTTP 200 with `[{"error": ...}, 404]`. | Fixed — `HTTPException(404)`. |
| 4 | High | Communities page rendered `Price Score A/100` — letter grades typed as numbers. | Fixed — `Grade` type; UI shows the grade. |
| 5 | Medium | Supply-risk colours never applied: DB held `low`/`medium`/`high`, UI compared `LOW`/`MEDIUM`/`HIGH`. | Fixed — upper-cased in the view; regression test. |
| 6 | Medium | Docker build failed on a clean clone: `COPY chroma_db/` but `chroma_db/` is in `.dockerignore`; nothing created the DuckDB file, and `rag.py` opens it read-only at import. | Fixed — `docker-entrypoint.sh` builds both artefacts if missing. |
| 7 | Medium | `docker compose` web service ran `next start` with no build, and `NEXT_PUBLIC_API_URL=http://api:8000` (unresolvable from the browser). | Fixed — `npm run build` first; URL is `http://localhost:8000`. |
| 8 | Medium | The same composite score mapped to different signals: JVC 76 → INVEST, International City 76 → HOLD. | Fixed — recommendation is now a band on the score (INVEST ≥ 70, HOLD ≥ 50), so they cannot disagree. |
| 9 | Medium | Docs described 5 factors at 25/25/20/15/15, the code weighted a different five including occupancy, and `CASE_STUDY` claimed 7. | Fixed — one weight table (gross 25, net 25, supply 20, occupancy 15, service 15) in code, README and case study. |
| 10 | Medium | API keys were sent in the `/api/chat` query string, so they landed in access logs, history and proxies; chat was unauthenticated and unrate-limited. | Partly fixed — POST body, GET deprecated and key-less, per-IP rate limit (`CHAT_RATE_LIMIT_PER_MIN`). No authentication by design. |
| 11 | Low | `/api/str` returned 200 with `{"error": ...}`. | Fixed — `HTTPException(404)`. |
| 12 | Low | Frontend fetches had no error path, leaving a permanent spinner when the API was down. | Fixed on `/`, `/communities`, `/properties`. |
| 13 | Low | `handover_status` compared `"READY"` against `"Ready"`, so every badge rendered secondary. | Fixed — case-insensitive. |
| 14 | Low | `HealthResponse` claimed the app was on live Bayut data while all analytics endpoints read DuckDB. | Fixed — `default_source: "mock"` alongside `data_source`. |
| 15 | Low | `Makefile` used the Windows-only `py` launcher, contradicting the Linux/Docker instructions. | Fixed — `PY ?= python`. |

## Data integrity (the most important finding)

**Fixed on this branch.** At review time the app showed two different markets at once:

- `src/price_trends.py` was 140 lines of hardcoded 2022–Q1 2024 figures served by
  `/trends` as observed history. `src/developer_scorecard.py` hardcoded on-time
  delivery, appreciation, unit counts and RERA compliance with no source.
- They contradicted DuckDB: Downtown was **6,246 AED/sqft** in the scores and **2,600**
  on `/trends`; Marina was **1,450** vs **2,050**.
- `generate_data.py` drew `price` and `size_sqft` independently, so price/sqft spanned
  **612–11,452 AED/sqft**.

What changed:

- Size is now derived from price through the community's implied AED/sqft density
  (midpoint price / midpoint size, ±12%, with a bedroom premium). Correlation between
  price and size went from **0.51 to 0.96**, and price/sqft from 612–11,452 to
  **1,046–2,615** with no community spread wider than 2×.
- A new `price_history` table (12 quarters per community, in DuckDB) replaces the
  hardcoded trends. Its latest quarter is the sample's own average, computed the same
  way as `v_community_summary`, so `/trends` and `/api/scores` cannot disagree.
  Earlier quarters are modelled and the volume is stock-turnover based; both the API
  (`source`, `basis`) and the page say so.
- Developer scorecards are now a transaction-weighted aggregation of
  `v_investment_scores`. The unsourced delivery, appreciation, unit-count and RERA
  fields are gone rather than relabelled.
- Each community still has only **2–5 transactions**; averages of that size remain
  weak evidence, and this is still documented in the README.

`tests/test_data_quality.py` pins the correlation, the AED/sqft band, per-community
density stability, the trend/scores anchor, and that a developer's score stays inside
its communities' range.

## Evaluation claims

**Partly fixed.** `eval/run_eval.py` marks a percentage "accurate" when it falls
inside the column's global min–max (ROI 4.9–10.3%, net yield 2.08–8.25%). A
fabricated 7.0% passes. "100% number accuracy" therefore measures "no out-of-range
figures", not correctness. Keyword matching averages 56%, and 29/30 includes a
quota error. README and case study now state the metric for what it is. The results
file was produced against the pre-regeneration dataset; the check itself is
range-based and still applies.

## Security

- No secrets committed; `.env` ignored and absent from history. Good.
- Chat spends real credit with no authentication. The rate limit is per-process and
  in-memory, so it resets on restart and does not work across workers. Deploying this
  publicly requires an API gateway or per-user tokens, not just this limiter.
- CORS is now configurable (`CORS_ORIGINS`) instead of hardcoded localhost.
- The container still runs as root; a non-root user conflicts with the bind-mounted
  `./data` and `./chroma_db` volumes on Linux hosts. Left as-is deliberately.

## Still open

1. Replace global-range validation in the eval with per-question expected values, and
   re-run it after the data regeneration (LLM quota permitting).
2. Pin `requirements.txt`; `streamlit`, `pandas`, `openpyxl` and `reportlab` are only
   needed by the legacy Streamlit UI and the export script.
3. Frontend tests and CI (pytest + eslint + `next build`). The API contract and data
   quality tests cover the regressions above but nothing renders a component.
4. `rag.py`'s `health_check()` still probes a `transactions` Chroma collection that
   `ingest.py` never creates.
5. Trends earlier than the latest quarter are modelled, not observed; real DLD history
   would remove the growth-curve assumption.

## What holds up well

- `src/filters.py` — ambiguity handled by refusing to filter, with every omission
  reported to the model and to the UI. Tests assert both directions.
- Sampling scarce `community + property_type` groups first (`rag.py`), and the
  "exact counts, don't total the sample" coverage manifest.
- Prompt discipline: financial figures come from SQL views, never from generation.
- Graceful degradation to a DuckDB-only answer instead of a 500.
- The case study's own caveat that 100% describes the context handed to the model,
  not that the pipeline is sound.
