"""BayutAPI data provider — real DLD-registered property data.

Uses the search-property endpoint (reliable) instead of transactions (502 issues).
Requires a BayutAPI key from RapidAPI (free tier: 900 req/month).
Set BAYUT_API_KEY in .env or pass directly.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))

import requests

from data_provider import DataProvider, Transaction, CommunitySummary


BAYUT_BASE = "https://uae-real-estate3.p.rapidapi.com"
SQM_TO_SQFT = 10.7639

# Map our community names to BayutAPI external IDs
COMMUNITY_LOCATION_IDS = {
    "Downtown Dubai": "6901",
    "Dubai Marina": "5003",
    "Palm Jumeirah": "5460",
    "Dubai Hills Estate": "8288",
    "JVC (Jumeirah Village Circle)": "5416",
    "Business Bay": "5093",
    "Arabian Ranches": "12423",
    "Sports City": "5179",
    "Discovery Gardens": "5097",
    "JLT (Jumeirah Lake Towers)": "5152",
    "The Springs": "5183",
    "Al Barsha": "5040",
    "Deira": "5084",
    "Bur Dubai": "5062",
    "International City": "5132",
    "Dubai Silicon Oasis": "5170",
    "Tilal Al Ghaf": "12424",
    "DAMAC Hills 2": "12420",
    "Dubai Creek Harbour": "12421",
    "Bluewaters Island": "5053",
    "Meydan": "5150",
    "Al Furjan": "5039",
    "Dubai South": "5173",
    "Town Square": "5196",
    "DIFC": "5089",
}


class BayutProvider(DataProvider):
    """Real property data via BayutAPI (RapidAPI)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BAYUT_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "BAYUT_API_KEY required. Get one at https://rapidapi.com/happyendpoint/api/uae-real-estate3"
            )
        self.headers = {
            "x-rapidapi-host": "uae-real-estate3.p.rapidapi.com",
            "x-rapidapi-key": self.api_key,
        }
        self._location_cache: Dict[str, str] = {}
        self._rate_limit_delay = 0.5

    def _get_location_id(self, query: str) -> Optional[str]:
        """Look up a community's BayutAPI location ID via autocomplete."""
        if query in self._location_cache:
            return self._location_cache[query]

        # Try pre-mapped IDs first
        for name, lid in COMMUNITY_LOCATION_IDS.items():
            if query.lower() in name.lower() or name.lower() in query.lower():
                self._location_cache[query] = lid
                return lid

        try:
            resp = requests.get(
                f"{BAYUT_BASE}/autocomplete",
                headers=self.headers,
                params={"query": query},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success") and data.get("data"):
                locations = data["data"]
                if isinstance(locations, dict):
                    locations = locations.get("locations", [])
                if locations:
                    location_id = str(locations[0].get("externalID", ""))
                    self._location_cache[query] = location_id
                    return location_id
        except Exception as e:
            print(f"[BayutAPI] Autocomplete error for '{query}': {e}")

        return None

    def _search_properties(
        self,
        purpose: str = "for-sale",
        location_id: Optional[str] = None,
        category: Optional[str] = None,
        beds: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        max_pages: int = 5,
    ) -> List[Dict]:
        """Fetch properties from BayutAPI search-property endpoint."""
        all_props = []
        page = 1

        while page <= max_pages:
            params = {
                "purpose": purpose,
                "page": str(page),
            }
            if location_id:
                params["location_ids"] = location_id
            if category:
                params["category_ids"] = category
            if beds is not None:
                params["beds"] = beds
            if price_min:
                params["price_min"] = str(price_min)
            if price_max:
                params["price_max"] = str(price_max)

            try:
                resp = requests.get(
                    f"{BAYUT_BASE}/search-property",
                    headers=self.headers,
                    params=params,
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                props = data.get("data", {}).get("properties", [])
                if not props:
                    break

                all_props.extend(props)

                total_pages = data.get("data", {}).get("totalPages", 1)
                if page >= total_pages:
                    break

                page += 1
                time.sleep(self._rate_limit_delay)

            except Exception as e:
                print(f"[BayutAPI] Search error (page {page}): {e}")
                break

        return all_props

    def _get_community_name(self, prop: Dict) -> str:
        """Extract community name from property location array."""
        locations = prop.get("location", [])
        # Level 2 = neighbourhood (Dubai Marina, Downtown, etc.)
        for loc in locations:
            if loc.get("level") == 2:
                return loc.get("name", "Unknown")
        # Fallback: use level 1 (Dubai)
        for loc in locations:
            if loc.get("level") == 1:
                return loc.get("name", "Unknown")
        return "Unknown"

    def get_transactions(
        self,
        community: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        location_id = None
        if community:
            location_id = self._get_location_id(community)

        category = None
        if property_type:
            category = property_type.lower()

        beds = None
        if bedrooms is not None:
            beds = str(bedrooms)

        props = self._search_properties(
            purpose="for-sale",
            location_id=location_id,
            category=category,
            beds=beds,
            price_min=min_price,
            price_max=max_price,
            max_pages=5,
        )

        # Also fetch rentals for yield calculation
        rent_props = self._search_properties(
            purpose="for-rent",
            location_id=location_id,
            category=category,
            beds=beds,
            max_pages=3,
        )

        # Build rent lookup by community + bedrooms
        rent_lookup: Dict[str, List[float]] = {}
        for rp in rent_props:
            community_name = self._get_community_name(rp)
            key = f"{community_name}_{rp.get('rooms', 0)}"
            rent_lookup.setdefault(key, []).append(rp.get("price", 0))

        transactions = []
        for p in props:
            price = p.get("price", 0)
            area_sqm = p.get("area", 0)
            area_sqft = area_sqm * SQM_TO_SQFT if area_sqm else 0

            if price <= 0 or area_sqft <= 0:
                continue

            community_name = self._get_community_name(p)

            # Estimate annual rent
            rent_key = f"{community_name}_{p.get('rooms', 0)}"
            rents = rent_lookup.get(rent_key, [])
            if rents:
                avg_annual_rent = median(rents)
            else:
                avg_annual_rent = price * 0.06  # fallback 6% gross

            # Compute net yield
            annual_service = 15.0 * area_sqft  # estimated
            management = avg_annual_rent * 0.08
            net_rent = avg_annual_rent - annual_service - management
            net_yield = round((net_rent / price) * 100, 2) if price > 0 else 0
            gross_yield = round((avg_annual_rent / price) * 100, 2) if price > 0 else 0

            # Check completion status
            is_offplan = p.get("offplanDetails") is not None
            status = "off-plan" if is_offplan else "ready"

            # Get developer from project
            project = p.get("project", {})
            dev_raw = project.get("developer", "") if project else ""
            if isinstance(dev_raw, dict):
                developer = dev_raw.get("name", "")
            else:
                developer = str(dev_raw) if dev_raw else ""

            transactions.append(Transaction(
                transaction_id=f"BAYUT-{p.get('id', '')}",
                community=community_name,
                property_type=p.get("category", "apartments"),
                bedrooms=p.get("rooms", 0),
                price_aed=int(price),
                size_sqft=int(area_sqft),
                transaction_date=str(p.get("createdAt", ""))[:10],
                roi_pct=gross_yield,
                developer=developer,
                handover_status=status,
                floor_level=None,
                view_type=None,
                service_charge_aed_sqft=15.0,
            ))

        transactions.sort(key=lambda t: t.roi_pct, reverse=True)
        return transactions[:limit]

    def get_community_summaries(self) -> List[CommunitySummary]:
        summaries = []

        for community_name, location_id in COMMUNITY_LOCATION_IDS.items():
            try:
                # Fetch sales
                sales = self._search_properties(
                    purpose="for-sale",
                    location_id=location_id,
                    max_pages=3,
                )
                time.sleep(self._rate_limit_delay)

                # Fetch rentals
                rentals = self._search_properties(
                    purpose="for-rent",
                    location_id=location_id,
                    max_pages=2,
                )
                time.sleep(self._rate_limit_delay)

                if not sales:
                    continue

                # Compute metrics
                sale_prices = [s["price"] for s in sales if s.get("price")]
                sale_areas = [s.get("area", 0) * SQM_TO_SQFT for s in sales if s.get("area")]
                rents = [r["price"] for r in rentals if r.get("price")]

                avg_price = median(sale_prices) if sale_prices else 0
                avg_area = median(sale_areas) if sale_areas else 800
                avg_ppsf = round(avg_price / avg_area) if avg_area > 0 else 0
                avg_rent = median(rents) if rents else avg_price * 0.06

                gross_yield = round((avg_rent / avg_price) * 100, 2) if avg_price > 0 else 0
                annual_service = 15.0 * avg_area
                management = avg_rent * 0.08
                net_rent = avg_rent - annual_service - management
                net_yield = round((net_rent / avg_price) * 100, 2) if avg_price > 0 else 0

                summaries.append(CommunitySummary(
                    community_name=community_name,
                    district="",
                    avg_price_per_sqft=avg_ppsf,
                    avg_roi_pct=gross_yield,
                    avg_net_yield_pct=net_yield,
                    avg_service_charge=15.0,
                    transaction_count=len(sales),
                    supply_risk="MEDIUM",
                    composite_score=0,
                    recommendation="HOLD",
                ))

            except Exception as e:
                print(f"[BayutAPI] Error fetching {community_name}: {e}")
                continue

        return summaries

    def get_supply_pipeline(self) -> List[Dict[str, Any]]:
        return []

    def health_check(self) -> bool:
        try:
            resp = requests.get(
                f"{BAYUT_BASE}/health",
                headers=self.headers,
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
