# Plan: replace synthetic data with real DLD data

**Status:** research done, not started · **Branch:** `feat/real-dld-data` · **Date:** 2026-10-23

## Progress

- [x] Exports: transactions ✅, projects (2026 handovers) ✅, **rents ⏳**
  (gateway export returned 401/500 on 2026-10-23; retry with a fresh
  captcha, or split into quarters).
- [x] v1 scope: apartments only, 29 communities (`data/reference/community_map.csv`).
- [x] Task 1, loader for sales + projects: `src/dld_loader.py`, run with
  `python src/dld_loader.py`. Tests in `tests/test_dld_loader.py` (10 on
  fixtures, 4 on the real export that skip when it's absent).
  Current output: 104,187 raw → **95,885 clean sales** (17 duplicates,
  7,616 non-apartments, 669 price outliers: 663 low, mostly partial
  transfers, 6 high, e.g. a AED 100M studio; one plausible AED 32M JBR 4BR is
  among them). 47,677 sales map to a v1 community. 165 projects, 89 linked
  to a community.
- [x] Task 2, partly: `db_setup.py` loads `dld_sales` / `dld_projects`
  beside the generated tables, plus two views on real data:
  `v_dld_price_history` (quarterly median AED/sqft per community, ready vs
  off-plan, ≥ 20 ready sales in every cell) and `v_dld_supply` (units DLD
  registered as completed in 2026, per community). The app still reads the
  generated tables until the switchover. Only 3 quarters exist (Q1–Q3 2026),
  so trends report quarter-on-quarter change, not year-on-year, unless 2025
  data comes from data.dubai.
- [x] Task 6, partly: `data/reference/community_coords.csv` has
  coordinates for all 29 communities, from OpenStreetMap Nominatim. Two were
  hand-picked: Dubai Healthcare City uses Al Jaddaf (Phase 2's location, not
  the Umm Hurair metro station) and Dubai Hills Estate uses Dubai Hills Park
  (the community's centre, not a sales centre at its southern edge). A test
  checks it matches the community map. Wiring it into `api/main.py` /
  `src/app.py` happens at switchover.
- [x] Rents in the loader (`load_rents`) and a yield view (`v_dld_yield`),
  built and tested on a **one-day** export (see rents findings). Need a full
  month of rents for real numbers.
- [x] **Switchover done (2026-10-23).** The app runs entirely on DLD data:
  - `db_setup.py` builds every view from the DLD tables (same view names as
    before).
  - 4-factor scoring: yield 40, supply pressure 25, same-project momentum 20,
    liquidity 15. No yield, no score.
  - API, RAG context and prompt, all frontend pages, search aliases (with
    "not covered" reporting for dropped communities), coordinates, one
    generated report per community (`build_reports.py`), README, case study,
    Makefile (`make setup`) and Docker entrypoint all updated.
  - Old generated data and hand-written reports removed.
  - Found and fixed a thread-safety bug: the shared DuckDB connection mixed up
    concurrent requests' results.
  - 103 tests pass; frontend type-checks and lints clean; dashboard,
    communities, trends, properties (paging), map and chat checked in the
    browser.
- [ ] **Rents: one month (Sep 2026)** to lift yield coverage from 7 to ~29
  communities. Drop it in `data/raw/dld/`, delete the one-day file, run `make setup`.
- [ ] Rebuild the eval set for DLD data (next roadmap step).
- [ ] Legacy Streamlit UI (`src/app.py`, `export.py`, `developer_scorecard.py`,
  `generate_data.py`, `MockDataProvider`) still targets the old schema; decide
  whether to port or delete it.

## Findings from the rents export (2026-10-23)

File: `data/raw/dld/rents-2026-10-22-one-day.csv`, 4,028 contracts, **all
registered on 2026-10-22**. The form said 01/01 → 23/10/2026, so either
the download ran before the dates changed or the export ignored them. Next
try: one month only, Registration Date 01/09/2026 → 30/09/2026 (one day ≈
2,600 flats, so a month is ~50k+ rows; the full 9 months is probably what
made the export fail with a 500).

Column codes: `REGISTRATION_DATE, START_DATE, END_DATE, VERSION_EN,
AREA_EN, CONTRACT_AMOUNT, ANNUAL_AMOUNT, IS_FREE_HOLD_EN, ACTUAL_AREA,
PROP_TYPE_EN, PROP_SUB_TYPE_EN, ROOMS, USAGE_EN, NEAREST_METRO_EN,
NEAREST_MALL_EN, NEAREST_LANDMARK_EN, PARKING, TOTAL_PROPERTIES,
MASTER_PROJECT_EN, PROJECT_EN`.

- **`ROOMS` is empty for every flat.** Yield can't be split by bedroom, so
  it's computed per m²: median annual rent per m² ÷ median ready sale price
  per m², per community. This replaces the per-(community, type,
  bedrooms) bucket design above.
- **Rents use DLD official area names** (99% title case, "Al Barsha South
  Fourth"), so the community map alone matches only ~10% of flats. The
  loader falls back to `PROJECT_EN` → the community of that project's ready
  sales, which works here (unlike sales) because rents and ready sales share
  project names. One day: 260 by area, 633 by project, out of 2,491 clean.
  Only 41% of rent rows have a project name.
- Multi-unit contracts: each unit row repeats the contract total
  (`TOTAL_PROPERTIES` 19 on 19 rows). Kept only `TOTAL_PROPERTIES = 1`.
- "Studio " (trailing space) is its own sub-type next to "Flat". Both kept.
- New vs renewed is about 50/50. Renewals lag the market under the RERA cap,
  so `v_dld_yield` reports both and treats new-contract yield as the market
  figure. A yield needs ≥ 30 contracts and ≥ 30 ready sales, else NULL.
- Provisional yields from the single day (new contracts): JVC 7.55%,
  Business Bay 6.56%, Downtown 6.15%, Creek Harbour 4.98%. Plausible for
  Dubai, but only 4 communities clear the sample minimum.

Early read of real vs generated: International City's ready apartments sell
at a median of ~AED 600–700/sqft (Q1–Q3 2026); the generated data said
1,221. JVC is 1,226–1,358 against a generated 1,461.

Loader finding: **no project has sales under both naming styles**, so the
"inherit community from the project's ready sales" rule matches nothing and
was dropped. The ~45k unmapped sales are off-plan in master developments
outside v1 (Madinat Al Mataar, Palm Deira, Al Khairan First, …).

## Goal

Swap the 74 generated transactions (and the generated communities, supply and
price-history tables) for real Dubai Land Department records, so every number
the app shows or the LLM cites traces back to a registered transaction or
Ejari contract. Done means: `make setup` builds DuckDB from DLD exports, scores
are computed from real sales and rents, and anything DLD does not publish is
either dropped or clearly labelled as an assumption.

## Where the data comes from

| Source | What it has | Access | Use it for |
|---|---|---|---|
| **DLD open-data gateway**, [dubailand.gov.ae/en/open-data/real-estate-data](https://dubailand.gov.ae/en/open-data/real-estate-data/) | Tabs: Transactions, Rents, Project, Valuations, Land, Building, Unit, Broker, Developer. Each has filters and a **Download as CSV** link | Free, but **every search needs a captcha**, so exports are manual | Primary source |
| **data.dubai** (replaced Dubai Pulse; old `dubaipulse.gov.ae` dataset URLs now 301 there) | DLD gateway points here for previous years | Portal is new and still marked "under development" | Back-history only, if needed |
| DLD Residential Price Index ([indexes](https://dubailand.gov.ae/en/open-data/indexes-home/)) | Official index series | Free | Cross-check our price trends |

Not used: third-party wrappers (BayutAPI transactions, Apify scrapers, WAQOV).
They repackage the same data, and scrapers would get around DLD's captcha.
The existing `bayut_provider.py` (live asking prices) stays as is. Asking
prices and transacted prices are different things and the UI should say so.

**Licence: still to confirm.** Third-party sites that redistribute this data
list it as CC BY 4.0 / "open data", but read DLD's own Terms and Conditions
(footer of the gateway) before committing any extract. Either way, attribute
"Source: Dubai Land Department open data" in the README, the UI footer and
LLM citations.

## Step 0: manual export (Ahmed, about 20 minutes)

The captcha means a person has to do this. Export into `data/raw/dld/`
(gitignored, see below):

1. **Transactions:** Transaction Type = Sales, Usage = Residential, Property
   Type = Unit, Registration type = All, date range = last 12 full months
   (2025-10-01 → 2026-09-30). If the export truncates, go month by month.
2. **Rents:** Date field = Registration Date, Usage = Residential, Property
   Type = Unit, same 12 months, Version = All.
3. **Project:** done (2026 handovers, see findings). Still to try: Date
   type = End Date, 01/01/2026 → 31/12/2028, Status = Active, for the
   future pipeline.

Filter notes from filling the forms: Rents' "Property Type" is a single
sub-type (Flat, Villa, Studio, Penthouse, …), so leave it at All and rely on
Usage = Residential. Project needs a date range; use Completion Date from
2025-10-01 to 2028-12-31 to cover recent and upcoming handovers.

### Confirmed result-table columns (read from the gateway page, 2026-10-23)

These are the column headers of each tab's results table. The CSV export is
expected to use the same headers. Confirm with the first real file. The
loader keeps one explicit column map per file and fails loudly on a missing
header. It never guesses.

- **Transactions:** Transaction Number, Transaction Date, Transaction Type,
  Transaction sub type, Registration type, Is Free Hold?, Usage, Area,
  Property Type, Property Sub Type, Amount, Transaction Size (sq.m),
  Property Size (sq.m), Room(s), Parking, Nearest Metro, Nearest Mall,
  Nearest Landmark, No. of Buyer, No. of Seller, Master Project, Project
- **Rents:** Registration Date, Start Date, End Date, Version, Area,
  Contract Amount, Annual Amount, Is Free Hold?, Property Size (sq.m),
  Property Type, Property Sub Type, Number of Rooms, Usage, Nearest Metro,
  Nearest Mall, Nearest Landmark, Parking, No of Units, Master Project, Project
- **Project:** Project Number, Project Name, Developer Number, Developer
  Name, Start Date, End Date, Adoption Date, Project Type, Project Value,
  Escrow Account Number, Project Status, Completed (%), Inspection Date,
  Completion Date, Description, Area, Zone Authority, Total Lands, Total
  Buildings, Total Villas, Total Units, Master Project
- **Unit** (later, for existing stock and floor): Unit Number, Property Sub
  Type, Property Size (sq.m), Balcony Area, …, Floor, Room Type, Parking, …,
  Building Name, Master Project, Project Number, Project Name, Area, Zone

What this settles:
- **Rents include Project and Master Project**, so yield buckets can go down
  to project level, not just area.
- **Sales have no developer column.** Get it by joining Project on project
  name (sales don't carry a project number).
- **Project has Total Units, Completed (%), Status and Completion Date**,
  which is enough for a real supply pipeline.
- The gateway's Area filter mixes DLD areas (`A-…` ids, e.g. "AL QUSAIS")
  with community names (`C-…` ids, e.g. "AL FURJAN"). Check which one the
  export's Area column uses before building the community map.

## Findings from the first export (transactions, 2026-10-23)

File: `data/raw/dld/transactions-2026-10-23.csv`, 25.7 MB, UTF-8 with BOM,
104,187 rows.

- **The CSV headers are column codes, not the table's display names:**
  `TRANSACTION_NUMBER, INSTANCE_DATE, GROUP_EN, PROCEDURE_EN, IS_OFFPLAN_EN,
  IS_FREE_HOLD_EN, USAGE_EN, AREA_EN, PROP_TYPE_EN, PROP_SB_TYPE_EN,
  TRANS_VALUE, PROCEDURE_AREA, ACTUAL_AREA, ROOMS_EN, PARKING,
  NEAREST_METRO_EN, NEAREST_MALL_EN, NEAREST_LANDMARK_EN, TOTAL_BUYER,
  TOTAL_SELLER, MASTER_PROJECT_EN, PROJECT_EN`. The loader maps these.
- **The window is 2026-01-01 → 2026-09-30, not the 12 months requested.**
  The gateway only serves the current year ("for previous year data visit
  data.dubai"). Decision: use **Jan–Sep 2026 (9 months)** for both sales and
  rents, so the yield numerator and denominator cover the same period. Add
  Q4 2025 from data.dubai later only if it's worth it.
- **74% of sales are off-plan** (77,159 off-plan vs 27,028 ready). Price
  stats and yields must be split by ready vs off-plan. Rent only exists for
  ready units, so yield should use ready sales.
- **Area names come in two styles in one column.** Most ready sales use
  community names in caps ("JUMEIRAH VILLAGE CIRCLE", "BURJ KHALIFA",
  "DUBAI MARINA"). About 35k mostly off-plan rows use DLD official areas in
  title case ("Madinat Al Mataar", "Jabal Ali First", "Marsa Dubai",
  "Al Hebiah Fifth"). Some names appear in both cases ("BUSINESS BAY" /
  "Business Bay"). The community map must list both styles per community and
  match case-insensitively. 130 distinct values in total.
- **No villas.** Property Type = Unit is almost all flats (96,566 Flat, 4
  Stacked Townhouses). **Decision (2026-10-23): v1 covers apartments only**
  (see "v1 community list").
- **"Residential" still includes non-homes:** Office 3,694, Hotel Apartment
  1,951, Shop 1,200, Hotel Rooms 754. Keep `PROP_SB_TYPE_EN in ('Flat',
  'Stacked Townhouses')`, which leaves 96,570 rows.
- **17 transaction numbers appear twice**, differing only in
  `NEAREST_METRO_EN`. Dedupe on `TRANSACTION_NUMBER`.
- **515 rows under AED 100k**, nearly all ready "Sale" procedures with
  absurd prices (e.g. AED 2,552 for a 44 m² 1BR in Dubai Hills), likely
  share or partial transfers. A flat AED floor is the wrong filter. Drop
  rows below a fraction (say 30%) of their community's median AED/m² and
  log the count.
- `MASTER_PROJECT_EN` is 99.5% empty, so don't use it. `PROJECT_EN` is
  filled for 94% of rows.
- `ROOMS_EN` values: Studio, 1–6 B/R, PENTHOUSE, plus `NA` (3,586) and
  non-residential labels. Parse to an int, with studio = 0.
- `PARKING` holds bay codes ("P-057", "G-01", "EU"), not counts. Treat it as
  "has parking" at most.
- `ACTUAL_AREA` differs from `PROCEDURE_AREA` in 5,750 rows. Use
  `ACTUAL_AREA`.
- Sanity check: median AED/sqft across flats is about 1,727, and the 1st–99th
  percentile range is 531–5,486. That looks plausible for Dubai 2026.

## Findings from the projects export (2026-10-23)

File: `data/raw/dld/projects-2026-10-23.csv`, 70 KB, 165 projects. It was
exported with Date type = Completion Date, 2025-10-01 → 2028-12-31.
Columns: `PROJECT_NUMBER, PROJECT_EN, DEVELOPER_NUMBER, DEVELOPER_EN,
START_DATE, END_DATE, ADOPTION_DATE, PRJ_TYPE_EN, PROJECT_VALUE,
ESCROW_ACCOUNT_NUMBER, PROJECT_STATUS, PERCENT_COMPLETED, INSPECTION_DATE,
COMPLETION_DATE, DESCRIPTION_EN, AREA_EN, ZONE_EN, CNT_LAND, CNT_BUILDING,
CNT_VILLA, CNT_UNIT, MASTER_PROJECT_EN`. `DESCRIPTION_EN` contains line
breaks, so read it with a CSV parser that handles quoted newlines.

- **This is 2026 handovers, not the future pipeline.** `COMPLETION_DATE` is
  the *actual* completion timestamp, and the current-year cap applies again:
  every row completed in 2026 (96 in H1, 69 in H2 to date), and 163 of 165
  are FINISHED. It holds **79,191 units** (plus 10,035 villas) handed over in
  2026. That's a real "recent supply" metric and replaces the synthetic
  `units_completed_last_12_months`.
- **Future pipeline still needs a second export.** Try Project with Date
  type = **End Date** (planned end), 01/01/2026 → 31/12/2028, Status =
  **Active**. If the gateway caps that to 2026 as well, v1 reports "units
  handed over in 2026" and drops "units expected next 24 months".
- **Projects use DLD official area names**, the ones sales use for off-plan
  rows. Linking projects to sales by `PROJECT_EN` (124 of 165 match)
  confirms official area → community pairs: Al Barsha South Fourth → JVC,
  Al Barshaa South Third → Arjan, Al Barsha South Fifth → JVT, Wadi Al
  Safa 3 → Majan, Wadi Al Safa 5 → Dubai Land Residence Complex, Al Hebiah
  Fourth → Sports City, Warsan Fourth → International City, Hadaeq Sheikh
  Mohammed Bin Rashid → Dubai Hills Estate (shared with other communities).
  This is the `PROJECT_EN` rule the community map needs to bring off-plan
  sales into communities: take each project's community from its ready
  sales, never from its area alone.
- **Developer join coverage is low with this file:** only 3,314 of 96,554
  flat sales link to a project here, because it only has projects finished
  in 2026. Developer on sales needs the full project register (the Active
  export above helps, plus anything finished earlier).
- `PERCENT_COMPLETED` has 4 impossible values (3,300 … 17,692). Clamp to
  0–100 or ignore. `END_DATE` is empty for 37 projects and differs from
  `COMPLETION_DATE` for 126 (planned vs actual), which is a usable
  delivery-delay signal later.
- 106 distinct developers.

## Field mapping

What each current column becomes. **Sales** = Transactions export, **Rents** =
Rents export, **Project** = Project export.

| Current column | Real source | Status |
|---|---|---|
| `transaction_id` | Sales: transaction number | ✅ direct |
| `transaction_date` | Sales: transaction date | ✅ direct |
| `community` | Sales: area + master project / project | ⚠️ needs the community map (below) |
| `property_type` | Sales: property sub-type (Flat, Villa, …) | ✅ normalise labels |
| `bedrooms` | Sales: rooms ("Studio", "1 B/R", …) | ✅ parse; missing for some rows |
| `price_aed` | Sales: amount | ✅ direct |
| `size_sqft` | Sales: property / procedure size (sq.m) | ✅ × 10.7639 |
| `handover_status` | Sales: registration type (Ready / Off-plan) | ✅ direct |
| `parking_spots` | Sales: parking | 🟡 present but sparse |
| `developer`, `completion_year` | Project: developer, completion date (join on project) | 🟡 join, partial coverage |
| `roi_pct` | **Not in sales.** Gross yield = median annual rent ÷ median price for the same bucket | 🔁 becomes a derived, bucket-level metric (see model changes) |
| `service_charge_aed_sqft` | Not in these exports. DLD publishes a service-charge index separately (Mollak) | ❓ check it in step 1. If it's not exportable, keep a per-community assumption table, labelled as such |
| `occupancy_rate` | **Not published** | ❌ drop the factor |
| `floor_level`, `view_type`, `furnishing`, `amenities` | **Not published** | ❌ drop from schema, API, UI |
| `price_history.*` | Aggregate quarterly from Sales | ✅ derived, `source = 'dld'` |
| `supply_pipeline.*` | Project: status, completion date, units | 🟡 derive "units completing next 24 months"; existing stock from Unit/Building tabs, if exports allow |
| market reports (`data/raw/market_report_*.md`) | Hand-written, describe Q1 2024 | 🔁 regenerate per community from DuckDB (templated, numbers come from queries) |

## Model changes this forces

1. **Yield moves from the transaction to the bucket.** A sale has no rent,
   so per-transaction `roi_pct` goes away. Compute gross yield per
   *(community, property type, bedrooms)* over the trailing 12 months as
   `median(annual rent) / median(sale price)`. Require at least 10 sales and
   10 rents per bucket, otherwise report "insufficient data" instead of a
   number. `v_net_yield` becomes a bucket-level view.
2. **Scoring loses two of its seven factors.** Occupancy and the hard-coded
   developer grades have no real source. Re-weight the remaining factors
   (gross yield, net yield, supply, service charge, plus price/sqft, which
   can now be weighted because price and size are real). Update the "7
   metrics" claim in the README and case study. Add a new real factor only
   if it holds up, e.g. 12-month price momentum from `price_history`.
3. **Thresholds need recalibrating.** The A–F cut-offs (yield ≥ 8.5% → A,
   etc.) were tuned to generated data. Set them from real distributions,
   e.g. quintiles across communities, and write down why.
4. **Scale goes from 74 rows to ~150k+ sales a year.** DuckDB is fine. The
   API's `/transactions` and the properties page need pagination and default
   filters, and the RAG context builder must send aggregates, not raw rows.

## v1 community list (apartments only)

**Rule:** a community is in v1 if it has **≥ 250 ready flat sales** in the
Jan–Sep 2026 export. Ready sales are what yield is computed from, and 250
leaves room to split by bedroom count (e.g. JVC: 1,758 ready 1BR, 767
studios, 462 2BR). Off-plan-only areas (Madinat Al Mataar 11k, Palm Deira
3k, Al Khairan First 2k, …) fail the rule because they have no ready stock
to rent yet. They feed the supply pipeline instead.

The rule gives **29 communities**, mapped in
[`data/reference/community_map.csv`](../../data/reference/community_map.csv)
(31 rows: International City and Meydan each span two `AREA_EN` values).
Every map row matches the export, and together they cover **20,760 of
23,973 ready flat sales (87%)**.

| Change | Communities |
|---|---|
| **Kept (16)** | JVC, Business Bay, Dubai Marina, Downtown Dubai, Dubai Creek Harbour, International City, Discovery Gardens, Sports City, Dubai Silicon Oasis, JLT, Meydan, Dubai Hills Estate, Dubai South, Al Furjan, Palm Jumeirah, Town Square |
| **Added (13)** | Arjan (875 ready), Sobha Hartland (705), Majan (648), Dubai Production City (551), Dubai Land Residence Complex (437), Motor City (408), Liwan (339), DAMAC Hills (311), The Greens (298), Dubai Healthcare City (296), JVT (292), JBR (289), Dubai Studio City (285) |
| **Dropped: villa-only (4)** | Arabian Ranches, The Springs, Tilal Al Ghaf, DAMAC Hills 2 |
| **Dropped: too few ready flat sales (4)** | Bluewaters (58), Al Barsha (27), Deira (0 under that name), Bur Dubai (0) |

Matching: `upper(AREA_EN) = area_en`. Only community-name `AREA_EN` values
are mapped. Official-area values (Marsa Dubai, Hadaeq Sheikh Mohammed Bin
Rashid, Al Thanyah Fifth, Madinat Al Mataar, …) are mostly off-plan and span
several communities, so they stay under their own names. Mapping them by
`PROJECT_EN` is a later refinement. Unmapped areas keep their own name, so
totals still reconcile. The loader test asserts that every map row matches
at least one export row.

**Hard-coded old community lists to update** (all keyed on the old 24
names): coordinates in `api/main.py` (~line 330) and `src/app.py` (~line
453), aliases in `src/filters.py` + `tests/test_filters.py`, Bayut location
ids in `src/bayut_provider.py`, the known-community list in
`eval/run_eval.py`, and the per-community short-term-rental assumptions
(ADR, occupancy) in `src/calculators.py`. The STR figures aren't DLD data:
keep them as labelled assumptions for the communities that have them, and
let the calculator use the Ejari median for long-term rent.

## Implementation tasks (in order)

1. **Loader:** `src/dld_loader.py` reads `data/raw/dld/*.csv` with an
   explicit column map per file, normalises units and labels, applies the
   community map, and writes `data/processed/dld_sales.parquet` and
   `dld_rents.parquet`. Reject or flag rows with missing price or size,
   zero-AED transfers and extreme price/sqft outliers. Log counts for each
   rule.
2. **Schema and views:** `src/db_setup.py` gets new `sales`, `rents` and
   `projects` tables, then rebuilds `v_net_yield` (bucket level),
   `v_community_summary` and `v_investment_scores` on top of them.
3. **Provider:** implement the existing `DLDInteractProvider` stub in
   `src/data_provider.py` against DuckDB, and make it the default.
   `MockDataProvider` stays available for tests and offline demos.
4. **Makefile:** add `make dld` (loader → DuckDB → reports → Chroma). Keep
   `make setup-mock` for the generated data.
5. **Market reports:** `src/build_reports.py` renders one markdown report
   per community from DuckDB queries, then ingests into ChromaDB.
6. **API and frontend:** remove the dropped fields from `api/main.py` and
   `frontend/src/lib/api.ts` and the pages that show them (`properties`,
   `compare`, `communities`, `/`). Add pagination. Add a "Source: DLD, data
   to <date>" footer.
7. **Tests:** rewrite `tests/test_data_quality.py` for real data (map
   coverage, bucket minimums, plausible price/sqft range, sales count
   reconciles with the export). Fix fixtures in `tests/test_api.py` that
   use `TRX-` ids.
8. **Docs:** README, CASE_STUDY and the in-app disclaimer drop "synthetic"
   and state the data window, the filters and the yield method.

The eval set (`eval/eval_set.json`) is tuned to the generated data, so it
gets rebuilt in the next step (eval overhaul), not patched here. Keep the
old results as a record, not as a baseline.

## Data in git

- `data/raw/dld/` gets added to `.gitignore`. Full exports are large and the
  terms aren't confirmed yet.
- Commit a small sample (e.g. one month, a few communities) under
  `data/sample/dld/`, so CI and anyone cloning can run `make dld SAMPLE=1`
  without exporting anything.
- Delete `src/generate_data.py`'s outputs from `data/raw/`, keep the script
  for the mock provider.

## Open questions to settle in step 0 or 1

- ~~Whether CSV headers match the result tables~~: they don't, they're
  column codes (see findings). Row cap: none seen, 104k rows came back in
  one export.
- Whether the Rents export is also limited to 2026, and what its column
  codes are.
- Villas: are they in the Building / Land exports, or does v1 drop villa
  communities?
- Whether the service-charge index is exportable.
- DLD terms for redistributing an extract (decides whether the sample can be
  committed).

## Done when

- `make dld` builds everything from real exports, and `make dld SAMPLE=1`
  works on a fresh clone.
- No column in the API or UI is generated data. Any remaining assumption
  (e.g. service charge) is labelled in the UI and in LLM answers.
- Tests pass on the sample and on the full export.
- README and case study describe the real data window and methods.
