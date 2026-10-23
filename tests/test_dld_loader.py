"""Contracts for the DLD export loader (src/dld_loader.py).

Unit tests run on tiny fixture exports shaped like the gateway's CSVs. The
integration tests at the bottom run on the real exports in data/raw/dld/ and
skip when they're absent (they're gitignored).
"""

import csv
import sys
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import db_setup  # noqa: E402
import dld_loader  # noqa: E402
from config import COMMUNITY_MAP_PATH, DLD_RAW_DIR, PROCESSED_DIR  # noqa: E402

COORDS_PATH = COMMUNITY_MAP_PATH.parent / "community_coords.csv"

SALES_HEADER = [
    "TRANSACTION_NUMBER", "INSTANCE_DATE", "GROUP_EN", "PROCEDURE_EN", "IS_OFFPLAN_EN",
    "IS_FREE_HOLD_EN", "USAGE_EN", "AREA_EN", "PROP_TYPE_EN", "PROP_SB_TYPE_EN", "TRANS_VALUE",
    "PROCEDURE_AREA", "ACTUAL_AREA", "ROOMS_EN", "PARKING", "NEAREST_METRO_EN", "NEAREST_MALL_EN",
    "NEAREST_LANDMARK_EN", "TOTAL_BUYER", "TOTAL_SELLER", "MASTER_PROJECT_EN", "PROJECT_EN",
]
RENT_HEADER = [
    "REGISTRATION_DATE", "START_DATE", "END_DATE", "VERSION_EN", "AREA_EN", "CONTRACT_AMOUNT",
    "ANNUAL_AMOUNT", "IS_FREE_HOLD_EN", "ACTUAL_AREA", "PROP_TYPE_EN", "PROP_SUB_TYPE_EN", "ROOMS",
    "USAGE_EN", "NEAREST_METRO_EN", "NEAREST_MALL_EN", "NEAREST_LANDMARK_EN", "PARKING",
    "TOTAL_PROPERTIES", "MASTER_PROJECT_EN", "PROJECT_EN",
]
PROJECT_HEADER = [
    "PROJECT_NUMBER", "PROJECT_EN", "DEVELOPER_NUMBER", "DEVELOPER_EN", "START_DATE", "END_DATE",
    "ADOPTION_DATE", "PRJ_TYPE_EN", "PROJECT_VALUE", "ESCROW_ACCOUNT_NUMBER", "PROJECT_STATUS",
    "PERCENT_COMPLETED", "INSPECTION_DATE", "COMPLETION_DATE", "DESCRIPTION_EN", "AREA_EN",
    "ZONE_EN", "CNT_LAND", "CNT_BUILDING", "CNT_VILLA", "CNT_UNIT", "MASTER_PROJECT_EN",
]


def sale(txn, area="JUMEIRAH VILLAGE CIRCLE", value="1000000", size="100", rooms="1 B/R",
         sub_type="Flat", offplan="Ready", metro="", project="Tower A", parking="1"):
    return {
        "TRANSACTION_NUMBER": txn, "INSTANCE_DATE": "2026-03-01 10:00:00", "GROUP_EN": "Sales",
        "PROCEDURE_EN": "Sale", "IS_OFFPLAN_EN": offplan, "IS_FREE_HOLD_EN": "Free Hold",
        "USAGE_EN": "Residential", "AREA_EN": area, "PROP_TYPE_EN": "Unit",
        "PROP_SB_TYPE_EN": sub_type, "TRANS_VALUE": value, "PROCEDURE_AREA": size,
        "ACTUAL_AREA": size, "ROOMS_EN": rooms, "PARKING": parking, "NEAREST_METRO_EN": metro,
        "PROJECT_EN": project,
    }


def rent(area="Al Barsha South Fourth", amount="80000", size="80", sub_type="Flat",
         usage="Residential", units="1", version="New", project="Tower A"):
    return {
        "REGISTRATION_DATE": "2026-10-22 10:00:00", "START_DATE": "2026-11-01 00:00:00",
        "END_DATE": "2027-10-31 00:00:00", "VERSION_EN": version, "AREA_EN": area,
        "CONTRACT_AMOUNT": amount, "ANNUAL_AMOUNT": amount, "ACTUAL_AREA": size,
        "PROP_TYPE_EN": "Unit", "PROP_SUB_TYPE_EN": sub_type, "USAGE_EN": usage,
        "TOTAL_PROPERTIES": units, "PROJECT_EN": project,
    }


def write_csv(path: Path, header: list, rows: list):
    # utf-8-sig: the gateway's exports start with a BOM.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in header})


@pytest.fixture
def exports(tmp_path):
    raw = tmp_path / "dld"
    raw.mkdir()
    map_path = tmp_path / "community_map.csv"
    map_path.write_text("community,area_en\nJVC,JUMEIRAH VILLAGE CIRCLE\nBusiness Bay,BUSINESS BAY\n")

    jvc_ready = [sale(f"r-{i}", value=str(1_000_000 + i * 10_000)) for i in range(5)]
    write_csv(raw / "transactions-2026-01-01.csv", SALES_HEADER, jvc_ready + [
        sale("dup-1", metro="Metro A"),
        sale("dup-1", metro="Metro B"),                          # same sale, other metro
        sale("office-1", sub_type="Office", rooms="Office"),
        sale("studio-1", rooms="Studio", value="600000", size="40"),
        sale("share-1", value="2552", size="44"),                # partial transfer
        sale("nosize-1", size=""),
        sale("bb-1", area="Business Bay", value="2000000"),      # title-case variant
        sale("offplan-1", area="Madinat Al Mataar", offplan="Off-Plan", project="New Launch"),
        sale("na-1", rooms="NA"),
    ])
    write_csv(raw / "projects-2026-01-01.csv", PROJECT_HEADER, [
        {"PROJECT_NUMBER": "1", "PROJECT_EN": "Tower A", "DEVELOPER_EN": "Dev One",
         "PROJECT_STATUS": "FINISHED", "PERCENT_COMPLETED": "100",
         "COMPLETION_DATE": "2026-02-01 09:00:00", "END_DATE": "2025-12-31 00:00:00",
         "AREA_EN": "Al Barsha South Fourth", "CNT_UNIT": "300", "CNT_VILLA": "0",
         "DESCRIPTION_EN": "TOWER\nWITH A LINE BREAK"},
        {"PROJECT_NUMBER": "2", "PROJECT_EN": "Glitch", "DEVELOPER_EN": "Dev Two",
         "PROJECT_STATUS": "ACTIVE", "PERCENT_COMPLETED": "10643.59",
         "COMPLETION_DATE": "2026-12-31 00:00:00", "AREA_EN": "Somewhere", "CNT_UNIT": ""},
    ])
    write_csv(raw / "rents-2026-01-01.csv", RENT_HEADER, [
        rent(),                                                   # official area, known project
        rent(amount="90000", version="Renewed"),
        rent(area="Business Bay", project=""),                    # community name, no project
        rent(area="Madinat Al Mataar", project="Unknown Tower"),  # neither maps
        rent(units="19", amount="1900000"),                       # row of a multi-unit contract
        rent(sub_type="Office", usage="Commercial"),
        rent(sub_type="Studio ", size="35", amount="35000"),      # trailing space in the export
        rent(amount="5000000"),                                   # rent outlier
    ])
    return raw, map_path


@pytest.fixture
def loaded(exports):
    raw, map_path = exports
    conn = duckdb.connect()
    sales_report = dld_loader.load_sales(conn, raw, map_path)
    projects_report = dld_loader.load_projects(conn, raw)
    rents_report = dld_loader.load_rents(conn, raw)
    return conn, sales_report, projects_report, rents_report


def _ids(conn):
    return {r[0] for r in conn.execute("SELECT transaction_id FROM sales").fetchall()}


def test_duplicate_transaction_numbers_are_kept_once(loaded):
    conn, report, _, _ = loaded
    assert report["duplicates_dropped"] == 1
    assert conn.execute("SELECT COUNT(*) FROM sales WHERE transaction_id = 'dup-1'").fetchone()[0] == 1


def test_only_apartments_survive(loaded):
    conn, report, _, _ = loaded
    assert report["non_apartment_dropped"] == 1
    assert "office-1" not in _ids(conn)


def test_missing_size_is_dropped_not_divided(loaded):
    conn, report, _, _ = loaded
    assert report["missing_price_or_size_dropped"] == 1
    assert "nosize-1" not in _ids(conn)


def test_partial_transfer_prices_are_outliers(loaded):
    conn, report, _, _ = loaded
    assert "share-1" not in _ids(conn)
    assert report["price_outliers_dropped"] == 1


def test_bedrooms_parse_studio_as_zero_and_unknown_as_null(loaded):
    conn, _, _, _ = loaded
    rows = dict(conn.execute(
        "SELECT transaction_id, bedrooms FROM sales WHERE transaction_id IN ('studio-1','r-0','na-1')"
    ).fetchall())
    assert rows == {"studio-1": 0, "r-0": 1, "na-1": None}


def test_units_and_flags_are_typed(loaded):
    conn, _, _, _ = loaded
    sqft, ppsf, offplan, parking = conn.execute(
        "SELECT size_sqft, price_per_sqft, is_offplan, has_parking FROM sales WHERE transaction_id = 'r-0'"
    ).fetchone()
    assert sqft == pytest.approx(100 * 10.7639)
    assert ppsf == pytest.approx(1_000_000 / (100 * 10.7639))
    assert offplan is False and parking is True


def test_community_matches_case_insensitively_and_unmapped_stays_null(loaded):
    conn, report, _, _ = loaded
    rows = dict(conn.execute(
        "SELECT transaction_id, community FROM sales WHERE transaction_id IN ('bb-1','offplan-1','r-0')"
    ).fetchall())
    assert rows == {"bb-1": "Business Bay", "offplan-1": None, "r-0": "JVC"}
    assert report["mapped_to_community"] == report["clean"] - 1


def test_projects_take_community_from_their_sales_and_null_bad_percent(loaded):
    conn, _, report, _ = loaded
    rows = {r[0]: r[1:] for r in conn.execute(
        "SELECT project, community, percent_completed, units FROM projects").fetchall()}
    assert rows["Tower A"] == ("JVC", 100.0, 300)
    assert rows["Glitch"] == (None, None, 0)
    assert report["bad_percent_nulled"] == 1


def test_rents_keep_single_unit_residential_apartments(loaded):
    _, _, _, report = loaded
    assert report["raw"] == 8
    assert report["non_apartment_dropped"] == 1      # office
    assert report["multi_unit_contracts_dropped"] == 1
    assert report["rent_outliers_dropped"] == 1      # AED 5M for 80 m2
    assert report["clean"] == 5                      # trailing-space "Studio " survives


def test_rents_find_community_by_area_name_or_project(loaded):
    conn, _, _, report = loaded
    rows = conn.execute("""
        SELECT area_en, project, community, community_source FROM rents ORDER BY annual_rent_aed
    """).fetchall()
    by_area = {(r[0], r[1]): (r[2], r[3]) for r in rows}
    # "Al Barsha South Fourth" isn't in the map; Tower A's ready sales are in JVC.
    assert by_area[("Al Barsha South Fourth", "Tower A")] == ("JVC", "project")
    assert by_area[("Business Bay", None)] == ("Business Bay", "area")
    assert by_area[("Madinat Al Mataar", "Unknown Tower")] == (None, None)
    assert report["community_by_project"] == 3 and report["community_by_area"] == 1


def test_rents_are_per_square_metre_and_flag_new_contracts(loaded):
    conn, _, _, _ = loaded
    per_sqm, is_new = conn.execute(
        "SELECT rent_per_sqm, is_new_contract FROM rents WHERE annual_rent_aed = 90000").fetchone()
    assert per_sqm == pytest.approx(90000 / 80) and is_new is False


def test_missing_column_fails_loudly(exports):
    raw, map_path = exports
    write_csv(raw / "transactions-broken.csv", [c for c in SALES_HEADER if c != "TRANS_VALUE"], [sale("x")])
    with pytest.raises(dld_loader.ExportFormatError, match="TRANS_VALUE"):
        dld_loader.load_sales(duckdb.connect(), raw, map_path)


def test_build_writes_parquet(exports, tmp_path):
    raw, map_path = exports
    report = dld_loader.build(raw, map_path, tmp_path / "out")
    assert (tmp_path / "out" / "dld_sales.parquet").exists()
    assert (tmp_path / "out" / "dld_projects.parquet").exists()
    # 14 raw - 1 duplicate - 1 office - 1 missing size - 1 partial transfer
    assert report["sales"]["clean"] == 10


def test_every_v1_community_has_coordinates_in_dubai():
    with open(COMMUNITY_MAP_PATH, encoding="utf-8") as f:
        communities = {r["community"] for r in csv.DictReader(f)}
    with open(COORDS_PATH, encoding="utf-8") as f:
        coords = {r["community"]: (float(r["lat"]), float(r["lng"])) for r in csv.DictReader(f)}
    assert set(coords) == communities
    for name, (lat, lng) in coords.items():
        assert 24.7 < lat < 25.4 and 54.9 < lng < 55.6, name


# --- Real exports (skipped when data/raw/dld/ has none) ---------------------

real_exports = pytest.mark.skipif(
    not list(DLD_RAW_DIR.glob("transactions-*.csv")),
    reason="no DLD exports in data/raw/dld/ - see docs/plans/2026-10-23-real-dld-data.md",
)


@pytest.fixture(scope="module")
def real():
    conn = duckdb.connect()
    report = dld_loader.load_sales(conn, DLD_RAW_DIR, COMMUNITY_MAP_PATH)
    return conn, report


@real_exports
def test_every_community_map_row_matches_the_export(real):
    conn, _ = real
    unmatched = conn.execute("""
        SELECT m.area_en FROM read_csv(?, header=true) m
        WHERE m.area_en NOT IN (SELECT upper(area_en) FROM sales)
    """, [COMMUNITY_MAP_PATH.as_posix()]).fetchall()
    assert unmatched == []


@real_exports
def test_every_v1_community_clears_the_ready_sales_bar(real):
    conn, _ = real
    thin = conn.execute("""
        SELECT community, COUNT(*) FILTER (WHERE NOT is_offplan) AS ready FROM sales
        WHERE community IS NOT NULL GROUP BY 1 HAVING ready < 250
    """).fetchall()
    assert thin == []


@real_exports
def test_prices_are_plausible_for_dubai(real):
    conn, _ = real
    p01, p50, p99 = conn.execute(
        "SELECT quantile_cont(price_per_sqft, [0.01, 0.5, 0.99]) FROM sales").fetchone()[0]
    assert 300 < p01 and 1_000 < p50 < 3_000 and p99 < 8_000


@pytest.mark.skipif(not (PROCESSED_DIR / "dld_sales.parquet").exists(),
                    reason="run `python src/dld_loader.py` first")
def test_price_history_view_has_enough_sales_per_cell():
    conn = duckdb.connect()
    db_setup._load_dld(conn)
    thin = conn.execute("""
        SELECT community, quarter FROM v_dld_price_history
        WHERE segment = 'Ready' AND sales_count < 20
    """).fetchall()
    communities = conn.execute(
        "SELECT COUNT(DISTINCT community) FROM v_dld_price_history WHERE segment = 'Ready'").fetchone()[0]
    assert thin == [] and communities == 29


@real_exports
def test_cleaning_reconciles_with_the_raw_count(real):
    _, r = real
    dropped = (r["duplicates_dropped"] + r["non_apartment_dropped"]
               + r["missing_price_or_size_dropped"] + r["price_outliers_dropped"])
    assert r["raw"] - dropped == r["clean"]
