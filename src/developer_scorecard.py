"""Developer scorecards, derived from the community scoring view.

The previous version hardcoded on-time delivery rates, post-handover
appreciation, unit counts and RERA flags with no source, and those figures
contradicted the transaction data (and the community scores). This version
aggregates `v_investment_scores` by master developer, so a developer's grade is
a transaction-weighted average of its communities' actual scores and the
recommendation uses the same INVEST/HOLD/AVOID bands.

Only metrics the dataset can support are reported: no delivery, appreciation or
RERA claims.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import duckdb

from config import DB_PATH

SOURCE = "duckdb:v_investment_scores"
BASIS = (
    "Transaction-weighted average of community metrics and grades. Covers only "
    "communities in this dataset; delivery timeliness, appreciation and RERA "
    "standing are not in the data and are not reported."
)


@dataclass
class DeveloperScore:
    name: str
    communities: List[str]
    community_count: int
    transaction_count: int
    avg_price_per_sqft: float
    avg_roi_pct: float
    avg_net_yield_pct: float
    avg_service_charge: float
    avg_occupancy_rate: float
    avg_pipeline_pct: float
    yield_grade: str
    net_yield_grade: str
    service_charge_grade: str
    supply_grade: str
    occupancy_grade: str
    composite_score: float
    overall_grade: str
    recommendation: str


# Thresholds mirror the CASE expressions in db_setup.py's v_investment_scores.
def _grade_high(value: float, a: float, b: float, c: float, d: float) -> str:
    if value >= a:
        return "A"
    if value >= b:
        return "B"
    if value >= c:
        return "C"
    if value >= d:
        return "D"
    return "F"


def _grade_low(value: float, a: float, b: float, c: float, d: float) -> str:
    if value <= a:
        return "A"
    if value <= b:
        return "B"
    if value <= c:
        return "C"
    if value <= d:
        return "D"
    return "F"


def _overall_grade(composite: float) -> str:
    if composite >= 80:
        return "A"
    if composite >= 70:
        return "B"
    if composite >= 60:
        return "C"
    if composite >= 50:
        return "D"
    return "F"


def _recommendation(composite: float) -> str:
    if composite >= 70:
        return "INVEST"
    if composite >= 50:
        return "HOLD"
    return "AVOID"


_QUERY = """
    SELECT
        master_developer AS name,
        LIST(community ORDER BY community) AS communities,
        COUNT(*) AS community_count,
        SUM(transaction_count) AS transaction_count,
        ROUND(SUM(avg_price_per_sqft * transaction_count) / SUM(transaction_count)) AS avg_price_per_sqft,
        ROUND(SUM(avg_roi_pct * transaction_count) / SUM(transaction_count), 1) AS avg_roi_pct,
        ROUND(SUM(avg_net_yield_pct * transaction_count) / SUM(transaction_count), 2) AS avg_net_yield_pct,
        ROUND(SUM(avg_service_charge * transaction_count) / SUM(transaction_count), 1) AS avg_service_charge,
        ROUND(SUM(occupancy_rate * transaction_count) / SUM(transaction_count), 3) AS avg_occupancy_rate,
        ROUND(SUM(pipeline_pct_of_stock * transaction_count) / SUM(transaction_count), 1) AS avg_pipeline_pct,
        ROUND(SUM(composite_score * transaction_count) / SUM(transaction_count), 0) AS composite_score
    FROM v_investment_scores
    WHERE master_developer IS NOT NULL AND master_developer <> 'Various'
    GROUP BY master_developer
    ORDER BY composite_score DESC, name
"""


def get_all_developer_scores() -> List[DeveloperScore]:
    """Score every master developer represented in the dataset."""
    try:
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        rows = conn.execute(_QUERY).fetchall()
    except duckdb.Error:
        # A database built before the scoring view existed should page empty,
        # not 500 the API.
        return []

    scores: List[DeveloperScore] = []
    for row in rows:
        (
            name,
            communities,
            community_count,
            transaction_count,
            avg_ppsf,
            avg_roi,
            avg_net_yield,
            avg_service_charge,
            avg_occupancy,
            avg_pipeline,
            composite,
        ) = row

        composite = float(composite)
        scores.append(
            DeveloperScore(
                name=name,
                communities=list(communities or []),
                community_count=int(community_count),
                transaction_count=int(transaction_count),
                avg_price_per_sqft=float(avg_ppsf),
                avg_roi_pct=float(avg_roi),
                avg_net_yield_pct=float(avg_net_yield),
                avg_service_charge=float(avg_service_charge),
                avg_occupancy_rate=float(avg_occupancy),
                avg_pipeline_pct=float(avg_pipeline),
                yield_grade=_grade_high(float(avg_roi), 8.5, 7.0, 6.0, 5.0),
                net_yield_grade=_grade_high(float(avg_net_yield), 7.0, 5.5, 4.0, 2.5),
                service_charge_grade=_grade_low(
                    float(avg_service_charge), 10.0, 15.0, 20.0, 25.0
                ),
                supply_grade=_grade_low(
                    float(avg_pipeline), 5.0, 10.0, 15.0, 25.0
                ),
                occupancy_grade=_grade_high(
                    float(avg_occupancy), 0.92, 0.88, 0.84, 0.80
                ),
                composite_score=composite,
                overall_grade=_overall_grade(composite),
                recommendation=_recommendation(composite),
            )
        )
    return scores


def score_developer(name: str) -> Optional[DeveloperScore]:
    """Look up one developer's scorecard, or None if it is not in the dataset."""
    for score in get_all_developer_scores():
        if score.name.lower() == name.lower():
            return score
    return None
