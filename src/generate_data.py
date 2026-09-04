"""Generate realistic mock data for Dubai property transactions.

Includes 7 additional fields: floor_level, view_type, service_charge_aed_sqft,
parking_spots, completion_year, furnishing, amenities.
"""

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Community profiles with realistic field distributions
COMMUNITY_PROFILES = {
    "Downtown Dubai": {
        "district": "Central",
        "established": 2009,
        "developer_master": "Emaar",
        "price_range": (1200000, 8500000),
        "sqft_range": (600, 3500),
        "roi_range": (5.5, 7.5),
        "service_charge": (18, 30),
        "floor_range": (5, 65),
        "views": ["burj_khalifa", "fountain", "community", "road"],
        "view_weights": [0.3, 0.25, 0.3, 0.15],
        "parking": {0: 0.05, 1: 0.55, 2: 0.40},
        "completion_range": (2009, 2024),
        "furnishing": {"furnished": 0.35, "unfurnished": 0.45, "semi": 0.20},
        "amenities_pool": ["pool", "gym", "concierge", "spa", "kids_play", "bbq", "retail"],
        "amenities_count": (4, 7),
        "occupancy": 0.92,
        "off_plan_pct": 0.15,
    },
    "Dubai Marina": {
        "district": "Marina",
        "established": 2006,
        "developer_master": "Various",
        "price_range": (900000, 3500000),
        "sqft_range": (400, 2200),
        "roi_range": (6.5, 8.0),
        "service_charge": (14, 25),
        "floor_range": (3, 55),
        "views": ["sea", "marina", "community", "road"],
        "view_weights": [0.25, 0.30, 0.30, 0.15],
        "parking": {0: 0.10, 1: 0.60, 2: 0.30},
        "completion_range": (2006, 2023),
        "furnishing": {"furnished": 0.40, "unfurnished": 0.35, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "concierge", "bbq", "kids_play", "beach_access"],
        "amenities_count": (3, 6),
        "occupancy": 0.89,
        "off_plan_pct": 0.10,
    },
    "Palm Jumeirah": {
        "district": "Palm",
        "established": 2006,
        "developer_master": "Nakheel",
        "price_range": (3000000, 15000000),
        "sqft_range": (1500, 8000),
        "roi_range": (4.5, 6.0),
        "service_charge": (20, 35),
        "floor_range": (1, 12),
        "views": ["sea", "burj_khalifa", "atlantis", "community"],
        "view_weights": [0.45, 0.10, 0.15, 0.30],
        "parking": {0: 0.0, 1: 0.30, 2: 0.50, 3: 0.20},
        "completion_range": (2006, 2024),
        "furnishing": {"furnished": 0.50, "unfurnished": 0.30, "semi": 0.20},
        "amenities_pool": ["pool", "gym", "private_beach", "concierge", "spa", "valet", "kids_play"],
        "amenities_count": (4, 7),
        "occupancy": 0.88,
        "off_plan_pct": 0.20,
    },
    "Dubai Hills Estate": {
        "district": "Dubai Hills",
        "established": 2016,
        "developer_master": "Emaar",
        "price_range": (1000000, 3500000),
        "sqft_range": (550, 2000),
        "roi_range": (6.5, 7.8),
        "service_charge": (12, 20),
        "floor_range": (2, 25),
        "views": ["golf", "community", "park", "road"],
        "view_weights": [0.20, 0.35, 0.25, 0.20],
        "parking": {0: 0.05, 1: 0.65, 2: 0.30},
        "completion_range": (2018, 2025),
        "furnishing": {"furnished": 0.15, "unfurnished": 0.60, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "bbq", "retail", "park"],
        "amenities_count": (3, 6),
        "occupancy": 0.88,
        "off_plan_pct": 0.40,
    },
    "JVC (Jumeirah Village Circle)": {
        "district": "JVC",
        "established": 2013,
        "developer_master": "Nakheel",
        "price_range": (400000, 1400000),
        "sqft_range": (350, 900),
        "roi_range": (8.0, 10.0),
        "service_charge": (8, 15),
        "floor_range": (1, 20),
        "views": ["community", "park", "road", "skyline"],
        "view_weights": [0.40, 0.25, 0.25, 0.10],
        "parking": {0: 0.15, 1: 0.70, 2: 0.15},
        "completion_range": (2015, 2024),
        "furnishing": {"furnished": 0.20, "unfurnished": 0.55, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "bbq"],
        "amenities_count": (2, 4),
        "occupancy": 0.85,
        "off_plan_pct": 0.30,
    },
    "Business Bay": {
        "district": "Central",
        "established": 2012,
        "developer_master": "Various",
        "price_range": (800000, 2500000),
        "sqft_range": (400, 1200),
        "roi_range": (6.5, 7.8),
        "service_charge": (14, 22),
        "floor_range": (5, 45),
        "views": ["canal", "burj_khalifa", "community", "road"],
        "view_weights": [0.25, 0.20, 0.35, 0.20],
        "parking": {0: 0.10, 1: 0.65, 2: 0.25},
        "completion_range": (2014, 2024),
        "furnishing": {"furnished": 0.30, "unfurnished": 0.45, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "concierge", "bbq", "retail"],
        "amenities_count": (3, 5),
        "occupancy": 0.87,
        "off_plan_pct": 0.25,
    },
    "Arabian Ranches": {
        "district": "Suburban",
        "established": 2004,
        "developer_master": "Emaar",
        "price_range": (2500000, 6500000),
        "sqft_range": (2200, 5500),
        "roi_range": (5.0, 6.5),
        "service_charge": (10, 18),
        "floor_range": (1, 3),
        "views": ["golf", "community", "park", "desert"],
        "view_weights": [0.25, 0.35, 0.25, 0.15],
        "parking": {0: 0.0, 1: 0.10, 2: 0.50, 3: 0.40},
        "completion_range": (2004, 2022),
        "furnishing": {"furnished": 0.05, "unfurnished": 0.75, "semi": 0.20},
        "amenities_pool": ["pool", "gym", "kids_play", "bbq", "park", "retail"],
        "amenities_count": (4, 6),
        "occupancy": 0.90,
        "off_plan_pct": 0.05,
    },
    "Sports City": {
        "district": "Sports",
        "established": 2006,
        "developer_master": "Union Properties",
        "price_range": (500000, 1200000),
        "sqft_range": (350, 850),
        "roi_range": (7.5, 9.0),
        "service_charge": (10, 16),
        "floor_range": (1, 18),
        "views": ["community", "road", "cricket_stadium", "park"],
        "view_weights": [0.35, 0.25, 0.15, 0.25],
        "parking": {0: 0.15, 1: 0.70, 2: 0.15},
        "completion_range": (2008, 2020),
        "furnishing": {"furnished": 0.15, "unfurnished": 0.60, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play"],
        "amenities_count": (2, 3),
        "occupancy": 0.84,
        "off_plan_pct": 0.10,
    },
    "Discovery Gardens": {
        "district": "Discovery",
        "established": 2006,
        "developer_master": "Nakheel",
        "price_range": (400000, 900000),
        "sqft_range": (350, 700),
        "roi_range": (8.5, 9.5),
        "service_charge": (8, 14),
        "floor_range": (1, 12),
        "views": ["community", "garden", "road", "pool"],
        "view_weights": [0.35, 0.30, 0.25, 0.10],
        "parking": {0: 0.20, 1: 0.65, 2: 0.15},
        "completion_range": (2006, 2015),
        "furnishing": {"furnished": 0.10, "unfurnished": 0.65, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "garden"],
        "amenities_count": (2, 4),
        "occupancy": 0.86,
        "off_plan_pct": 0.0,
    },
    "JLT (Jumeirah Lake Towers)": {
        "district": "JLT",
        "established": 2008,
        "developer_master": "DMCC",
        "price_range": (800000, 2200000),
        "sqft_range": (450, 1400),
        "roi_range": (6.8, 7.8),
        "service_charge": (12, 20),
        "floor_range": (3, 40),
        "views": ["lake", "community", "marina", "road"],
        "view_weights": [0.25, 0.35, 0.20, 0.20],
        "parking": {0: 0.10, 1: 0.65, 2: 0.25},
        "completion_range": (2008, 2020),
        "furnishing": {"furnished": 0.25, "unfurnished": 0.50, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "concierge", "retail"],
        "amenities_count": (2, 4),
        "occupancy": 0.86,
        "off_plan_pct": 0.05,
    },
    "The Springs": {
        "district": "Suburban",
        "established": 2001,
        "developer_master": "Emaar",
        "price_range": (1200000, 3500000),
        "sqft_range": (1000, 3000),
        "roi_range": (6.0, 7.5),
        "service_charge": (8, 15),
        "floor_range": (1, 3),
        "views": ["lake", "community", "park", "garden"],
        "view_weights": [0.30, 0.30, 0.25, 0.15],
        "parking": {0: 0.0, 1: 0.15, 2: 0.55, 3: 0.30},
        "completion_range": (2001, 2008),
        "furnishing": {"furnished": 0.05, "unfurnished": 0.80, "semi": 0.15},
        "amenities_pool": ["pool", "gym", "kids_play", "bbq", "lake_access"],
        "amenities_count": (3, 5),
        "occupancy": 0.91,
        "off_plan_pct": 0.0,
    },
    "Al Barsha": {
        "district": "Al Barsha",
        "established": 2005,
        "developer_master": "Various",
        "price_range": (700000, 1800000),
        "sqft_range": (450, 1100),
        "roi_range": (7.0, 8.2),
        "service_charge": (10, 18),
        "floor_range": (2, 22),
        "views": ["community", "road", "mall", "park"],
        "view_weights": [0.35, 0.30, 0.15, 0.20],
        "parking": {0: 0.10, 1: 0.65, 2: 0.25},
        "completion_range": (2005, 2022),
        "furnishing": {"furnished": 0.15, "unfurnished": 0.60, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "retail"],
        "amenities_count": (2, 4),
        "occupancy": 0.87,
        "off_plan_pct": 0.08,
    },
    "Deira": {
        "district": "Deira",
        "established": 2000,
        "developer_master": "Various",
        "price_range": (350000, 900000),
        "sqft_range": (300, 650),
        "roi_range": (8.5, 10.0),
        "service_charge": (8, 14),
        "floor_range": (1, 15),
        "views": ["community", "road", "creek", "market"],
        "view_weights": [0.35, 0.30, 0.15, 0.20],
        "parking": {0: 0.25, 1: 0.60, 2: 0.15},
        "completion_range": (2000, 2018),
        "furnishing": {"furnished": 0.30, "unfurnished": 0.45, "semi": 0.25},
        "amenities_pool": ["gym", "retail"],
        "amenities_count": (1, 2),
        "occupancy": 0.88,
        "off_plan_pct": 0.05,
    },
    "Bur Dubai": {
        "district": "Bur Dubai",
        "established": 2002,
        "developer_master": "Various",
        "price_range": (550000, 1500000),
        "sqft_range": (400, 900),
        "roi_range": (7.5, 8.8),
        "service_charge": (10, 16),
        "floor_range": (1, 18),
        "views": ["community", "road", "creek", "museum"],
        "view_weights": [0.35, 0.30, 0.20, 0.15],
        "parking": {0: 0.20, 1: 0.60, 2: 0.20},
        "completion_range": (2002, 2020),
        "furnishing": {"furnished": 0.25, "unfurnished": 0.50, "semi": 0.25},
        "amenities_pool": ["gym", "pool", "retail"],
        "amenities_count": (1, 3),
        "occupancy": 0.87,
        "off_plan_pct": 0.05,
    },
    "International City": {
        "district": "International City",
        "established": 2006,
        "developer_master": "Nakheel",
        "price_range": (280000, 600000),
        "sqft_range": (250, 500),
        "roi_range": (9.5, 10.5),
        "service_charge": (6, 12),
        "floor_range": (1, 8),
        "views": ["community", "road", "park", "dragon_mart"],
        "view_weights": [0.40, 0.30, 0.20, 0.10],
        "parking": {0: 0.25, 1: 0.65, 2: 0.10},
        "completion_range": (2006, 2015),
        "furnishing": {"furnished": 0.10, "unfurnished": 0.70, "semi": 0.20},
        "amenities_pool": ["pool", "gym", "retail"],
        "amenities_count": (1, 3),
        "occupancy": 0.83,
        "off_plan_pct": 0.0,
    },
    "Dubai Silicon Oasis": {
        "district": "DSO",
        "established": 2009,
        "developer_master": "Various",
        "price_range": (400000, 1000000),
        "sqft_range": (380, 750),
        "roi_range": (8.0, 9.5),
        "service_charge": (8, 14),
        "floor_range": (1, 15),
        "views": ["community", "tech_park", "road", "park"],
        "view_weights": [0.35, 0.20, 0.25, 0.20],
        "parking": {0: 0.15, 1: 0.70, 2: 0.15},
        "completion_range": (2010, 2022),
        "furnishing": {"furnished": 0.10, "unfurnished": 0.65, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "retail"],
        "amenities_count": (2, 4),
        "occupancy": 0.82,
        "off_plan_pct": 0.15,
    },
    "Tilal Al Ghaf": {
        "district": "Tilal Al Ghaf",
        "established": 2019,
        "developer_master": "Meraas",
        "price_range": (1500000, 6000000),
        "sqft_range": (900, 4500),
        "roi_range": (5.0, 7.5),
        "service_charge": (10, 18),
        "floor_range": (1, 4),
        "views": ["lagoon", "community", "park", "golf"],
        "view_weights": [0.30, 0.30, 0.25, 0.15],
        "parking": {0: 0.0, 1: 0.20, 2: 0.50, 3: 0.30},
        "completion_range": (2022, 2026),
        "furnishing": {"furnished": 0.10, "unfurnished": 0.65, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "lagoon", "kids_play", "bbq", "park"],
        "amenities_count": (4, 6),
        "occupancy": 0.80,
        "off_plan_pct": 0.55,
    },
    "DAMAC Hills 2": {
        "district": "DAMAC Hills",
        "established": 2018,
        "developer_master": "DAMAC",
        "price_range": (550000, 1500000),
        "sqft_range": (400, 1000),
        "roi_range": (7.5, 9.0),
        "service_charge": (10, 16),
        "floor_range": (1, 15),
        "views": ["community", "golf", "park", "road"],
        "view_weights": [0.35, 0.20, 0.25, 0.20],
        "parking": {0: 0.10, 1: 0.65, 2: 0.25},
        "completion_range": (2020, 2026),
        "furnishing": {"furnished": 0.15, "unfurnished": 0.60, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "bbq", "retail"],
        "amenities_count": (3, 5),
        "occupancy": 0.78,
        "off_plan_pct": 0.45,
    },
    "Dubai Creek Harbour": {
        "district": "Creek Harbour",
        "established": 2017,
        "developer_master": "Emaar",
        "price_range": (1100000, 3000000),
        "sqft_range": (600, 1800),
        "roi_range": (6.5, 7.8),
        "service_charge": (14, 22),
        "floor_range": (3, 35),
        "views": ["creek", "burj_khalifa", "community", "park"],
        "view_weights": [0.30, 0.20, 0.30, 0.20],
        "parking": {0: 0.05, 1: 0.60, 2: 0.35},
        "completion_range": (2019, 2026),
        "furnishing": {"furnished": 0.20, "unfurnished": 0.55, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "concierge", "kids_play", "park", "retail"],
        "amenities_count": (4, 6),
        "occupancy": 0.85,
        "off_plan_pct": 0.35,
    },
    "Bluewaters Island": {
        "district": "Bluewaters",
        "established": 2018,
        "developer_master": "Meraas",
        "price_range": (2500000, 6000000),
        "sqft_range": (1100, 3000),
        "roi_range": (5.5, 6.5),
        "service_charge": (18, 28),
        "floor_range": (2, 18),
        "views": ["sea", "ain_dubai", "marina", "community"],
        "view_weights": [0.35, 0.25, 0.25, 0.15],
        "parking": {0: 0.0, 1: 0.40, 2: 0.50, 3: 0.10},
        "completion_range": (2018, 2023),
        "furnishing": {"furnished": 0.45, "unfurnished": 0.30, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "concierge", "beach_access", "spa", "valet"],
        "amenities_count": (4, 6),
        "occupancy": 0.87,
        "off_plan_pct": 0.05,
    },
    "Meydan": {
        "district": "Meydan",
        "established": 2015,
        "developer_master": "Meydan",
        "price_range": (900000, 2000000),
        "sqft_range": (550, 1200),
        "roi_range": (6.8, 7.8),
        "service_charge": (12, 18),
        "floor_range": (3, 25),
        "views": ["community", "racetrack", "skyline", "park"],
        "view_weights": [0.35, 0.15, 0.25, 0.25],
        "parking": {0: 0.05, 1: 0.65, 2: 0.30},
        "completion_range": (2018, 2025),
        "furnishing": {"furnished": 0.15, "unfurnished": 0.60, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "park"],
        "amenities_count": (3, 4),
        "occupancy": 0.83,
        "off_plan_pct": 0.35,
    },
    "Al Furjan": {
        "district": "Al Furjan",
        "established": 2015,
        "developer_master": "Nakheel",
        "price_range": (800000, 1800000),
        "sqft_range": (500, 1100),
        "roi_range": (7.0, 8.0),
        "service_charge": (10, 16),
        "floor_range": (1, 15),
        "views": ["community", "park", "road", "metro"],
        "view_weights": [0.35, 0.30, 0.25, 0.10],
        "parking": {0: 0.10, 1: 0.65, 2: 0.25},
        "completion_range": (2016, 2024),
        "furnishing": {"furnished": 0.15, "unfurnished": 0.60, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "retail"],
        "amenities_count": (2, 4),
        "occupancy": 0.85,
        "off_plan_pct": 0.20,
    },
    "Dubai South": {
        "district": "Dubai South",
        "established": 2015,
        "developer_master": "Dubai South",
        "price_range": (450000, 1100000),
        "sqft_range": (380, 800),
        "roi_range": (8.5, 9.8),
        "service_charge": (8, 14),
        "floor_range": (1, 15),
        "views": ["community", "airport", "road", "park"],
        "view_weights": [0.35, 0.15, 0.30, 0.20],
        "parking": {0: 0.15, 1: 0.70, 2: 0.15},
        "completion_range": (2018, 2026),
        "furnishing": {"furnished": 0.10, "unfurnished": 0.65, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "retail"],
        "amenities_count": (2, 4),
        "occupancy": 0.78,
        "off_plan_pct": 0.50,
    },
    "Town Square": {
        "district": "Town Square",
        "established": 2016,
        "developer_master": "Nshama",
        "price_range": (500000, 1100000),
        "sqft_range": (380, 800),
        "roi_range": (8.0, 9.2),
        "service_charge": (8, 14),
        "floor_range": (1, 15),
        "views": ["community", "park", "town_square", "road"],
        "view_weights": [0.35, 0.30, 0.15, 0.20],
        "parking": {0: 0.15, 1: 0.70, 2: 0.15},
        "completion_range": (2018, 2024),
        "furnishing": {"furnished": 0.10, "unfurnished": 0.65, "semi": 0.25},
        "amenities_pool": ["pool", "gym", "kids_play", "bbq", "retail"],
        "amenities_count": (2, 5),
        "occupancy": 0.82,
        "off_plan_pct": 0.25,
    },
}

# Transaction templates (bedroom configs per property type)
BEDROOM_CONFIGS = {
    "Apartment": [
        {"bedrooms": 0, "weight": 0.15, "size_factor": 1.0},
        {"bedrooms": 1, "weight": 0.40, "size_factor": 1.0},
        {"bedrooms": 2, "weight": 0.35, "size_factor": 1.0},
        {"bedrooms": 3, "weight": 0.10, "size_factor": 1.0},
    ],
    "Villa": [
        {"bedrooms": 3, "weight": 0.30, "size_factor": 1.0},
        {"bedrooms": 4, "weight": 0.45, "size_factor": 1.0},
        {"bedrooms": 5, "weight": 0.25, "size_factor": 1.0},
    ],
    "Penthouse": [
        {"bedrooms": 2, "weight": 0.20, "size_factor": 1.3},
        {"bedrooms": 3, "weight": 0.50, "size_factor": 1.3},
        {"bedrooms": 4, "weight": 0.30, "size_factor": 1.3},
    ],
}

DEVELOPERS = ["Emaar", "DAMAC", "Nakheel", "Meraas", "Omniyat", "Select Group", "Binghatti", "Nshama", "Union Properties", "DMCC", "Various"]
OFF_PLAN_STATUS = ["Off-Plan", "Ready"]


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def generate_transaction(tx_id: int, community: str, profile: dict) -> dict:
    """Generate a single realistic transaction record."""
    prop_type = weighted_choice(
        ["Apartment", "Villa", "Penthouse"] if community in ["Palm Jumeirah", "Arabian Ranches", "The Springs", "Bluewaters Island", "Tilal Al Ghaf"]
        else ["Apartment"],
        [0.85, 0.10, 0.05] if community in ["Palm Jumeirah", "Bluewaters Island"]
        else [1.0] if community not in ["Arabian Ranches", "The Springs", "Tilal Al Ghaf"]
        else [0.30, 0.65, 0.05],
    )

    bedroom_config = weighted_choice(
        BEDROOM_CONFIGS[prop_type],
        [c["weight"] for c in BEDROOM_CONFIGS[prop_type]],
    )
    bedrooms = bedroom_config["bedrooms"]

    # Price
    min_p, max_p = profile["price_range"]
    base_price = random.uniform(min_p, max_p)
    if prop_type == "Villa":
        base_price *= 1.2
    elif prop_type == "Penthouse":
        base_price *= 1.5
    price = int(round(base_price / 50000) * 50000)

    # Size
    min_s, max_s = profile["sqft_range"]
    base_size = random.uniform(min_s, max_s) * bedroom_config["size_factor"]
    if bedrooms == 0:
        base_size = random.uniform(min_s, min_s + 150)
    size = int(round(base_size / 10) * 10)

    # Floor
    min_f, max_f = profile["floor_range"]
    floor = random.randint(min_f, max_f)

    # View
    view = weighted_choice(profile["views"], profile["view_weights"])

    # Service charge
    sc_min, sc_max = profile["service_charge"]
    service_charge = round(random.uniform(sc_min, sc_max), 1)

    # Parking
    parking_options = list(profile["parking"].keys())
    parking_weights = list(profile["parking"].values())
    parking = weighted_choice(parking_options, parking_weights)

    # Completion year
    yr_min, yr_max = profile["completion_range"]
    completion_year = random.randint(yr_min, yr_max)

    # Furnishing
    furnishing_options = list(profile["furnishing"].keys())
    furnishing_weights = list(profile["furnishing"].values())
    furnishing = weighted_choice(furnishing_options, furnishing_weights)

    # Amenities
    amenity_count = random.randint(*profile["amenities_count"])
    amenities = random.sample(profile["amenities_pool"], min(amenity_count, len(profile["amenities_pool"])))

    # ROI
    roi_min, roi_max = profile["roi_range"]
    roi = round(random.uniform(roi_min, roi_max), 1)

    # Off-plan status
    is_offplan = random.random() < profile["off_plan_pct"]
    handover_status = "Off-Plan" if is_offplan else "Ready"

    # Date
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    date = f"2024-{month:02d}-{day:02d}"

    return {
        "transaction_id": f"TRX-{tx_id:03d}",
        "community": community,
        "property_type": prop_type,
        "bedrooms": bedrooms,
        "price_aed": price,
        "size_sqft": size,
        "transaction_date": date,
        "roi_pct": roi,
        "developer": profile["developer_master"] if profile["developer_master"] != "Various" else random.choice(DEVELOPERS),
        "handover_status": handover_status,
        "floor_level": floor,
        "view_type": view,
        "service_charge_aed_sqft": service_charge,
        "parking_spots": parking,
        "completion_year": completion_year,
        "furnishing": furnishing,
        "amenities": ",".join(sorted(amenities)),
    }


def generate_communities_dimension() -> list:
    """Generate community dimension table."""
    rows = []
    for name, profile in COMMUNITY_PROFILES.items():
        rows.append({
            "community_name": name,
            "district": profile["district"],
            "established_year": profile["established"],
            "master_developer": profile["developer_master"],
            "occupancy_rate": profile["occupancy"],
            "off_plan_percentage": profile["off_plan_pct"],
        })
    return rows


def generate_supply_pipeline() -> list:
    """Generate supply pipeline data."""
    rows = []
    for name, profile in COMMUNITY_PROFILES.items():
        existing_stock = random.randint(2000, 15000)
        under_construction = int(existing_stock * random.uniform(0.05, 0.25))
        completed_12m = int(existing_stock * random.uniform(0.03, 0.12))
        expected_24m = int(under_construction * random.uniform(0.6, 1.0))
        pipeline_pct = round(expected_24m / existing_stock * 100, 1)

        rows.append({
            "community_name": name,
            "existing_stock_units": existing_stock,
            "units_under_construction": under_construction,
            "units_completed_last_12_months": completed_12m,
            "units_expected_next_24_months": expected_24m,
            "pipeline_pct_of_stock": pipeline_pct,
            "supply_risk": "high" if pipeline_pct > 15 else "medium" if pipeline_pct > 8 else "low",
        })
    return rows


def main():
    random.seed(42)  # Reproducible

    # Generate transactions
    transactions = []
    tx_id = 1
    for community, profile in COMMUNITY_PROFILES.items():
        # Number of transactions proportional to community size
        n_tx = random.randint(2, 5)
        for _ in range(n_tx):
            transactions.append(generate_transaction(tx_id, community, profile))
            tx_id += 1

    # Write transactions CSV
    csv_path = DATA_DIR / "transactions.csv"
    fieldnames = list(transactions[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)
    print(f"Generated {len(transactions)} transactions -> {csv_path}")

    # Write communities dimension
    communities = generate_communities_dimension()
    comm_path = DATA_DIR / "communities.csv"
    with open(comm_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(communities[0].keys()))
        writer.writeheader()
        writer.writerows(communities)
    print(f"Generated {len(communities)} communities -> {comm_path}")

    # Write supply pipeline
    supply = generate_supply_pipeline()
    supply_path = DATA_DIR / "supply_pipeline.csv"
    with open(supply_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(supply[0].keys()))
        writer.writeheader()
        writer.writerows(supply)
    print(f"Generated {len(supply)} supply pipeline records -> {supply_path}")


if __name__ == "__main__":
    main()
