"""Quarterly price trends, read from DuckDB.

The series lives in the `price_history` table produced by `generate_data.py`.
Its latest point is the same average AED/sqft that `v_community_summary`
reports, so `/api/trends` cannot contradict `/api/scores`.

Two things are modelled rather than observed, and both are labelled as such
here and in the UI:

* Earlier quarters are walked backwards from the anchor with a 2022-2024
  growth curve and a per-community dispersion factor.
* `market_volume` is derived from stock turnover (`supply_pipeline`), not from
  a count of the 73 sampled transactions.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

import duckdb

from config import DB_PATH

SOURCE = "duckdb:price_history"

BASIS = (
    "Latest quarter is the sample's average AED/sqft (the same value /api/scores "
    "reports). Earlier quarters are modelled with a 2022-2024 growth curve; "
    "volume is modelled from stock turnover, not a count of the 73 transactions."
)


@dataclass
class PriceTrend:
    community: str
    quarters: List[str]
    prices: List[float]  # avg price per sqft
    volumes: List[int]  # market transaction volume (modelled)
    yoy_change_pct: float
    trend_direction: str  # "up", "down", "stable"


_conn = duckdb.connect(str(DB_PATH), read_only=True)
_table_checked = False
_has_table = False


def _has_price_history() -> bool:
    global _table_checked, _has_table
    if not _table_checked:
        _has_table = bool(
            _conn.execute(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'price_history'
                """
            ).fetchone()[0]
        )
        _table_checked = True
    return _has_table


def list_trend_communities() -> List[str]:
    """Communities that have a price series, alphabetically."""
    if not _has_price_history():
        return []
    return [
        row[0]
        for row in _conn.execute(
            "SELECT DISTINCT community FROM price_history ORDER BY community"
        ).fetchall()
    ]


def get_price_trend(community: str) -> PriceTrend:
    """Get the quarterly price series for one community."""
    if not _has_price_history():
        return PriceTrend(community, [], [], [], 0.0, "stable")

    rows = _conn.execute(
        """
        SELECT community, quarter, avg_price_per_sqft, market_volume
        FROM price_history
        WHERE lower(community) = lower(?)
        ORDER BY quarter_start
        """,
        [community],
    ).fetchall()

    if not rows:
        return PriceTrend(community, [], [], [], 0.0, "stable")

    name = rows[0][0]
    quarters = [r[1] for r in rows]
    prices = [float(r[2]) for r in rows]
    volumes = [int(r[3]) for r in rows]

    # Year on year: the latest quarter against the same quarter a year earlier
    # (four points back in a quarterly series), not against the prior quarter.
    if len(prices) >= 5 and prices[-5]:
        yoy = ((prices[-1] - prices[-5]) / prices[-5]) * 100
    else:
        yoy = 0.0

    if len(prices) >= 3:
        recent = prices[-3:]
        if recent[-1] > recent[0] * 1.02:
            trend = "up"
        elif recent[-1] < recent[0] * 0.98:
            trend = "down"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return PriceTrend(
        community=name,
        quarters=quarters,
        prices=prices,
        volumes=volumes,
        yoy_change_pct=round(yoy, 1),
        trend_direction=trend,
    )


def get_all_trends() -> Dict[str, PriceTrend]:
    """Get trends for every community that has a series."""
    return {comm: get_price_trend(comm) for comm in list_trend_communities()}


def get_top_gainers(n: int = 5) -> List[PriceTrend]:
    """Get top N communities by YoY price appreciation."""
    trends = get_all_trends()
    sorted_trends = sorted(trends.values(), key=lambda t: t.yoy_change_pct, reverse=True)
    return sorted_trends[:n]


def get_top_volume(n: int = 5) -> List[PriceTrend]:
    """Get top N communities by modelled market volume."""
    trends = get_all_trends()
    sorted_trends = sorted(
        trends.values(), key=lambda t: sum(t.volumes), reverse=True
    )
    return sorted_trends[:n]
