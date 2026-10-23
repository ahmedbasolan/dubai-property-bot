"""DuckDB setup: load real DLD data and build the analytical views.

Input is the parquet output of `src/dld_loader.py` (DLD open-data sales,
Ejari rents and projects). The views keep the names the API, RAG and UI read
(`transactions`, `v_net_yield`, `v_community_summary`, `v_investment_scores`,
`price_history`, `supply_pipeline`), now computed from registered records.
Method and data window: docs/plans/2026-10-23-real-dld-data.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import duckdb

from config import DB_PATH, MANAGEMENT_FEE_RATE, VACANCY_RATE, PROCESSED_DIR

# Yield compares rents and ready sales within the same projects. A project
# counts when it has this many new-contract rents and this many ready sales;
# a community needs this many such projects and matched rents, else its
# yield is reported as insufficient data rather than a number.
MIN_PROJECT_RENTS = 5
MIN_PROJECT_SALES = 5
MIN_YIELD_PROJECTS = 3
MIN_YIELD_SAMPLE = 30
# Momentum compares the same projects in the first and last quarter; fewer
# paired projects than this and it's reported as unknown.
MIN_MOMENTUM_PROJECTS = 5
MIN_PROJECT_SALES_PER_QUARTER = 3

# Composite weights (sum 100). Price/sqft and 2026 handovers are reported
# but not weighted: yield already prices value against rent, and handovers
# only link for projects in the 2026 projects export.
WEIGHTS = {"yield": 40, "supply": 25, "momentum": 20, "liquidity": 15}

DATA_SOURCE = "Dubai Land Department open data (sales, Ejari rents, projects)"


def init_db():
    """Rebuild the database from the DLD parquet files."""
    missing = [n for n in ("sales", "rents", "projects")
               if not (PROCESSED_DIR / f"dld_{n}.parquet").exists()]
    if missing:
        raise SystemExit(f"Missing DLD data ({', '.join(missing)}): run `python src/dld_loader.py` "
                         "after exporting to data/raw/dld/")

    DB_PATH.unlink(missing_ok=True)  # views and tables changed shape; start clean
    conn = duckdb.connect(str(DB_PATH))
    _load_dld(conn)
    print(f"DuckDB initialized: {DB_PATH}")
    _print_summary(conn)
    conn.close()


def _load_dld(conn):
    for name in ("sales", "rents", "projects"):
        conn.execute(f"CREATE OR REPLACE TABLE dld_{name} AS SELECT * FROM read_parquet(?)",
                     [(PROCESSED_DIR / f"dld_{name}.parquet").as_posix()])

    # Developer comes from the projects export, matched on project name. It
    # only covers projects completed in 2026, so most sales have none.
    conn.execute("""
        CREATE OR REPLACE VIEW transactions AS
        SELECT
            s.transaction_id,
            s.community,
            'Apartment' AS property_type,
            s.bedrooms,
            s.price_aed,
            ROUND(s.size_sqft, 0) AS size_sqft,
            s.size_sqm,
            s.transaction_date,
            CASE WHEN s.is_offplan THEN 'Off-Plan' ELSE 'Ready' END AS handover_status,
            s.project,
            p.developer,
            s.has_parking,
            s.procedure
        FROM dld_sales s
        LEFT JOIN (SELECT upper(project) AS key, any_value(developer) AS developer
                   FROM dld_projects GROUP BY 1) p ON upper(s.project) = p.key
        WHERE s.community IS NOT NULL
    """)

    # Market rent is new contracts only: renewals lag the market under the
    # RERA rent cap. Per project, and per community as a fallback.
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_project_rent AS
        SELECT community, upper(project) AS project_key,
               median(rent_per_sqm) AS rent_per_sqm, COUNT(*) AS new_contracts
        FROM dld_rents
        WHERE community IS NOT NULL AND project IS NOT NULL AND is_new_contract
        GROUP BY ALL
        HAVING COUNT(*) >= {MIN_PROJECT_RENTS}
    """)
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_community_rent AS
        SELECT community,
               COUNT(*) AS rent_contracts,
               COUNT(*) FILTER (WHERE is_new_contract) AS new_contracts,
               CASE WHEN COUNT(*) FILTER (WHERE is_new_contract) >= {MIN_YIELD_SAMPLE}
                    THEN median(rent_per_sqm) FILTER (WHERE is_new_contract) END AS rent_per_sqm
        FROM dld_rents WHERE community IS NOT NULL GROUP BY community
    """)

    # Community yield, like for like: each project's median new rent per m2
    # over its own median ready price per m2, then the median across
    # projects. Pooling all rents against all sales compared different
    # buildings - International City read 11.6% because a third of its
    # rents were one newer tower, against older blocks' sale prices.
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_community_yield AS
        WITH s AS (
            SELECT community, upper(project) AS project_key,
                   median(price_aed / size_sqm) AS price_per_sqm, COUNT(*) AS ready_sales
            FROM transactions
            WHERE handover_status = 'Ready' AND project IS NOT NULL
            GROUP BY ALL
            HAVING COUNT(*) >= {MIN_PROJECT_SALES}
        ),
        pairs AS (
            SELECT r.community, 100 * r.rent_per_sqm / s.price_per_sqm AS yield_pct, r.new_contracts
            FROM v_project_rent r JOIN s USING (community, project_key)
        )
        SELECT community,
               COUNT(*) AS yield_projects,
               SUM(new_contracts) AS matched_contracts,
               CASE WHEN COUNT(*) >= {MIN_YIELD_PROJECTS} AND SUM(new_contracts) >= {MIN_YIELD_SAMPLE}
                    THEN ROUND(median(yield_pct), 2) END AS gross_yield_pct
        FROM pairs GROUP BY community
    """)

    # Per-sale yield estimate: the sale's own project rent per m2 when that
    # project has enough new contracts, else the community's, applied to the
    # unit's size. Net deducts management and vacancy only; DLD publishes no
    # service charges, so net yield is before service charges.
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_net_yield AS
        WITH r AS (
            SELECT t.*, coalesce(pr.rent_per_sqm, cr.rent_per_sqm) AS rent_per_sqm
            FROM transactions t
            LEFT JOIN v_project_rent pr
                   ON pr.community = t.community AND pr.project_key = upper(t.project)
            LEFT JOIN v_community_rent cr ON cr.community = t.community
        )
        SELECT
            r.* EXCLUDE (rent_per_sqm),
            ROUND(r.price_aed / r.size_sqft, 1) AS price_per_sqft,
            ROUND(r.rent_per_sqm * r.size_sqm) AS estimated_annual_rent,
            ROUND(100 * r.rent_per_sqm * r.size_sqm / r.price_aed, 2) AS roi_pct,
            ROUND(100 * r.rent_per_sqm * r.size_sqm * (1 - {MANAGEMENT_FEE_RATE} - {VACANCY_RATE})
                  / r.price_aed, 2) AS net_yield_pct
        FROM r
    """)

    # Quarterly ready-apartment series (what /api/trends reads), plus a
    # segmented one with off-plan for analysis.
    conn.execute("""
        CREATE OR REPLACE VIEW v_dld_price_history AS
        SELECT
            community,
            handover_status AS segment,
            'Q' || quarter(transaction_date) || ' ' || year(transaction_date) AS quarter,
            date_trunc('quarter', transaction_date)::DATE AS quarter_start,
            ROUND(median(price_aed / size_sqft), 0) AS median_price_per_sqft,
            COUNT(*) AS sales_count
        FROM transactions
        GROUP BY ALL
    """)
    conn.execute("""
        CREATE OR REPLACE VIEW price_history AS
        SELECT community, quarter, quarter_start,
               median_price_per_sqft AS avg_price_per_sqft,
               sales_count AS market_volume,
               'dld' AS source
        FROM v_dld_price_history WHERE segment = 'Ready'
    """)

    # Same-project price change, first to last quarter in the data. Raw
    # community medians swing with which buildings happened to sell
    # (Majan +52%, Marina +10%); pairing projects removes that mix effect.
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_price_momentum AS
        WITH bounds AS (
            SELECT date_trunc('quarter', MIN(transaction_date)) AS first_q,
                   date_trunc('quarter', MAX(transaction_date)) AS last_q
            FROM transactions WHERE handover_status = 'Ready'
        ),
        p AS (
            SELECT t.community, t.project, date_trunc('quarter', t.transaction_date) AS q,
                   median(t.price_aed / t.size_sqft) AS ppsf, COUNT(*) AS n
            FROM transactions t
            WHERE t.handover_status = 'Ready' AND t.project IS NOT NULL
            GROUP BY ALL
        ),
        pairs AS (
            SELECT a.community, b.ppsf / a.ppsf - 1 AS change
            FROM p a JOIN p b USING (community, project), bounds
            WHERE a.q = bounds.first_q AND b.q = bounds.last_q
              AND a.n >= {MIN_PROJECT_SALES_PER_QUARTER} AND b.n >= {MIN_PROJECT_SALES_PER_QUARTER}
        )
        SELECT community,
               COUNT(*) AS paired_projects,
               CASE WHEN COUNT(*) >= {MIN_MOMENTUM_PROJECTS}
                    THEN ROUND(100 * median(change), 1) END AS price_momentum_pct
        FROM pairs GROUP BY community
    """)

    # Supply: off-plan sold this year is stock still to be handed over, so
    # off-plan sales per ready sale is the forward pipeline. Handovers are
    # what DLD registered as completed in 2026 (projects export).
    conn.execute("""
        CREATE OR REPLACE VIEW supply_pipeline AS
        WITH s AS (
            SELECT community,
                   COUNT(*) FILTER (WHERE handover_status = 'Off-Plan') AS offplan_sales,
                   COUNT(*) FILTER (WHERE handover_status = 'Ready') AS ready_sales
            FROM transactions GROUP BY community
        ),
        h AS (
            SELECT community, SUM(units) AS units_completed
            FROM dld_projects WHERE community IS NOT NULL AND status = 'FINISHED'
            GROUP BY community
        )
        SELECT
            s.community AS community_name,
            s.offplan_sales,
            s.ready_sales,
            ROUND(s.offplan_sales / s.ready_sales, 2) AS pipeline_ratio,
            coalesce(h.units_completed, 0) AS units_completed_2026,
            CASE WHEN s.offplan_sales / s.ready_sales <= 0.75 THEN 'LOW'
                 WHEN s.offplan_sales / s.ready_sales <= 1.5 THEN 'MEDIUM'
                 ELSE 'HIGH' END AS supply_risk
        FROM s LEFT JOIN h USING (community)
    """)

    conn.execute("""
        CREATE OR REPLACE VIEW v_community_summary AS
        SELECT
            t.community,
            COUNT(*) FILTER (WHERE t.handover_status = 'Ready') AS transaction_count,
            ROUND(median(t.price_aed / t.size_sqft) FILTER (WHERE t.handover_status = 'Ready'), 0)
                AS avg_price_per_sqft,
            ROUND(median(t.price_aed) FILTER (WHERE t.handover_status = 'Ready'), 0) AS avg_price,
            cy.gross_yield_pct AS avg_roi_pct,
            CASE WHEN cy.gross_yield_pct IS NOT NULL
                 THEN 'same-project, new contracts' END AS rent_basis,
            coalesce(cr.rent_contracts, 0) AS rent_contracts,
            coalesce(cy.matched_contracts, 0) AS matched_contracts,
            coalesce(cy.yield_projects, 0) AS yield_projects,
            pm.price_momentum_pct,
            pm.paired_projects,
            sp.offplan_sales,
            sp.pipeline_ratio,
            sp.units_completed_2026,
            sp.supply_risk
        FROM transactions t
        LEFT JOIN v_community_rent cr USING (community)
        LEFT JOIN v_community_yield cy USING (community)
        LEFT JOIN v_price_momentum pm USING (community)
        LEFT JOIN supply_pipeline sp ON sp.community_name = t.community
        GROUP BY t.community, cy.gross_yield_pct, cr.rent_contracts, cy.matched_contracts,
                 cy.yield_projects, pm.price_momentum_pct, pm.paired_projects, sp.offplan_sales,
                 sp.pipeline_ratio, sp.units_completed_2026, sp.supply_risk
    """)

    # Grades: yield bands are absolute (an investor's 7% is 7% anywhere);
    # momentum, supply and liquidity bands were set from the Q1-Q3 2026
    # distribution across the 29 communities (see the plan doc).
    w = WEIGHTS
    conn.execute(f"""
        CREATE OR REPLACE VIEW v_investment_scores AS
        WITH g AS (
            SELECT *,
                ROUND(avg_roi_pct * (1 - {MANAGEMENT_FEE_RATE} - {VACANCY_RATE}), 2) AS avg_net_yield_pct,
                CASE WHEN avg_roi_pct IS NULL THEN NULL
                     WHEN avg_roi_pct >= 7.5 THEN 'A' WHEN avg_roi_pct >= 6.5 THEN 'B'
                     WHEN avg_roi_pct >= 5.5 THEN 'C' WHEN avg_roi_pct >= 4.5 THEN 'D' ELSE 'F' END
                    AS yield_score,
                CASE WHEN pipeline_ratio <= 0.25 THEN 'A' WHEN pipeline_ratio <= 0.75 THEN 'B'
                     WHEN pipeline_ratio <= 1.5 THEN 'C' WHEN pipeline_ratio <= 3 THEN 'D' ELSE 'F' END
                    AS supply_risk_score,
                CASE WHEN price_momentum_pct IS NULL THEN NULL
                     WHEN price_momentum_pct >= 2 THEN 'A' WHEN price_momentum_pct >= -2 THEN 'B'
                     WHEN price_momentum_pct >= -5 THEN 'C' WHEN price_momentum_pct >= -8 THEN 'D' ELSE 'F' END
                    AS momentum_score,
                CASE WHEN transaction_count >= 1000 THEN 'A' WHEN transaction_count >= 700 THEN 'B'
                     WHEN transaction_count >= 500 THEN 'C' WHEN transaction_count >= 350 THEN 'D' ELSE 'F' END
                    AS liquidity_score
            FROM v_community_summary
        ),
        pts AS (
            SELECT *,
                list_position(['F','D','C','B','A'], yield_score) AS yp,
                list_position(['F','D','C','B','A'], supply_risk_score) AS sp,
                list_position(['F','D','C','B','A'], momentum_score) AS mp,
                list_position(['F','D','C','B','A'], liquidity_score) AS lp
            FROM g
        ),
        scored AS (
            -- Points 1-5 per factor, weighted mean over the factors present,
            -- scaled to 20-100. No yield, no score: it's the core factor.
            SELECT *,
                CASE WHEN yp IS NULL THEN NULL ELSE ROUND(20 * (
                    {w['yield']} * yp + {w['supply']} * sp + {w['liquidity']} * lp
                    + coalesce({w['momentum']} * mp, 0)
                ) / ({w['yield']} + {w['supply']} + {w['liquidity']}
                     + CASE WHEN mp IS NULL THEN 0 ELSE {w['momentum']} END), 0) END AS composite_score
            FROM pts
        )
        SELECT
            community, transaction_count, avg_price_per_sqft, avg_price,
            avg_roi_pct, avg_net_yield_pct, rent_basis, rent_contracts,
            matched_contracts, yield_projects,
            price_momentum_pct, paired_projects,
            offplan_sales, pipeline_ratio, units_completed_2026, supply_risk,
            yield_score, supply_risk_score, momentum_score, liquidity_score,
            composite_score,
            CASE WHEN composite_score IS NULL THEN 'INSUFFICIENT DATA'
                 WHEN composite_score >= 70 THEN 'INVEST'
                 WHEN composite_score >= 50 THEN 'HOLD'
                 ELSE 'AVOID' END AS recommendation
        FROM scored
    """)


def _print_summary(conn):
    """Print database summary."""
    print("\n--- Database Summary ---")
    for table in ["dld_sales", "dld_rents", "dld_projects", "transactions"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,} rows")

    scored = conn.execute(
        "SELECT COUNT(*) FILTER (WHERE composite_score IS NOT NULL), COUNT(*) FROM v_investment_scores"
    ).fetchone()
    print(f"\n--- Scores: {scored[0]} of {scored[1]} communities have enough rent data ---")
    rows = conn.execute("""
        SELECT community, avg_roi_pct, price_momentum_pct, pipeline_ratio,
               composite_score, recommendation
        FROM v_investment_scores
        ORDER BY composite_score DESC NULLS LAST, community
    """).fetchall()
    for c, y, m, p, s, r in rows:
        fmt = lambda v, f: "  n/a" if v is None else format(v, f)
        print(f"  {c:32s} | Yield: {fmt(y, '5.2f')}% | Momentum: {fmt(m, '5.1f')}% | "
              f"Off-plan/ready: {p:5.2f} | Score: {fmt(s, '3.0f')} | {r}")


if __name__ == "__main__":
    init_db()
