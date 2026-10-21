"""Data-quality contracts for the generated dataset.

These pin the two defects found in the review: price and size were drawn
independently (AED/sqft spanned 612-11,452), and `/trends` reported different
AED/sqft from `/api/scores` because it came from a separate hardcoded table.
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
    not DB_PATH.exists(), reason="database missing - run `make setup` first"
)


@pytest.fixture(scope="module")
def conn():
    return duckdb.connect(str(DB_PATH), read_only=True)


def test_price_and_size_are_correlated(conn):
    """Price is the driver and size is derived from it.

    With independent draws the correlation was ~0.51; deriving size through the
    community's price density puts it well above 0.9.
    """
    rows = conn.execute("SELECT price_aed, size_sqft FROM v_net_yield").fetchall()
    prices = [r[0] for r in rows]
    sizes = [r[1] for r in rows]

    assert len(rows) > 20
    assert statistics.correlation(prices, sizes) > 0.85


def test_price_per_sqft_stays_plausible(conn):
    low, high = conn.execute(
        "SELECT MIN(price_per_sqft), MAX(price_per_sqft) FROM v_net_yield"
    ).fetchone()

    assert 600 <= low, f"lowest AED/sqft is {low}"
    assert high <= 4000, f"highest AED/sqft is {high}"


def test_price_per_sqft_is_stable_within_a_community(conn):
    """A community's transactions should trade in a similar density band."""
    rows = conn.execute(
        """
        SELECT community, MIN(price_per_sqft), MAX(price_per_sqft)
        FROM v_net_yield
        GROUP BY community
        """
    ).fetchall()

    for community, low, high in rows:
        assert high <= low * 2.0, f"{community}: {low} - {high} AED/sqft"


def test_latest_trend_quarter_matches_the_scores(conn):
    """/trends and /api/scores must report the same current AED/sqft."""
    mismatches = conn.execute(
        """
        SELECT s.community, s.avg_price_per_sqft, h.avg_price_per_sqft
        FROM v_community_summary s
        JOIN price_history h ON h.community = s.community
        WHERE h.quarter_start = (SELECT MAX(quarter_start) FROM price_history)
          AND s.avg_price_per_sqft <> h.avg_price_per_sqft
        """
    ).fetchall()

    assert mismatches == []


def test_every_community_has_a_usable_series(conn):
    counts = conn.execute(
        "SELECT community, COUNT(*) FROM price_history GROUP BY community"
    ).fetchall()
    communities = conn.execute(
        "SELECT COUNT(DISTINCT community) FROM transactions"
    ).fetchone()[0]

    assert len(counts) == communities
    # At least five points are needed for the year-on-year comparison.
    assert {count for _, count in counts} and min(c for _, c in counts) >= 5
    assert len({count for _, count in counts}) == 1, "series lengths differ"


def test_developer_score_is_bounded_by_its_communities(conn):
    from developer_scorecard import get_all_developer_scores

    developers = get_all_developer_scores()
    assert developers

    for developer in developers:
        composites = [
            row[0]
            for row in conn.execute(
                "SELECT composite_score FROM v_investment_scores WHERE master_developer = ?",
                [developer.name],
            ).fetchall()
        ]

        assert composites, developer.name
        # Weighted average, rounded to a whole point.
        assert min(composites) - 1 <= developer.composite_score <= max(composites) + 1


def test_developer_counts_reconcile_with_scorecards(conn):
    """The chat's developer totals and the scorecards must agree.

    "Various" communities used to draw from a pool that included the master
    developers, so Emaar and Nakheel showed 18 transactions by
    `transactions.developer` and 16 in their scorecards.
    """
    from developer_scorecard import get_all_developer_scores

    for developer in get_all_developer_scores():
        raw = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE developer = ?", [developer.name]
        ).fetchone()[0]
        assert raw == developer.transaction_count, (
            f"{developer.name}: {raw} rows name the developer, "
            f"but the scorecard counts {developer.transaction_count} community transactions"
        )
