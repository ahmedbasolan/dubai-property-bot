# Case Study: AI Investment Assistant for Dubai Real Estate

## Problem

DLD registered 38,432 residential unit sales in Q1 2026 alone (from its own open data). Yet investors face a fragmented data landscape:

- **DXB Interact** (free) provides community-level averages but no building granularity, no yield calculations, no service charge data
- **Private platforms** (AED 5,000-50,000/year) offer building-level data but are prohibitively expensive for individual investors
- **Listing portals** show asking prices 8-15% above actual transaction prices
- **Net yield** — the metric that actually determines investment returns — requires manual calculation across 4 data sources

The result: investors make AED 1M+ decisions based on incomplete information.

## Solution

Built a **polyglot RAG system** combining DuckDB (structured analytics) with ChromaDB (semantic search) to answer natural-language investment questions with pre-computed rental yields and 4-factor investment scoring, all from Dubai Land Department registered sales and Ejari rents.

### Architecture

```
Investor Question
    ↓
[Query Router]
    ├── DuckDB: Structured queries (price, yield, filters)
    │   └── v_net_yield view (deterministic calculation)
    │   └── v_investment_scores view (4 weighted factors → INVEST/HOLD/AVOID)
    │
    └── ChromaDB: Semantic search (one generated report per community)
    ↓
[LLM Generation with Citations]
    ↓
Answer citing DLD as the source; "insufficient data" where rents are too few
```

### Why Polyglot Persistence

| Query Type | Right Tool | Why |
|------------|-----------|-----|
| "Which 1BR under 1.5M has best ROI?" | DuckDB | Exact price comparison + sorting |
| "What are the risks of investing in JVC?" | ChromaDB | Semantic matching to risk sections |
| "Calculate net yield for this property" | DuckDB SQL view | Deterministic, never LLM-computed |
| "Is Downtown a good investment?" | Both | Structured scores + market context |

## Key Features

### 1. Rental Yield From Registered Records

```
Gross yield = median Ejari rent per m² ÷ median ready sale price per m²
Net yield   = gross × (1 − 8% management − 5% vacancy)   (before service charges)
```

Both sides come from Dubai Land Department records: registered apartment sales and
Ejari rent contracts. Ejari rows carry no bedroom count, so rent and price are
matched per square metre. A community needs at least 30 contracts; below that it
shows "insufficient data", never an estimate. Implemented as DuckDB views:
deterministic, auditable, never computed by the LLM.

### 2. 4-Factor Investment Scoring

Every factor is something the data supports. Occupancy, service charges and
developer track record were dropped because DLD doesn't publish them.

| Factor | Weight | Grade Thresholds |
|--------|--------|-----------------|
| Rental yield | 40 | A: ≥7.5%, B: ≥6.5%, C: ≥5.5%, D: ≥4.5%, F: <4.5% |
| Supply pressure (off-plan ÷ ready sales) | 25 | A: ≤0.25, B: ≤0.75, C: ≤1.5, D: ≤3, F: >3 |
| Price momentum (same projects, Q1→Q3) | 20 | A: ≥+2%, B: ≥−2%, C: ≥−5%, D: ≥−8%, F: <−8% |
| Liquidity (ready sales) | 15 | A: ≥1,000, B: ≥700, C: ≥500, D: ≥350, F: <350 |

Composite: INVEST ≥ 70, HOLD ≥ 50, AVOID < 50, from one rule set so the number and
the signal can't disagree. No yield, no score.

### 3. Supply Pressure From Off-Plan Sales

Off-plan apartments sold this year are stock still to be handed over, so off-plan
sales per ready sale is a forward pipeline measured from registrations, not from
developer announcements. DLD's projects export adds the units actually handed over
in 2026 (79,191 apartments).

### 4. Same-Project Price Momentum

Community median prices move with which buildings happened to sell. Comparing the
same projects in Q1 and Q3 removes that mix effect (details below).

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | Next.js 16, React 19, Tailwind 4, shadcn/ui | Dashboard, chat, charts, map |
| Charts / Map | Recharts, Leaflet | Trends, scores, community map |
| Backend | FastAPI (Python) | REST API + RAG orchestration |
| Structured Analytics | DuckDB | Transaction queries, net yield, scoring |
| Semantic Search | ChromaDB | Market report retrieval |
| Embeddings | all-MiniLM-L6-v2 | Report chunk embedding |
| LLM | Groq gpt-oss-120b (default), OpenAI, OpenRouter | Answer generation |
| Data | Dubai Land Department open data | Registered sales, Ejari rents, projects |
| Live Listings | Bayut API (optional) | Asking prices |
| Design | Luxury Gold design system | Brand book, logos, banners |
| Container | Docker | Deployment |

## Data Model

Source: Dubai Land Department open-data gateway, exported by hand (each search
needs a captcha) and loaded by `src/dld_loader.py`. January–September 2026, the
only window the gateway serves.

| Table | Rows | Notes |
|-------|------|-------|
| Sales | 104,187 raw → 95,885 clean | Removed 17 duplicates, 7,616 offices/shops/hotel rooms, 669 price outliers (mostly partial transfers) |
| In v1 communities | 47,677 | 29 communities with ≥ 250 ready apartment sales |
| Ejari rents | single-unit residential apartments | Community found via the area map, or via the project's ready sales |
| Projects | 165 | Completed in 2026; 79,191 apartments handed over |

**ChromaDB:** one generated report per community (229 chunks), built from the
same DuckDB views, so semantic retrieval can't contradict the structured numbers.

## Moving From Generated to Real Data

The first version ran on 74 generated transactions. Replacing them with DLD
records changed more than the numbers:

- **The generated data was badly off.** International City's ready apartments sell
  at a median of about AED 650/sqft; the generator said 1,221. JVC is about 1,275
  against a generated 1,461.
- **The export format wasn't what the website showed.** The CSVs use column codes
  (`TRANS_VALUE`, `AREA_EN`), area names come in two styles in one column (community
  names on ready sales, DLD official areas such as "Madinat Al Mataar" on most
  off-plan sales), and rents have no bedroom count. The loader maps columns
  explicitly and fails loudly on a missing one.
- **Raw medians mislead.** Q1→Q3 community medians showed Majan +52% and Dubai
  Marina +10%. Comparing the same projects gives Majan +8.7% and Marina −5.3%, and
  shows most communities softening 4–10% through 2026.
- **Three scoring factors had no real source.** Occupancy, service charges and
  developer grades were replaced by supply pressure, momentum and liquidity.
- **Real data exposed a concurrency bug.** Every API request shared one DuckDB
  connection. With 74 rows queries finished before they could overlap; with 48k,
  two parallel page loads got each other's result rows. Each query now uses its own
  cursor, and a regression test fires concurrent requests (it fails 3/3 without
  the fix).

## Evaluation

> These results were measured on the earlier generated dataset. The eval set is
> being rebuilt for the DLD data.

30-question suite (`eval/run_eval.py`) scored against DuckDB as ground truth:

| Metric | Result (Groq `openai/gpt-oss-120b`) |
|--------|------------------------------------|
| Successful answers | 29 / 30 (the failure was a 413: Groq counts prompt + max_tokens, and the old 4k ceiling made a 6k prompt a 10k request; fixed. Full 120b re-run quota-blocked; Q20 re-verified on 20b and 120b) |
| Avg keyword score | 56% |
| Percentage claims outside dataset range | 0 (earlier reported as "100% number accuracy") |
| Community attribution (entities exist in DB) | **100%** |

The percentage check asserts that a claimed ROI or net yield falls inside that
column's global min–max — a range check, not a per-question accuracy measure. A
fabricated figure passes if the real column spans it. Community attribution at
100% means every named community exists in the DB (alias-normalized, e.g. `JVC` ↔
`JVC (Jumeirah Village Circle)`). The harness itself is covered by 14 tests
(`pytest eval/test_run_eval.py`).

### Two defects the eval surfaced

**Retrieval starvation.** Context was built with `ORDER BY net_yield_pct DESC LIMIT 15`, which exposed only 5 of 24 communities and **zero** villas. On a villa question the model answered *"No villa listings are present in the provided data"* — factually wrong; the database held 9. It was reasoning correctly about an impoverished context.

The fix samples the top 2 per `community + property_type`, ranks scarce groups first so a single penthouse is never truncated, and caps at 40 rows. Coverage went from 5/24 communities and 1/3 property types to 20/24 and 3/3. Four factually wrong answers became correct, and 26 of 30 questions improved with **zero regressions**.

**A measurement bug, not a model error.** Number accuracy initially read 93% after the fix. Both failures were false positives in the checker: a supply-pipeline percentage (`15.9%`) was flagged as an out-of-range ROI because the regex crossed sentence boundaries, and a net yield was validated against the ROI range instead of the net-yield range. The checker now confines matches to a single clause and validates each metric against its own range. Real accuracy is 100%.

Both matter for interpretation: the 100% figures describe what the model did with the context it was given, not that the pipeline was sound. The coverage manifest — exact counts by property type, developer, handover status and bedrooms, plus an instruction not to total the sample rows — exists so the model can distinguish "does not exist in the data" from "was not in the rows shown", and so a reader of the answer can tell the difference.

### Deterministic filter extraction

`filters` was a parameter no caller ever populated, so every query ran unfiltered. `src/filters.py` now derives constraints from the query text with no LLM call, for the same reason financial figures come from SQL views rather than generation. It resolves community aliases to exact column values (`JVC`, `downtown`, `DSO`, `marina` → `'JVC (Jumeirah Village Circle)'` and so on), plus property type, bedrooms and price bounds.

The design assumption is that **a wrong filter is worse than no filter**, because a filter that removes rows is indistinguishable from a property that does not exist. So:

- Comparison questions, bare numbers, percentages and prices with no directional wording are left unfiltered, and every omission is recorded and shown to the model.
- A filter matching zero rows is retried unfiltered and the relaxation is reported.
- `community` and `property_type` match with `ILIKE` — the columns hold `'Business Bay'` and `'Villa'`, so `= 'villa'` would match nothing and manufacture a "no data" answer.
- Community filters also scope the investment-score and supply tables, and scope the semantic branch to that community's own market report. Unscoped, a DAMAC Hills 2 question was once answered from the *Dubai Hills* report. Now every v1 community has a generated report, and communities the data doesn't cover (DAMAC Hills 2, villa-only areas) are reported as not covered instead of being matched to a similar name.

Across the 30-question suite 17 questions are now filtered, none of the extracted filters match zero rows, and average context is 21 transactions rather than a fixed 15.

## What This Proves

1. **Polyglot Persistence** — Right tool for the right query type (DuckDB for analytics, ChromaDB for semantic)
2. **Domain-Specific AI** — Net yield calculation, investment scoring, supply risk flagging
3. **Data Engineering** — Real government data: manual exports, explicit column maps, counted cleaning rules, and a community mapping across two naming systems
4. **Production Thinking** — FastAPI + Next.js split, health checks, multi-provider LLM with retry, Docker path
5. **Business Understanding** — domain metrics (yield per m², off-plan supply pressure, mix-adjusted momentum) rather than "RAG over data"
6. **Full-Stack Delivery** — Designed brand system (Luxury Gold), 8-page app, eval loop with automated checks

## Market Context

- UAE PropTech market: $678M in 2025, projected $1.6B by 2032
- 189 PropTech companies in UAE (3x from two years ago)
- Gap: No free tool automates net yield calculation with supply pipeline risk
- This project fills that gap at the prototype level

## Future Enhancements

1. **More rent data and earlier years**: a full month of Ejari contracts for every community's yield, and 2025 from data.dubai for year-on-year trends
2. **Price predictor** (ML model trained on same data) — Project 2
3. **Market trend dashboard** (time series visualization) — Project 3 ✅ shipped (`/trends`)
4. **Multi-turn conversation** with portfolio tracking
5. **Stress test calculator** (what-if scenarios for price decline, vacancy, rent reduction)
