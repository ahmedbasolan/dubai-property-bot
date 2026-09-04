"""DuckDB setup: schema, data loading, and analytical views."""

import csv
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"


def init_db():
    """Initialize DuckDB with schema, load data, create views."""
    conn = duckdb.connect(str(DB_PATH))

    # --- Schema ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id VARCHAR PRIMARY KEY,
            community VARCHAR,
            property_type VARCHAR,
            bedrooms INTEGER,
            price_aed BIGINT,
            size_sqft INTEGER,
            transaction_date DATE,
            roi_pct DOUBLE,
            developer VARCHAR,
            handover_status VARCHAR,
            floor_level INTEGER,
            view_type VARCHAR,
            service_charge_aed_sqft DOUBLE,
            parking_spots INTEGER,
            completion_year INTEGER,
            furnishing VARCHAR,
            amenities VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS communities (
            community_name VARCHAR PRIMARY KEY,
            district VARCHAR,
            established_year INTEGER,
            master_developer VARCHAR,
            occupancy_rate DOUBLE,
            off_plan_percentage DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS supply_pipeline (
            community_name VARCHAR PRIMARY KEY,
            existing_stock_units INTEGER,
            units_under_construction INTEGER,
            units_completed_last_12_months INTEGER,
            units_expected_next_24_months INTEGER,
            pipeline_pct_of_stock DOUBLE,
            supply_risk VARCHAR
        )
    """)

    # --- Load CSVs ---
    _load_csv(conn, "transactions", DATA_DIR / "transactions.csv")
    _load_csv(conn, "communities", DATA_DIR / "communities.csv")
    _load_csv(conn, "supply_pipeline", DATA_DIR / "supply_pipeline.csv")

    # --- Analytical Views ---

    # Net yield calculation (deterministic, no LLM involvement)
    conn.execute("""
        CREATE OR REPLACE VIEW v_net_yield AS
        SELECT
            t.transaction_id,
            t.community,
            t.property_type,
            t.bedrooms,
            t.price_aed,
            t.size_sqft,
            t.roi_pct,
            t.floor_level,
            t.view_type,
            t.service_charge_aed_sqft,
            t.parking_spots,
            t.completion_year,
            t.furnishing,
            t.developer,
            t.handover_status,
            -- Estimated annual rent from ROI
            ROUND(t.price_aed * t.roi_pct / 100) AS estimated_annual_rent,
            -- Annual service charges
            ROUND(t.size_sqft * t.service_charge_aed_sqft) AS annual_service_charges,
            -- Management fees (8% of rent)
            ROUND(t.price_aed * t.roi_pct / 100 * 0.08) AS management_fees,
            -- Vacancy loss (5% of rent, ~2-3 weeks/year)
            ROUND(t.price_aed * t.roi_pct / 100 * 0.05) AS vacancy_loss,
            -- Net yield
            ROUND(
                (t.price_aed * t.roi_pct / 100
                 - t.size_sqft * t.service_charge_aed_sqft
                 - t.price_aed * t.roi_pct / 100 * 0.08
                 - t.price_aed * t.roi_pct / 100 * 0.05
                ) / t.price_aed * 100,
                2
            ) AS net_yield_pct,
            -- Price per sqft
            ROUND(t.price_aed::DOUBLE / t.size_sqft, 1) AS price_per_sqft
        FROM transactions t
    """)

    # Community summary with aggregated metrics
    conn.execute("""
        CREATE OR REPLACE VIEW v_community_summary AS
        SELECT
            v.community,
            COUNT(*) AS transaction_count,
            ROUND(AVG(v.price_per_sqft), 0) AS avg_price_per_sqft,
            ROUND(MIN(v.price_per_sqft), 0) AS min_price_per_sqft,
            ROUND(MAX(v.price_per_sqft), 0) AS max_price_per_sqft,
            ROUND(AVG(v.roi_pct), 1) AS avg_roi_pct,
            ROUND(AVG(v.net_yield_pct), 2) AS avg_net_yield_pct,
            ROUND(AVG(v.service_charge_aed_sqft), 1) AS avg_service_charge,
            ROUND(AVG(v.price_aed), 0) AS avg_price,
            sp.supply_risk,
            sp.pipeline_pct_of_stock,
            sp.units_expected_next_24_months,
            c.occupancy_rate,
            c.district,
            c.master_developer
        FROM v_net_yield v
        LEFT JOIN supply_pipeline sp ON v.community = sp.community_name
        LEFT JOIN communities c ON v.community = c.community_name
        GROUP BY v.community, sp.supply_risk, sp.pipeline_pct_of_stock,
                 sp.units_expected_next_24_months, c.occupancy_rate,
                 c.district, c.master_developer
    """)

    # Investment scoring view (7 metrics)
    conn.execute("""
        CREATE OR REPLACE VIEW v_investment_scores AS
        WITH community_stats AS (
            SELECT * FROM v_community_summary
        ),
        benchmarks AS (
            SELECT
                AVG(avg_price_per_sqft) AS bench_price_sqft,
                AVG(avg_roi_pct) AS bench_roi,
                AVG(avg_net_yield_pct) AS bench_net_yield,
                AVG(avg_service_charge) AS bench_service_charge,
                AVG(pipeline_pct_of_stock) AS bench_pipeline,
                AVG(occupancy_rate) AS bench_occupancy
            FROM community_stats
        )
        SELECT
            cs.community,
            cs.district,
            cs.transaction_count,
            cs.avg_price_per_sqft,
            cs.avg_roi_pct,
            cs.avg_net_yield_pct,
            cs.avg_service_charge,
            cs.avg_price,
            cs.supply_risk,
            cs.pipeline_pct_of_stock,
            cs.occupancy_rate,
            cs.master_developer,
            -- Metric 1: Price/sqft score (lower is better, below avg = good)
            CASE
                WHEN cs.avg_price_per_sqft < b.bench_price_sqft * 0.8 THEN 'A'
                WHEN cs.avg_price_per_sqft < b.bench_price_sqft * 0.95 THEN 'B'
                WHEN cs.avg_price_per_sqft < b.bench_price_sqft * 1.1 THEN 'C'
                WHEN cs.avg_price_per_sqft < b.bench_price_sqft * 1.3 THEN 'D'
                ELSE 'F'
            END AS price_score,
            -- Metric 2: Gross yield score (higher is better)
            CASE
                WHEN cs.avg_roi_pct >= 8.5 THEN 'A'
                WHEN cs.avg_roi_pct >= 7.0 THEN 'B'
                WHEN cs.avg_roi_pct >= 6.0 THEN 'C'
                WHEN cs.avg_roi_pct >= 5.0 THEN 'D'
                ELSE 'F'
            END AS yield_score,
            -- Metric 3: Net yield score (higher is better)
            CASE
                WHEN cs.avg_net_yield_pct >= 7.0 THEN 'A'
                WHEN cs.avg_net_yield_pct >= 5.5 THEN 'B'
                WHEN cs.avg_net_yield_pct >= 4.0 THEN 'C'
                WHEN cs.avg_net_yield_pct >= 2.5 THEN 'D'
                ELSE 'F'
            END AS net_yield_score,
            -- Metric 4: Service charge score (lower is better)
            CASE
                WHEN cs.avg_service_charge <= 10 THEN 'A'
                WHEN cs.avg_service_charge <= 15 THEN 'B'
                WHEN cs.avg_service_charge <= 20 THEN 'C'
                WHEN cs.avg_service_charge <= 25 THEN 'D'
                ELSE 'F'
            END AS service_charge_score,
            -- Metric 5: Supply pipeline risk (lower is better)
            CASE
                WHEN cs.pipeline_pct_of_stock <= 5 THEN 'A'
                WHEN cs.pipeline_pct_of_stock <= 10 THEN 'B'
                WHEN cs.pipeline_pct_of_stock <= 15 THEN 'C'
                WHEN cs.pipeline_pct_of_stock <= 25 THEN 'D'
                ELSE 'F'
            END AS supply_risk_score,
            -- Metric 6: Occupancy (higher is better)
            CASE
                WHEN cs.occupancy_rate >= 0.92 THEN 'A'
                WHEN cs.occupancy_rate >= 0.88 THEN 'B'
                WHEN cs.occupancy_rate >= 0.84 THEN 'C'
                WHEN cs.occupancy_rate >= 0.80 THEN 'D'
                ELSE 'F'
            END AS occupancy_score,
            -- Metric 7: Developer track record (simplified)
            CASE
                WHEN cs.master_developer IN ('Emaar', 'Meraas') THEN 'A'
                WHEN cs.master_developer IN ('Nakheel', 'DAMAC') THEN 'B'
                WHEN cs.master_developer IN ('DMCC', 'Nshama') THEN 'C'
                ELSE 'D'
            END AS developer_score,
            -- Composite recommendation
            CASE
                WHEN (
                    (CASE WHEN cs.avg_roi_pct >= 7.0 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.avg_net_yield_pct >= 5.0 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.pipeline_pct_of_stock <= 15 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.occupancy_rate >= 0.85 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.avg_service_charge <= 18 THEN 1 ELSE 0 END)
                ) >= 4 THEN 'INVEST'
                WHEN (
                    (CASE WHEN cs.avg_roi_pct >= 6.0 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.avg_net_yield_pct >= 3.5 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.pipeline_pct_of_stock <= 20 THEN 1 ELSE 0 END) +
                    (CASE WHEN cs.occupancy_rate >= 0.82 THEN 1 ELSE 0 END)
                ) >= 3 THEN 'HOLD'
                ELSE 'AVOID'
            END AS recommendation,
            -- Numeric composite score (0-100)
            ROUND(
                (CASE WHEN cs.avg_roi_pct >= 8.5 THEN 25 WHEN cs.avg_roi_pct >= 7.0 THEN 20 WHEN cs.avg_roi_pct >= 6.0 THEN 15 WHEN cs.avg_roi_pct >= 5.0 THEN 10 ELSE 5 END) +
                (CASE WHEN cs.avg_net_yield_pct >= 7.0 THEN 25 WHEN cs.avg_net_yield_pct >= 5.5 THEN 20 WHEN cs.avg_net_yield_pct >= 4.0 THEN 15 WHEN cs.avg_net_yield_pct >= 2.5 THEN 10 ELSE 5 END) +
                (CASE WHEN cs.pipeline_pct_of_stock <= 5 THEN 20 WHEN cs.pipeline_pct_of_stock <= 10 THEN 15 WHEN cs.pipeline_pct_of_stock <= 15 THEN 10 WHEN cs.pipeline_pct_of_stock <= 25 THEN 5 ELSE 0 END) +
                (CASE WHEN cs.occupancy_rate >= 0.92 THEN 15 WHEN cs.occupancy_rate >= 0.88 THEN 12 WHEN cs.occupancy_rate >= 0.84 THEN 9 WHEN cs.occupancy_rate >= 0.80 THEN 6 ELSE 3 END) +
                (CASE WHEN cs.avg_service_charge <= 10 THEN 15 WHEN cs.avg_service_charge <= 15 THEN 12 WHEN cs.avg_service_charge <= 20 THEN 9 WHEN cs.avg_service_charge <= 25 THEN 6 ELSE 3 END)
            , 0) AS composite_score
        FROM community_stats cs
        CROSS JOIN benchmarks b
    """)

    print(f"DuckDB initialized: {DB_PATH}")
    _print_summary(conn)
    conn.close()


def _load_csv(conn, table_name: str, csv_path: Path):
    """Load a CSV file into a DuckDB table."""
    if not csv_path.exists():
        print(f"  WARNING: {csv_path} not found, skipping {table_name}")
        return

    conn.execute(f"DELETE FROM {table_name}")
    conn.execute(f"""
        INSERT INTO {table_name}
        SELECT * FROM read_csv_auto('{csv_path.as_posix()}', header=true, all_varchar=false)
    """)
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"  Loaded {count} rows into {table_name}")


def _print_summary(conn):
    """Print database summary."""
    print("\n--- Database Summary ---")
    for table in ["transactions", "communities", "supply_pipeline"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    # Top 5 communities by net yield
    print("\n--- Top 5 Communities by Net Yield ---")
    rows = conn.execute("""
        SELECT community, avg_roi_pct, avg_net_yield_pct, avg_price_per_sqft,
               supply_risk, composite_score, recommendation
        FROM v_investment_scores
        ORDER BY avg_net_yield_pct DESC
        LIMIT 5
    """).fetchall()
    for row in rows:
        print(f"  {row[0]:30s} | ROI: {row[1]:5.1f}% | Net: {row[2]:5.2f}% | "
              f"AED/sqft: {row[3]:,.0f} | Risk: {row[4]:6s} | Score: {row[5]:3.0f} | {row[6]}")


if __name__ == "__main__":
    init_db()
