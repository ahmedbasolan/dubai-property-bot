"""Load DLD open-data exports into clean sales and projects tables.

Reads the CSVs exported by hand from dubailand.gov.ae/en/open-data/real-estate-data
(`transactions-*.csv`, `projects-*.csv` in data/raw/dld/), applies the cleaning
rules from docs/plans/2026-10-23-real-dld-data.md, and writes
data/processed/dld_sales.parquet and dld_projects.parquet.

Every rule that drops rows is counted, so the report shows exactly how the raw
export became the table the app scores.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import duckdb

from config import COMMUNITY_MAP_PATH, DLD_RAW_DIR, PROCESSED_DIR

SQM_TO_SQFT = 10.7639

# Export column code -> our column. The gateway's CSV headers are these codes,
# not the display names its results table shows.
SALES_COLUMNS = {
    "TRANSACTION_NUMBER": "transaction_id",
    "INSTANCE_DATE": "transaction_ts",
    "PROCEDURE_EN": "procedure",
    "IS_OFFPLAN_EN": "offplan_label",
    "IS_FREE_HOLD_EN": "freehold_label",
    "AREA_EN": "area_en",
    "PROP_SB_TYPE_EN": "property_sub_type",
    "TRANS_VALUE": "price_aed",
    "ACTUAL_AREA": "size_sqm",
    "ROOMS_EN": "rooms",
    "PARKING": "parking",
    "PROJECT_EN": "project",
}

RENT_COLUMNS = {
    "REGISTRATION_DATE": "registration_ts",
    "START_DATE": "start_ts",
    "END_DATE": "end_ts",
    "VERSION_EN": "version",
    "AREA_EN": "area_en",
    "ANNUAL_AMOUNT": "annual_rent_aed",
    "ACTUAL_AREA": "size_sqm",
    "PROP_SUB_TYPE_EN": "property_sub_type",
    "USAGE_EN": "usage",
    "TOTAL_PROPERTIES": "total_properties",
    "PROJECT_EN": "project",
}

PROJECT_COLUMNS = {
    "PROJECT_NUMBER": "project_number",
    "PROJECT_EN": "project",
    "DEVELOPER_EN": "developer",
    "PROJECT_STATUS": "status",
    "PERCENT_COMPLETED": "percent_completed",
    "END_DATE": "planned_end_ts",
    "COMPLETION_DATE": "completion_ts",
    "AREA_EN": "area_en",
    "CNT_UNIT": "units",
    "CNT_VILLA": "villas",
}

# Residential exports still contain offices, shops and hotel rooms.
APARTMENT_SUB_TYPES = ("Flat", "Stacked Townhouses")

# A sale is a price outlier when its AED/sqm sits outside these multiples of
# the median for its community (or area) and ready/off-plan status. The low
# side catches share and partial transfers (e.g. AED 2,552 for a 44 m2 1BR).
OUTLIER_LOW, OUTLIER_HIGH = 0.3, 5.0


class ExportFormatError(ValueError):
    """An export is missing a column the loader depends on."""


def _read_exports(conn, table: str, pattern: str, columns: dict, raw_dir: Path) -> list:
    files = sorted(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No {pattern} in {raw_dir} - export it from the DLD gateway")
    for path in files:
        header = conn.execute(
            "SELECT * FROM read_csv(?, header=true, all_varchar=true, strict_mode=false) LIMIT 0",
            [path.as_posix()],
        ).description
        missing = set(columns) - {col[0] for col in header}
        if missing:
            raise ExportFormatError(f"{path.name} is missing columns: {sorted(missing)}")

    select = ", ".join(f'"{src}" AS {dst}' for src, dst in columns.items())
    paths = [p.as_posix() for p in files]
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE {table} AS
        SELECT {select}
        FROM read_csv(?, header=true, all_varchar=true, strict_mode=false, union_by_name=true)
    """, [paths])
    return files


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def load_sales(conn, raw_dir: Path, map_path: Path) -> dict:
    """Build table `sales` from transactions exports. Returns per-rule row counts."""
    _read_exports(conn, "raw_sales", "transactions-*.csv", SALES_COLUMNS, raw_dir)
    report = {"raw": _count(conn, "raw_sales")}

    conn.execute("CREATE OR REPLACE TEMP TABLE community_map AS SELECT * FROM read_csv(?, header=true)",
                 [map_path.as_posix()])

    # Rows differ only in nearest metro when a transaction number repeats.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE s AS
        SELECT DISTINCT ON (transaction_id) * FROM raw_sales ORDER BY transaction_id
    """)
    report["duplicates_dropped"] = report["raw"] - _count(conn, "s")

    before = _count(conn, "s")
    conn.execute(f"DELETE FROM s WHERE property_sub_type NOT IN {APARTMENT_SUB_TYPES}")
    report["non_apartment_dropped"] = before - _count(conn, "s")

    before = _count(conn, "s")
    conn.execute("""
        DELETE FROM s WHERE TRY_CAST(price_aed AS DOUBLE) IS NULL OR TRY_CAST(price_aed AS DOUBLE) <= 0
                         OR TRY_CAST(size_sqm AS DOUBLE) IS NULL OR TRY_CAST(size_sqm AS DOUBLE) <= 0
    """)
    report["missing_price_or_size_dropped"] = before - _count(conn, "s")

    conn.execute("""
        CREATE OR REPLACE TEMP TABLE typed AS
        SELECT
            transaction_id,
            CAST(transaction_ts AS TIMESTAMP)::DATE AS transaction_date,
            procedure,
            offplan_label = 'Off-Plan' AS is_offplan,
            freehold_label = 'Free Hold' AS is_freehold,
            area_en,
            property_sub_type,
            CAST(price_aed AS DOUBLE) AS price_aed,
            CAST(size_sqm AS DOUBLE) AS size_sqm,
            CAST(size_sqm AS DOUBLE) * {sqft} AS size_sqft,
            CAST(price_aed AS DOUBLE) / CAST(size_sqm AS DOUBLE) AS price_per_sqm,
            CAST(price_aed AS DOUBLE) / (CAST(size_sqm AS DOUBLE) * {sqft}) AS price_per_sqft,
            CASE
                WHEN upper(rooms) = 'STUDIO' THEN 0
                ELSE TRY_CAST(regexp_extract(rooms, '^(\\d+) B/R$', 1) AS INTEGER)
            END AS bedrooms,
            rooms,
            nullif(trim(parking), '') IS NOT NULL AS has_parking,
            nullif(trim(project), '') AS project
        FROM s
    """.format(sqft=SQM_TO_SQFT))

    # Only community-name areas are mapped. Rows under DLD official areas
    # ("Madinat Al Mataar") keep community NULL; no project carries both
    # naming styles, so they can't be recovered through the project either.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE mapped AS
        SELECT t.*, m.community
        FROM typed t LEFT JOIN community_map m ON upper(t.area_en) = m.area_en
    """)

    conn.execute(f"""
        CREATE OR REPLACE TABLE sales AS
        WITH grouped AS (
            SELECT *,
                   median(price_per_sqm) OVER (
                       PARTITION BY coalesce(community, upper(area_en)), is_offplan
                   ) AS group_median
            FROM mapped
        )
        SELECT * EXCLUDE (group_median) FROM grouped
        WHERE price_per_sqm BETWEEN group_median * {OUTLIER_LOW} AND group_median * {OUTLIER_HIGH}
    """)
    report["price_outliers_dropped"] = _count(conn, "mapped") - _count(conn, "sales")
    report["clean"] = _count(conn, "sales")
    report["mapped_to_community"] = conn.execute(
        "SELECT COUNT(*) FROM sales WHERE community IS NOT NULL").fetchone()[0]
    return report


def load_rents(conn, raw_dir: Path) -> dict:
    """Build table `rents` from Ejari exports. Needs `sales` and `community_map`.

    Rents carry DLD official area names ("Al Barsha South Fourth") and no
    bedroom count, so community comes from the area map when the name matches,
    else from the project's ready sales, and yields are computed per m2.
    """
    _read_exports(conn, "raw_rents", "rents-*.csv", RENT_COLUMNS, raw_dir)
    report = {"raw": _count(conn, "raw_rents")}

    conn.execute("CREATE OR REPLACE TEMP TABLE r AS SELECT * FROM raw_rents")
    before = _count(conn, "r")
    conn.execute(f"""
        DELETE FROM r WHERE usage IS DISTINCT FROM 'Residential'
                         OR trim(property_sub_type) NOT IN ('Flat', 'Studio')
    """)
    report["non_apartment_dropped"] = before - _count(conn, "r")

    # Each unit row of a multi-unit contract repeats the contract's total rent.
    before = _count(conn, "r")
    conn.execute("DELETE FROM r WHERE TRY_CAST(total_properties AS INTEGER) IS DISTINCT FROM 1")
    report["multi_unit_contracts_dropped"] = before - _count(conn, "r")

    before = _count(conn, "r")
    conn.execute("""
        DELETE FROM r WHERE TRY_CAST(annual_rent_aed AS DOUBLE) IS NULL OR TRY_CAST(annual_rent_aed AS DOUBLE) <= 0
                         OR TRY_CAST(size_sqm AS DOUBLE) IS NULL OR TRY_CAST(size_sqm AS DOUBLE) <= 0
    """)
    report["missing_rent_or_size_dropped"] = before - _count(conn, "r")

    conn.execute("""
        CREATE OR REPLACE TEMP TABLE project_community AS
        SELECT upper(project) AS key, arg_max(community, n) AS community
        FROM (SELECT project, community, COUNT(*) AS n FROM sales
              WHERE community IS NOT NULL AND project IS NOT NULL AND NOT is_offplan GROUP BY ALL)
        GROUP BY key
    """)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE rents_mapped AS
        SELECT
            CAST(r.registration_ts AS TIMESTAMP)::DATE AS registration_date,
            TRY_CAST(r.start_ts AS TIMESTAMP)::DATE AS start_date,
            TRY_CAST(r.end_ts AS TIMESTAMP)::DATE AS end_date,
            r.version = 'New' AS is_new_contract,
            r.area_en,
            CAST(r.annual_rent_aed AS DOUBLE) AS annual_rent_aed,
            CAST(r.size_sqm AS DOUBLE) AS size_sqm,
            CAST(r.annual_rent_aed AS DOUBLE) / CAST(r.size_sqm AS DOUBLE) AS rent_per_sqm,
            nullif(trim(r.project), '') AS project,
            coalesce(m.community, pc.community) AS community,
            CASE WHEN m.community IS NOT NULL THEN 'area'
                 WHEN pc.community IS NOT NULL THEN 'project' END AS community_source
        FROM r
        LEFT JOIN community_map m ON upper(r.area_en) = m.area_en
        LEFT JOIN project_community pc ON upper(trim(r.project)) = pc.key
    """)

    conn.execute(f"""
        CREATE OR REPLACE TABLE rents AS
        WITH grouped AS (
            SELECT *, median(rent_per_sqm) OVER (
                       PARTITION BY coalesce(community, upper(area_en))) AS group_median
            FROM rents_mapped
        )
        SELECT * EXCLUDE (group_median) FROM grouped
        WHERE rent_per_sqm BETWEEN group_median * {OUTLIER_LOW} AND group_median * {OUTLIER_HIGH}
    """)
    report["rent_outliers_dropped"] = _count(conn, "rents_mapped") - _count(conn, "rents")
    report["clean"] = _count(conn, "rents")
    for source in ("area", "project"):
        report[f"community_by_{source}"] = conn.execute(
            "SELECT COUNT(*) FROM rents WHERE community_source = ?", [source]).fetchone()[0]
    return report


def load_projects(conn, raw_dir: Path) -> dict:
    """Build table `projects` from projects exports. Needs `sales` for communities."""
    _read_exports(conn, "raw_projects", "projects-*.csv", PROJECT_COLUMNS, raw_dir)
    report = {"raw": _count(conn, "raw_projects")}

    conn.execute("""
        CREATE OR REPLACE TABLE projects AS
        WITH p AS (
            SELECT DISTINCT ON (project_number) * FROM raw_projects ORDER BY project_number
        ),
        project_community AS (
            SELECT upper(project) AS key, arg_max(community, n) AS community
            FROM (SELECT project, community, COUNT(*) AS n FROM sales
                  WHERE community IS NOT NULL AND project IS NOT NULL GROUP BY ALL)
            GROUP BY key
        )
        SELECT
            p.project_number,
            p.project,
            p.developer,
            p.status,
            -- A handful of rows report 3,300-17,692 percent; treat as unknown.
            CASE WHEN TRY_CAST(p.percent_completed AS DOUBLE) BETWEEN 0 AND 100
                 THEN TRY_CAST(p.percent_completed AS DOUBLE) END AS percent_completed,
            TRY_CAST(p.planned_end_ts AS TIMESTAMP)::DATE AS planned_end_date,
            TRY_CAST(p.completion_ts AS TIMESTAMP)::DATE AS completion_date,
            p.area_en,
            coalesce(TRY_CAST(p.units AS INTEGER), 0) AS units,
            coalesce(TRY_CAST(p.villas AS INTEGER), 0) AS villas,
            pc.community
        FROM p LEFT JOIN project_community pc ON upper(trim(p.project)) = pc.key
    """)
    report["clean"] = _count(conn, "projects")
    report["linked_to_community"] = conn.execute(
        "SELECT COUNT(*) FROM projects WHERE community IS NOT NULL").fetchone()[0]
    report["bad_percent_nulled"] = conn.execute("""
        SELECT COUNT(*) FROM raw_projects
        WHERE TRY_CAST(percent_completed AS DOUBLE) NOT BETWEEN 0 AND 100
    """).fetchone()[0]
    return report


def build(raw_dir: Path = DLD_RAW_DIR, map_path: Path = COMMUNITY_MAP_PATH,
          out_dir: Path = PROCESSED_DIR) -> dict:
    """Load all exports and write parquet files. Returns the cleaning report."""
    conn = duckdb.connect()
    report = {"sales": load_sales(conn, raw_dir, map_path)}
    report["projects"] = load_projects(conn, raw_dir)
    tables = ["sales", "projects"]
    if list(raw_dir.glob("rents-*.csv")):
        report["rents"] = load_rents(conn, raw_dir)
        tables.append("rents")

    out_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        conn.execute(f"COPY {table} TO ? (FORMAT parquet)", [(out_dir / f"dld_{table}.parquet").as_posix()])
    conn.close()
    return report


def _print_report(report: dict):
    for table, counts in report.items():
        print(f"{table}:")
        for rule, n in counts.items():
            print(f"  {rule:32} {n:>8,}")


if __name__ == "__main__":
    _print_report(build())
