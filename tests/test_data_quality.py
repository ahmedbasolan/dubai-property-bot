"""Data-quality contracts for the DLD-backed database.

These pin the properties the app relies on: prices in a plausible range after
cleaning, series that reconcile with the sales they summarise, and yields and
scores that only exist when the rent data supports them.
"""

import statistics
import sys
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="database missing - run `python src/db_setup.py` first"
)


@pytest.fixture(scope="module")
def conn():
    return duckdb.connect(str(DB_PATH), read_only=True)


def test_price_and_size_are_correlated(conn):
    """Registered prices track unit size; a weak link would mean a unit mix-up
    (sq.m read as sqft) or prices joined to the wrong rows."""
    rows = conn.execute("SELECT price_aed, size_sqft FROM v_net_yield").fetchall()

    assert len(rows) > 10_000
    assert statistics.correlation([r[0] for r in rows], [r[1] for r in rows]) > 0.6


def test_price_per_sqft_stays_plausible(conn):
    """After outlier cleaning, Dubai apartments sit roughly 400-8,000 AED/sqft."""
    p01, p50, p99 = conn.execute(
        "SELECT quantile_cont(price_per_sqft, [0.01, 0.5, 0.99]) FROM v_net_yield"
    ).fetchone()[0]

    assert 300 <= p01, p01
    assert 1_000 <= p50 <= 3_000, p50
    assert p99 <= 8_000, p99


def test_trend_volumes_reconcile_with_ready_sales(conn):
    """/api/trends volume and /api/scores sale count must be the same sales."""
    mismatches = conn.execute(
        """
        SELECT s.community, s.transaction_count, h.volume
        FROM v_community_summary s
        JOIN (SELECT community, SUM(market_volume) AS volume
              FROM price_history GROUP BY community) h USING (community)
        WHERE s.transaction_count <> h.volume
        """
    ).fetchall()

    assert mismatches == []


def test_every_community_has_a_full_series(conn):
    counts = dict(conn.execute(
        "SELECT community, COUNT(*) FROM price_history GROUP BY community"
    ).fetchall())
    communities = conn.execute(
        "SELECT COUNT(DISTINCT community) FROM transactions"
    ).fetchone()[0]

    assert len(counts) == communities
    assert set(counts.values()) == {3}, "every community should have Q1-Q3 2026"


def test_yield_exists_only_with_enough_matched_projects(conn):
    from db_setup import MIN_YIELD_PROJECTS, MIN_YIELD_SAMPLE

    rows = conn.execute(
        "SELECT community, avg_roi_pct, matched_contracts, yield_projects FROM v_investment_scores"
    ).fetchall()
    for community, gross, contracts, projects in rows:
        if gross is not None:
            assert contracts >= MIN_YIELD_SAMPLE, community
            assert projects >= MIN_YIELD_PROJECTS, community
            assert 2 <= gross <= 12, (community, gross)


def test_community_yield_is_the_median_of_its_project_yields(conn):
    """Yield compares rents and sales in the same buildings. Pooling all rents
    against all sales put International City at 11.6% because a third of its
    rents came from one newer tower."""
    check = conn.execute(
        """
        WITH s AS (
            SELECT community, upper(project) AS k, median(price_aed / size_sqm) AS pps
            FROM transactions WHERE handover_status = 'Ready' AND project IS NOT NULL
            GROUP BY ALL HAVING COUNT(*) >= 5
        )
        SELECT round(median(100 * r.rent_per_sqm / s.pps), 2)
        FROM v_project_rent r JOIN s ON s.community = r.community AND s.k = r.project_key
        WHERE r.community = 'International City'
        """
    ).fetchone()[0]
    reported = conn.execute(
        "SELECT avg_roi_pct FROM v_investment_scores WHERE community = 'International City'"
    ).fetchone()[0]

    assert reported == check
    assert reported < 10, "pooled rents vs sales would put it at 11.6%"


def test_score_exists_exactly_when_yield_does(conn):
    """No yield, no score: the composite must never be built without its core factor."""
    bad = conn.execute(
        """SELECT community FROM v_investment_scores
           WHERE (composite_score IS NULL) <> (avg_roi_pct IS NULL)"""
    ).fetchall()

    assert bad == []


def test_momentum_needs_enough_paired_projects(conn):
    from db_setup import MIN_MOMENTUM_PROJECTS

    bad = conn.execute(
        f"""SELECT community FROM v_investment_scores
            WHERE price_momentum_pct IS NOT NULL AND paired_projects < {MIN_MOMENTUM_PROJECTS}"""
    ).fetchall()

    assert bad == []


def test_net_yield_is_gross_less_management_and_vacancy(conn):
    from config import MANAGEMENT_FEE_RATE, VACANCY_RATE

    rows = conn.execute(
        "SELECT avg_roi_pct, avg_net_yield_pct FROM v_investment_scores WHERE avg_roi_pct IS NOT NULL"
    ).fetchall()
    assert rows
    for gross, net in rows:
        assert net == pytest.approx(gross * (1 - MANAGEMENT_FEE_RATE - VACANCY_RATE), abs=0.01)
