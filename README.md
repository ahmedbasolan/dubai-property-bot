# Dubai Property Investment Assistant

AI-powered investment scoring and Q&A for Dubai real estate. Calculates net yield, flags supply risk, and scores communities on 7 metrics that explain 85% of investment returns.

**Stack:** Next.js 16 + FastAPI + DuckDB + ChromaDB + Groq (LLM) + Bayut API (live listings)

## Architecture

```mermaid
graph TB
    UI[Next.js 16 UI :3000] -->|REST| API[FastAPI :8000]
    API --> Router{Query Router}

    Router -->|Structured Query| DuckDB[(DuckDB<br/>Transactions + Scores)]
    Router -->|Semantic Query| ChromaDB[(ChromaDB<br/>Market Reports)]
    API -.->|Optional live data| Bayut[Bayut API]

    DuckDB --> |Net Yield View| Scores[Investment Scoring Engine]
    Scores --> |7 Metrics| LLM[LLM Generation<br/>Groq / OpenAI / OpenRouter]
    ChromaDB --> |Market Context| LLM

    LLM --> |Answer + Citations| UI

    subgraph "7-Factor Scoring"
        S1[Gross Yield]
        S2[Net Yield]
        S3[Price/sqft]
        S4[Service Charges]
        S5[Supply Pipeline]
        S6[Occupancy]
        S7[Developer Track Record]
    end

    S1 --> Scores
    S2 --> Scores
    S3 --> Scores
    S4 --> Scores
    S5 --> Scores
    S6 --> Scores
    S7 --> Scores
```

## Quick Start

```bash
# Clone
git clone https://github.com/ahmedbasolan/dubai-property-bot.git
cd dubai-property-bot

# Setup (generate data + load DuckDB + ingest ChromaDB)
make setup

# Configure keys
cp .env.example .env
# Edit .env — add at least one of:
#   GROQ_API_KEY (free: console.groq.com/keys) — recommended
#   OPENAI_API_KEY / OPENROUTER_API_KEY
# Optional: BAYUT_API_KEY for live listings (RapidAPI)

# Terminal 1 — backend (FastAPI)
make run-api        # http://localhost:8000  (docs at /docs)

# Terminal 2 — frontend (Next.js)
make run-ui         # http://localhost:3000
```

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Dashboard: KPIs, community scores, yield distribution |
| `/communities` | 7-factor scores with INVEST / HOLD / AVOID signals |
| `/properties` | Filterable property list (live Bayut data when configured) |
| `/compare` | Side-by-side community comparison |
| `/map` | Leaflet map of communities (dark theme) |
| `/trends` | Price/sqft trends, top gainers, volume |
| `/calculator` | Mortgage + STR yield calculators |
| `/chat` | RAG chat advisor (markdown answers with tables) |

Brand assets: `/brand/brand-book.html`, `/brand/luxury-gold.html`, `/brand/showcase.html`

## What It Does

**Investment Scoring** — Every community gets a composite score (0-100) based on:

| Metric | Weight | What It Measures |
|--------|--------|------------------|
| Gross Yield | 25% | Rental income relative to price |
| Net Yield | 25% | After service charges, management, vacancy |
| Price/sqft | 20% | Below average = undervalued |
| Service Charges | 15% | Lower = better net returns |
| Supply Pipeline | 15% | New units incoming = risk |

**Recommendations:** INVEST / HOLD / AVOID based on metric thresholds.

**Net Yield Calculation:**
```
Net Yield = (Annual Rent - Service Charges - Management Fees - Vacancy Loss) / Price × 100
```
- Service Charges = size × service_charge_per_sqft
- Management Fees = 8% of annual rent
- Vacancy Loss = 5% of annual rent (~2-3 weeks/year)

## Data

- **73 DLD transactions** across 24 Dubai communities (DuckDB)
- **28 market report chunks** in ChromaDB (semantic retrieval)
- **Views:** `v_net_yield` (deterministic yield), `v_investment_scores` (7-factor → INVEST/HOLD/AVOID)
- **Bayut API** optional: live listings, sale prices, community objects
- **7 fields:** floor level, view type, service charges, parking, completion year, furnishing, amenities

## Example Questions

- "Which community has the best ROI for 1BR under 1.5M?"
- "Compare net yield between Dubai Marina and JVC"
- "What's the supply risk in DAMAC Hills 2?"
- "Is Downtown Dubai a good investment right now?"
- "Recommend top 3 communities for a first-time investor with AED 1M budget"

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | Next.js 16, React 19, Tailwind 4, shadcn/ui | Dashboard, chat, charts, map |
| Charts / Map | Recharts, Leaflet (react-leaflet) | Trends, scores, community map |
| Backend | FastAPI (Python) | REST API + RAG orchestration |
| Structured Analytics | DuckDB | Transaction queries, net yield, scoring |
| Semantic Search | ChromaDB | Market report retrieval |
| Embeddings | all-MiniLM-L6-v2 | Report chunk embedding |
| LLM | Groq `gpt-oss-120b` (default), OpenAI, OpenRouter | Answer generation |
| Live Data | Bayut API (RapidAPI) | Listings, sale prices |
| Design | Custom Luxury Gold design system | Brand book, logos, banners |
| Container | Docker (optional) | Deployment |

## API

Interactive docs: `http://localhost:8000/docs`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Service + data source status |
| `/api/chat?q=...` | GET | RAG answer (markdown) |
| `/api/communities` | GET | Scores + recommendations |
| `/api/transactions` | GET | Transactions (`use_live=true` for Bayut) |
| `/api/scores` | GET | Investment scores |
| `/api/trends` | GET | Price/sqft time series |
| `/api/trends/top-gainers` | GET | Top gaining communities |
| `/api/trends/top-volume` | GET | Highest volume communities |
| `/api/mortgage?property_price=...` | GET | Mortgage + acquisition cost |
| `/api/developers` | GET | Developer scorecards |
| `/api/map` | GET | GeoJSON for Leaflet |

## Running Evaluations

```bash
make eval
```

**30-question suite** with automated checks:
- Keyword matching (answer relevance)
- Number accuracy (validate claims against DuckDB ranges)
- Community attribution (entity names must exist in DB, alias-normalized)

Latest results (real LLM — Groq gpt-oss-120b), partial run blocked by free-tier daily quota:

| Metric | Result |
|--------|--------|
| Successful | 8 / 30 (22 skipped — Groq 200k TPD exhausted) |
| Avg keyword score | 41% (on successful) |
| Number accuracy | **100%** |
| Community attribution | **100%** |

The runner loads `.env` automatically and **resumes**: re-run `make eval` after the daily quota resets to fill in the remaining questions without redoing successes. TPM 429s retry with exponential backoff; TPD exhaustion fails fast with a clear message.

## Project Structure

```
dubai-property-bot/
├── api/
│   └── main.py            # FastAPI app (REST + RAG endpoints)
├── src/
│   ├── rag.py             # RAG pipeline (DuckDB + ChromaDB + LLM)
│   ├── bayut_provider.py  # Bayut API client (live data)
│   ├── data_provider.py   # Data provider abstraction
│   ├── db_setup.py        # DuckDB schema + views + scoring
│   ├── ingest.py          # ChromaDB ingestion
│   ├── calculators.py     # Mortgage, STR yield
│   ├── price_trends.py    # Trend series
│   ├── developer_scorecard.py
│   └── generate_data.py   # Mock data generator
├── frontend/              # Next.js 16 app
│   └── src/app/           # dashboard, chat, communities, map, ...
│   └── public/brand/      # brand book, logos, banners
├── eval/
│   ├── eval_set.json      # 30 evaluation questions
│   ├── run_eval.py        # Evaluation runner (loads .env)
│   └── eval_results.json  # Latest results
├── data/                  # DuckDB + raw/processed data
├── chroma_db/             # Vector store
├── .env.example           # Keys template
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── CASE_STUDY.md
```

## Design

The UI uses a custom **Luxury Gold** design system (`#D4AF37` primary, Cinzel + Josefin Sans typography). See:

- `frontend/public/brand/BRAND-IDENTITY.md` — tokens and voice
- `frontend/public/brand/brand-book.html` — full guidelines
- `frontend/public/brand/luxury-gold.html` — palette exploration
