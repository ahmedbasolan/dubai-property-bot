"""Price trend data and historical analysis."""

import random
from dataclasses import dataclass
from typing import List, Dict, Tuple


@dataclass
class PriceTrend:
    community: str
    quarters: List[str]
    prices: List[float]  # avg price per sqft
    volumes: List[int]  # transaction count
    yoy_change_pct: float
    trend_direction: str  # "up", "down", "stable"


# Historical price data (mock, based on Dubai market patterns 2022-2024)
# Format: community -> list of (quarter, avg_price_per_sqft, transaction_volume)
HISTORICAL_DATA = {
    "Downtown Dubai": [
        ("Q1 2022", 1950, 180), ("Q2 2022", 2050, 195), ("Q3 2022", 2100, 170),
        ("Q4 2022", 2180, 200), ("Q1 2023", 2280, 210), ("Q2 2023", 2350, 225),
        ("Q3 2023", 2400, 190), ("Q4 2023", 2500, 230), ("Q1 2024", 2600, 245),
    ],
    "Dubai Marina": [
        ("Q1 2022", 1500, 220), ("Q2 2022", 1580, 240), ("Q3 2022", 1620, 200),
        ("Q4 2022", 1700, 250), ("Q1 2023", 1780, 260), ("Q2 2023", 1850, 275),
        ("Q3 2023", 1900, 230), ("Q4 2023", 1980, 280), ("Q1 2024", 2050, 290),
    ],
    "Palm Jumeirah": [
        ("Q1 2022", 2800, 60), ("Q2 2022", 2950, 65), ("Q3 2022", 3100, 55),
        ("Q4 2022", 3250, 70), ("Q1 2023", 3400, 75), ("Q2 2023", 3550, 80),
        ("Q3 2023", 3650, 65), ("Q4 2023", 3800, 85), ("Q1 2024", 3950, 90),
    ],
    "Dubai Hills Estate": [
        ("Q1 2022", 1200, 150), ("Q2 2022", 1280, 165), ("Q3 2022", 1350, 140),
        ("Q4 2022", 1420, 175), ("Q1 2023", 1500, 185), ("Q2 2023", 1580, 195),
        ("Q3 2023", 1650, 160), ("Q4 2023", 1720, 200), ("Q1 2024", 1800, 210),
    ],
    "JVC (Jumeirah Village Circle)": [
        ("Q1 2022", 900, 180), ("Q2 2022", 980, 200), ("Q3 2022", 1050, 170),
        ("Q4 2022", 1120, 210), ("Q1 2023", 1200, 225), ("Q2 2023", 1280, 240),
        ("Q3 2023", 1350, 200), ("Q4 2023", 1420, 250), ("Q1 2024", 1500, 260),
    ],
    "Business Bay": [
        ("Q1 2022", 1300, 120), ("Q2 2022", 1380, 135), ("Q3 2022", 1420, 110),
        ("Q4 2022", 1500, 140), ("Q1 2023", 1580, 150), ("Q2 2023", 1650, 160),
        ("Q3 2023", 1700, 130), ("Q4 2023", 1780, 165), ("Q1 2024", 1850, 175),
    ],
    "Arabian Ranches": [
        ("Q1 2022", 1100, 45), ("Q2 2022", 1150, 50), ("Q3 2022", 1180, 40),
        ("Q4 2022", 1220, 55), ("Q1 2023", 1280, 60), ("Q2 2023", 1320, 65),
        ("Q3 2023", 1350, 50), ("Q4 2023", 1400, 70), ("Q1 2024", 1450, 75),
    ],
    "Sports City": [
        ("Q1 2022", 750, 90), ("Q2 2022", 800, 100), ("Q3 2022", 830, 85),
        ("Q4 2022", 870, 105), ("Q1 2023", 920, 110), ("Q2 2023", 960, 115),
        ("Q3 2023", 1000, 95), ("Q4 2023", 1040, 120), ("Q1 2024", 1080, 125),
    ],
    "Discovery Gardens": [
        ("Q1 2022", 650, 70), ("Q2 2022", 690, 80), ("Q3 2022", 720, 65),
        ("Q4 2022", 760, 85), ("Q1 2023", 800, 90), ("Q2 2023", 840, 95),
        ("Q3 2023", 870, 75), ("Q4 2023", 910, 100), ("Q1 2024", 950, 105),
    ],
    "JLT (Jumeirah Lake Towers)": [
        ("Q1 2022", 950, 130), ("Q2 2022", 1010, 145), ("Q3 2022", 1050, 120),
        ("Q4 2022", 1110, 150), ("Q1 2023", 1170, 160), ("Q2 2023", 1230, 170),
        ("Q3 2023", 1280, 140), ("Q4 2023", 1340, 175), ("Q1 2024", 1400, 185),
    ],
    "The Springs": [
        ("Q1 2022", 1050, 35), ("Q2 2022", 1090, 40), ("Q3 2022", 1120, 30),
        ("Q4 2022", 1160, 42), ("Q1 2023", 1200, 45), ("Q2 2023", 1240, 48),
        ("Q3 2023", 1270, 38), ("Q4 2023", 1310, 50), ("Q1 2024", 1350, 52),
    ],
    "Al Barsha": [
        ("Q1 2022", 850, 80), ("Q2 2022", 900, 90), ("Q3 2022", 930, 75),
        ("Q4 2022", 970, 95), ("Q1 2023", 1020, 100), ("Q2 2023", 1060, 105),
        ("Q3 2023", 1100, 85), ("Q4 2023", 1140, 110), ("Q1 2024", 1180, 115),
    ],
    "Deira": [
        ("Q1 2022", 600, 60), ("Q2 2022", 630, 65), ("Q3 2022", 650, 55),
        ("Q4 2022", 680, 70), ("Q1 2023", 710, 75), ("Q2 2023", 740, 80),
        ("Q3 2023", 760, 65), ("Q4 2023", 790, 85), ("Q1 2024", 820, 90),
    ],
    "Bur Dubai": [
        ("Q1 2022", 720, 55), ("Q2 2022", 760, 60), ("Q3 2022", 790, 50),
        ("Q4 2022", 830, 65), ("Q1 2023", 870, 70), ("Q2 2023", 910, 75),
        ("Q3 2023", 940, 60), ("Q4 2023", 980, 80), ("Q1 2024", 1020, 85),
    ],
    "International City": [
        ("Q1 2022", 420, 100), ("Q2 2022", 450, 110), ("Q3 2022", 470, 90),
        ("Q4 2022", 500, 115), ("Q1 2023", 530, 120), ("Q2 2023", 560, 130),
        ("Q3 2023", 580, 105), ("Q4 2023", 610, 135), ("Q1 2024", 640, 140),
    ],
    "Dubai Silicon Oasis": [
        ("Q1 2022", 550, 75), ("Q2 2022", 590, 85), ("Q3 2022", 620, 70),
        ("Q4 2022", 660, 90), ("Q1 2023", 700, 95), ("Q2 2023", 740, 100),
        ("Q3 2023", 770, 80), ("Q4 2023", 810, 105), ("Q1 2024", 850, 110),
    ],
    "Tilal Al Ghaf": [
        ("Q1 2022", 1300, 40), ("Q2 2022", 1380, 45), ("Q3 2022", 1450, 38),
        ("Q4 2022", 1520, 48), ("Q1 2023", 1600, 52), ("Q2 2023", 1680, 55),
        ("Q3 2023", 1740, 45), ("Q4 2023", 1820, 58), ("Q1 2024", 1900, 62),
    ],
    "DAMAC Hills 2": [
        ("Q1 2022", 680, 95), ("Q2 2022", 730, 105), ("Q3 2022", 770, 85),
        ("Q4 2022", 820, 110), ("Q1 2023", 870, 120), ("Q2 2023", 920, 130),
        ("Q3 2023", 960, 100), ("Q4 2023", 1010, 135), ("Q1 2024", 1060, 140),
    ],
    "Dubai Creek Harbour": [
        ("Q1 2022", 1100, 80), ("Q2 2022", 1180, 90), ("Q3 2022", 1240, 75),
        ("Q4 2022", 1320, 95), ("Q1 2023", 1400, 100), ("Q2 2023", 1480, 110),
        ("Q3 2023", 1540, 85), ("Q4 2023", 1620, 115), ("Q1 2024", 1700, 120),
    ],
    "Bluewaters Island": [
        ("Q1 2022", 2200, 30), ("Q2 2022", 2320, 35), ("Q3 2022", 2400, 28),
        ("Q4 2022", 2520, 38), ("Q1 2023", 2640, 40), ("Q2 2023", 2750, 42),
        ("Q3 2023", 2830, 35), ("Q4 2023", 2960, 45), ("Q1 2024", 3100, 48),
    ],
    "Meydan": [
        ("Q1 2022", 900, 50), ("Q2 2022", 960, 55), ("Q3 2022", 1010, 45),
        ("Q4 2022", 1070, 58), ("Q1 2023", 1130, 62), ("Q2 2023", 1190, 65),
        ("Q3 2023", 1240, 52), ("Q4 2023", 1300, 68), ("Q1 2024", 1360, 72),
    ],
    "Al Furjan": [
        ("Q1 2022", 820, 65), ("Q2 2022", 870, 72), ("Q3 2022", 910, 60),
        ("Q4 2022", 960, 78), ("Q1 2023", 1010, 82), ("Q2 2023", 1060, 88),
        ("Q3 2023", 1100, 72), ("Q4 2023", 1150, 92), ("Q1 2024", 1200, 96),
    ],
    "Dubai South": [
        ("Q1 2022", 580, 80), ("Q2 2022", 630, 90), ("Q3 2022", 670, 75),
        ("Q4 2022", 720, 95), ("Q1 2023", 770, 100), ("Q2 2023", 820, 110),
        ("Q3 2023", 860, 85), ("Q4 2023", 910, 115), ("Q1 2024", 960, 120),
    ],
    "Town Square": [
        ("Q1 2022", 550, 85), ("Q2 2022", 590, 95), ("Q3 2022", 620, 80),
        ("Q4 2022", 660, 100), ("Q1 2023", 700, 105), ("Q2 2023", 740, 115),
        ("Q3 2023", 770, 90), ("Q4 2023", 810, 120), ("Q1 2024", 850, 125),
    ],
}


def get_price_trend(community: str) -> PriceTrend:
    """Get price trend data for a community."""
    data = HISTORICAL_DATA.get(community, [])
    if not data:
        return PriceTrend(
            community=community, quarters=[], prices=[], volumes=[],
            yoy_change_pct=0, trend_direction="stable"
        )

    quarters = [d[0] for d in data]
    prices = [d[1] for d in data]
    volumes = [d[2] for d in data]

    # YoY change (Q1 2024 vs Q1 2023)
    if len(prices) >= 5:
        yoy = ((prices[-1] - prices[-5]) / prices[-5]) * 100
    else:
        yoy = 0

    # Trend direction
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
        community=community,
        quarters=quarters,
        prices=prices,
        volumes=volumes,
        yoy_change_pct=round(yoy, 1),
        trend_direction=trend,
    )


def get_all_trends() -> Dict[str, PriceTrend]:
    """Get trends for all communities."""
    return {comm: get_price_trend(comm) for comm in HISTORICAL_DATA.keys()}


def get_top_gainers(n: int = 5) -> List[PriceTrend]:
    """Get top N communities by YoY price appreciation."""
    trends = get_all_trends()
    sorted_trends = sorted(trends.values(), key=lambda t: t.yoy_change_pct, reverse=True)
    return sorted_trends[:n]


def get_top_volume(n: int = 5) -> List[PriceTrend]:
    """Get top N communities by transaction volume."""
    trends = get_all_trends()
    sorted_trends = sorted(trends.values(), key=lambda t: t.volumes[-1] if t.volumes else 0, reverse=True)
    return sorted_trends[:n]
