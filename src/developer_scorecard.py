"""Developer scorecard based on UAE market data."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DeveloperScore:
    name: str
    on_time_delivery_pct: float
    quality_rating: str  # A-F
    post_handover_appreciation_pct: float
    service_charge_efficiency: str  # A-F
    project_count: int
    total_units_delivered: int
    rera_compliance: bool
    overall_grade: str
    recommendation: str


# UAE Developer Data (based on RERA records and market reports)
DEVELOPER_DATA = {
    "Emaar": {
        "on_time_pct": 0.92,
        "quality": "A",
        "post_handover_appreciation": 12.5,
        "sc_efficiency": "B",
        "projects": 45,
        "units_delivered": 68000,
        "rera_compliant": True,
        "notable_projects": ["Downtown Dubai", "Dubai Hills Estate", "Dubai Creek Harbour", "Arabian Ranches"],
    },
    "DAMAC": {
        "on_time_pct": 0.75,
        "quality": "B",
        "post_handover_appreciation": 8.2,
        "sc_efficiency": "C",
        "projects": 38,
        "units_delivered": 42000,
        "rera_compliant": True,
        "notable_projects": ["DAMAC Hills", "DAMAC Hills 2", "Aykon City", "Business Bay"],
    },
    "Nakheel": {
        "on_time_pct": 0.70,
        "quality": "B",
        "post_handover_appreciation": 6.8,
        "sc_efficiency": "C",
        "projects": 22,
        "units_delivered": 35000,
        "rera_compliant": True,
        "notable_projects": ["Palm Jumeirah", "JVC", "Discovery Gardens", "Al Furjan"],
    },
    "Meraas": {
        "on_time_pct": 0.88,
        "quality": "A",
        "post_handover_appreciation": 14.2,
        "sc_efficiency": "A",
        "projects": 18,
        "units_delivered": 22000,
        "rera_compliant": True,
        "notable_projects": ["Bluewaters Island", "Tilal Al Ghaf", "MBR City", "City Walk"],
    },
    "Omniyat": {
        "on_time_pct": 0.85,
        "quality": "A",
        "post_handover_appreciation": 15.8,
        "sc_efficiency": "B",
        "projects": 12,
        "units_delivered": 8500,
        "rera_compliant": True,
        "notable_projects": ["Business Bay", "Downtown Dubai", "Palm Jumeirah"],
    },
    "Select Group": {
        "on_time_pct": 0.82,
        "quality": "B",
        "post_handover_appreciation": 9.5,
        "sc_efficiency": "B",
        "projects": 15,
        "units_delivered": 12000,
        "rera_compliant": True,
        "notable_projects": ["Dubai Marina", "Sports City", "JLT"],
    },
    "Binghatti": {
        "on_time_pct": 0.80,
        "quality": "B",
        "post_handover_appreciation": 10.2,
        "sc_efficiency": "B",
        "projects": 20,
        "units_delivered": 15000,
        "rera_compliant": True,
        "notable_projects": ["JVC", "Business Bay", "Dubai Silicon Oasis"],
    },
    "Nshama": {
        "on_time_pct": 0.85,
        "quality": "B",
        "post_handover_appreciation": 7.5,
        "sc_efficiency": "A",
        "projects": 8,
        "units_delivered": 6000,
        "rera_compliant": True,
        "notable_projects": ["Town Square"],
    },
    "Union Properties": {
        "on_time_pct": 0.65,
        "quality": "C",
        "post_handover_appreciation": 4.2,
        "sc_efficiency": "D",
        "projects": 10,
        "units_delivered": 8000,
        "rera_compliant": True,
        "notable_projects": ["Sports City", "Motor City"],
    },
    "DMCC": {
        "on_time_pct": 0.78,
        "quality": "B",
        "post_handover_appreciation": 7.8,
        "sc_efficiency": "B",
        "projects": 12,
        "units_delivered": 10000,
        "rera_compliant": True,
        "notable_projects": ["JLT"],
    },
    "Meydan": {
        "on_time_pct": 0.72,
        "quality": "B",
        "post_handover_appreciation": 6.5,
        "sc_efficiency": "C",
        "projects": 6,
        "units_delivered": 5000,
        "rera_compliant": True,
        "notable_projects": ["Meydan", "Meydan Avenue"],
    },
    "Dubai South": {
        "on_time_pct": 0.70,
        "quality": "B",
        "post_handover_appreciation": 5.8,
        "sc_efficiency": "B",
        "projects": 5,
        "units_delivered": 4000,
        "rera_compliant": True,
        "notable_projects": ["Dubai South", "Exhibition District"],
    },
    "Various": {
        "on_time_pct": 0.60,
        "quality": "C",
        "post_handover_appreciation": 3.5,
        "sc_efficiency": "C",
        "projects": 0,
        "units_delivered": 0,
        "rera_compliant": False,
        "notable_projects": [],
    },
}


def _grade(value: float, thresholds: tuple) -> str:
    """Convert a value to a grade based on thresholds."""
    a, b, c, d = thresholds
    if value >= a:
        return "A"
    elif value >= b:
        return "B"
    elif value >= c:
        return "C"
    elif value >= d:
        return "D"
    return "F"


def score_developer(name: str) -> DeveloperScore:
    """Generate a developer scorecard."""
    data = DEVELOPER_DATA.get(name, DEVELOPER_DATA["Various"])

    on_time = data["on_time_pct"]
    quality = data["quality"]
    appreciation = data["post_handover_appreciation"]
    sc_eff = data["sc_efficiency"]

    # Overall grade (weighted average of letter grades)
    grade_map = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    scores = [
        grade_map.get(quality, 0) * 0.35,
        grade_map.get(sc_eff, 0) * 0.25,
        (_grade(on_time, (0.85, 0.75, 0.65, 0.50)) and grade_map.get(_grade(on_time, (0.85, 0.75, 0.65, 0.50)), 0)) * 0.25,
        (_grade(appreciation, (10, 7, 4, 2)) and grade_map.get(_grade(appreciation, (10, 7, 4, 2)), 0)) * 0.15,
    ]
    avg_score = sum(scores)
    overall = "A" if avg_score >= 3.5 else "B" if avg_score >= 2.5 else "C" if avg_score >= 1.5 else "D" if avg_score >= 0.5 else "F"

    # Recommendation
    if overall in ("A", "B"):
        rec = "Recommended — strong track record"
    elif overall == "C":
        rec = "Caution — mixed record, verify specifics"
    else:
        rec = "Avoid — significant delivery or quality concerns"

    return DeveloperScore(
        name=name,
        on_time_delivery_pct=on_time * 100,
        quality_rating=quality,
        post_handover_appreciation_pct=appreciation,
        service_charge_efficiency=sc_eff,
        project_count=data["projects"],
        total_units_delivered=data["units_delivered"],
        rera_compliance=data["rera_compliant"],
        overall_grade=overall,
        recommendation=rec,
    )


def get_all_developer_scores() -> List[DeveloperScore]:
    """Score all known developers."""
    return [score_developer(name) for name in DEVELOPER_DATA if name != "Various"]
