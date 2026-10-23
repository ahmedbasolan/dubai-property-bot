"""Quarterly price trends, read from DuckDB.

The series is the `price_history` view: median AED/sqft of ready apartments
per community and quarter, from DLD registered sales, with the quarter's sale
count as volume. Two change figures are reported:

* `change_pct` - first to latest quarter on community medians. Easy to read,
  but it moves with which buildings happened to sell.
* `momentum_pct` - the median change of the *same projects* between those
  quarters (`v_price_momentum`), which removes that mix effect. Gainers are
  ranked on it. None when fewer than 5 projects sold in both quarters.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import duckdb

from config import DB_PATH

SOURCE = "dld:price_history"

BASIS = (
    "Median AED/sqft of ready apartments registered with DLD each quarter, "
    "Q1-Q3 2026; volume is the count of those sales. Momentum compares the same "
    "projects across quarters, so it isn't skewed by which buildings sold."
)


@dataclass
class PriceTrend:
    community: str
    quarters: List[str]
    prices: List[float]  # median price per sqft, ready apartments
    volumes: List[int]  # ready sales registered in the quarter
    change_pct: float  # first -> latest quarter, community medians
    momentum_pct: Optional[float]  # same-project change; None if too few projects
    trend_direction: str  # "up", "down", "stable", from momentum when known


_conn = duckdb.connect(str(DB_PATH), read_only=True)
_table_checked = False
_has_table = False


def _has_price_history() -> bool:
    global _table_checked, _has_table
    if not _table_checked:
        _has_table = bool(
            _conn.cursor().execute(
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
        for row in _conn.cursor().execute(
            "SELECT DISTINCT community FROM price_history ORDER BY community"
        ).fetchall()
    ]


def get_price_trend(community: str) -> PriceTrend:
    """Get the quarterly price series for one community."""
    if not _has_price_history():
        return PriceTrend(community, [], [], [], 0.0, None, "stable")

    rows = _conn.cursor().execute(
        """
        SELECT community, quarter, avg_price_per_sqft, market_volume
        FROM price_history
        WHERE lower(community) = lower(?)
        ORDER BY quarter_start
        """,
        [community],
    ).fetchall()

    if not rows:
        return PriceTrend(community, [], [], [], 0.0, None, "stable")

    name = rows[0][0]
    quarters = [r[1] for r in rows]
    prices = [float(r[2]) for r in rows]
    volumes = [int(r[3]) for r in rows]

    # Only Q1-Q3 2026 exist (the DLD gateway serves the current year), so a
    # year-on-year figure isn't possible; report first -> latest quarter.
    change = ((prices[-1] - prices[0]) / prices[0]) * 100 if len(prices) >= 2 and prices[0] else 0.0

    momentum_row = _conn.cursor().execute(
        "SELECT price_momentum_pct FROM v_price_momentum WHERE lower(community) = lower(?)",
        [community],
    ).fetchone()
    momentum = float(momentum_row[0]) if momentum_row and momentum_row[0] is not None else None

    basis = momentum if momentum is not None else change
    trend = "up" if basis > 2 else "down" if basis < -2 else "stable"

    return PriceTrend(
        community=name,
        quarters=quarters,
        prices=prices,
        volumes=volumes,
        change_pct=round(change, 1),
        momentum_pct=momentum,
        trend_direction=trend,
    )


def get_all_trends() -> Dict[str, PriceTrend]:
    """Get trends for every community that has a series."""
    return {comm: get_price_trend(comm) for comm in list_trend_communities()}


def get_top_gainers(n: int = 5) -> List[PriceTrend]:
    """Top N communities by same-project price momentum (unknown momentum excluded)."""
    trends = [t for t in get_all_trends().values() if t.momentum_pct is not None]
    return sorted(trends, key=lambda t: t.momentum_pct, reverse=True)[:n]


def get_top_volume(n: int = 5) -> List[PriceTrend]:
    """Get top N communities by ready sales registered."""
    trends = get_all_trends()
    sorted_trends = sorted(
        trends.values(), key=lambda t: sum(t.volumes), reverse=True
    )
    return sorted_trends[:n]
