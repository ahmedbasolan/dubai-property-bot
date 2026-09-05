"""BayutAPI data provider — real DLD-registered transaction data.

Requires a BayutAPI key from RapidAPI (free tier: 900 req/month).
Set BAYUT_API_KEY in .env or pass directly.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))

import requests

from data_provider import DataProvider, Transaction, CommunitySummary


BAYUT_BASE = "https://uae-real-estate3.p.rapidapi.com"

# Map our community names to BayutAPI location IDs (from autocomplete endpoint)
COMMUNITY_LOCATION_IDS = {
    "Downtown Dubai": "8130",
    "Dubai Marina": "8136",
    "Palm Jumeirah": "8146",
    "Dubai Hills Estate": "8665",
    "JVC (Jumeirah Village Circle)": "8143",
    "Business Bay": "8128",
    "Arabian Ranches": "8118",
    "Sports City": "8160",
    "Discovery Gardens": "8133",
    "JLT (Jumeirah Lake Towers)": "8144",
    "The Springs": "8163",
    "Al Barsha": "8115",
    "Deira": "8131",
    "Bur Dubai": "8127",
    "International City": "8141",
    "Dubai Silicon Oasis": "8132",
    "Tilal Al Ghaf": "8666",
    "DAMAC Hills 2": "8664",
    "Dubai Creek Harbour": "8667",
    "Bluewaters Island": "8125",
    "Meydan": "8145",
    "Al Furjan": "8116",
    "Dubai South": "8134",
    "Town Square": "8166",
    "DIFC": "8129",
}

# Reverse: BayutAPI location name → our community name
BAYUT_TO_OURS = {v: k for k, v in COMMUNITY_LOCATION_IDS.items()}


class BayutProvider(DataProvider):
    """Real DLD data via BayutAPI (RapidAPI)."""

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
        self._rate_limit_delay = 0.5  # seconds between requests

    def _get_location_id(self, query: str) -> Optional[str]:
        """Look up a community's BayutAPI location ID via autocomplete."""
        if query in self._location_cache:
            return self._location_cache[query]

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
                # First result is usually the best match
                location_id = str(data["data"][0].get("id", ""))
                self._location_cache[query] = location_id
                return location_id
        except Exception as e:
            print(f"[BayutAPI] Autocomplete error for '{query}': {e}")

        return None

    def _fetch_transactions(
        self,
        purpose: str = "for-sale",
        location_id: Optional[str] = None,
        category: Optional[str] = None,
        beds: Optional[str] = None,
        time_period: str = "24m",
        max_pages: int = 10,
    ) -> List[Dict]:
        """Fetch raw transactions from BayutAPI, paginating up to max_pages."""
        all_hits = []
        page = 1

        while page <= max_pages:
            params = {
                "purpose": purpose,
                "time_period": time_period,
                "page": str(page),
            }
            if location_id:
                params["location_ids"] = location_id
            if category:
                params["category_ids"] = category
            if beds is not None:
                params["beds"] = beds

            try:
                resp = requests.get(
                    f"{BAYUT_BASE}/transactions",
                    headers=self.headers,
                    params=params,
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                hits = data.get("data", {}).get("hits", [])
                if not hits:
                    break

                all_hits.extend(hits)

                nb_pages = data.get("data", {}).get("nbPages", 1)
                if page >= nb_pages:
                    break

                page += 1
                time.sleep(self._rate_limit_delay)

            except Exception as e:
                print(f"[BayutAPI] Transaction fetch error (page {page}): {e}")
                break

        return all_hits

    def _compute_yield(
        self,
        sale_price: float,
        annual_rent: float,
        service_charge_sqft: float = 15.0,
        size_sqft: float = 800,
    ) -> float:
        """Compute net yield from sale price and annual rent."""
        if sale_price <= 0:
            return 0.0
        annual_service = service_charge_sqft * size_sqft
        management = annual_rent * 0.08
        net_rent = annual_rent - annual_service - management
        return round((net_rent / sale_price) * 100, 2)

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
            if not location_id:
                # Try pre-mapped IDs
                for name, lid in COMMUNITY_LOCATION_IDS.items():
                    if community.lower() in name.lower() or name.lower() in community.lower():
                        location_id = lid
                        break

        category = None
        if property_type:
            category = property_type.lower()

        beds = None
        if bedrooms is not None:
            beds = str(bedrooms)

        hits = self._fetch_transactions(
            purpose="for-sale",
            location_id=location_id,
            category=category,
            beds=beds,
            time_period="24m",
            max_pages=5,
        )

        # Also fetch rentals for yield calculation
        rent_hits = self._fetch_transactions(
            purpose="for-rent",
            location_id=location_id,
            category=category,
            beds=beds,
            time_period="12m",
            max_pages=3,
        )

        # Build rent lookup by community + bedrooms
        rent_lookup: Dict[str, List[float]] = {}
        for rh in rent_hits:
            key = f"{rh.get('location', '')}_{rh.get('rooms', 0)}"
            rent_lookup.setdefault(key, []).append(rh.get("price", 0))

        transactions = []
        for h in hits:
            price = h.get("price", 0)
            area = h.get("area", 0)
            if price <= 0 or area <= 0:
                continue

            if min_price and price < min_price:
                continue
            if max_price and price > max_price:
                continue

            community_name = h.get("location", "Unknown")
            # Normalize to our community name
            our_name = BAYUT_TO_OURS.get(community_name, community_name)

            # Estimate annual rent from rent data
            rent_key = f"{community_name}_{h.get('rooms', 0)}"
            rents = rent_lookup.get(rent_key, [])
            avg_rent = median(rents) if rents else price * 0.06  # fallback 6% gross

            net_yield = self._compute_yield(price, avg_rent, 15.0, area)

            transactions.append(Transaction(
                transaction_id=h.get("transactionId", f"BAYUT-{len(transactions)}"),
                community=our_name,
                property_type=h.get("category", "apartments"),
                bedrooms=h.get("rooms", 0),
                price_aed=int(price),
                size_sqft=int(area),
                transaction_date=h.get("date", ""),
                roi_pct=round((avg_rent / price) * 100, 2) if price > 0 else 0,
                developer="",
                handover_status=h.get("completionStatus", "completed"),
            ))

        # Sort by net yield descending
        transactions.sort(key=lambda t: t.roi_pct, reverse=True)
        return transactions[:limit]

    def get_community_summaries(self) -> List[CommunitySummary]:
        summaries = []

        for community_name, location_id in COMMUNITY_LOCATION_IDS.items():
            try:
                # Fetch sales
                sales = self._fetch_transactions(
                    purpose="for-sale",
                    location_id=location_id,
                    max_pages=3,
                )
                time.sleep(self._rate_limit_delay)

                # Fetch rentals
                rentals = self._fetch_transactions(
                    purpose="for-rent",
                    location_id=location_id,
                    max_pages=2,
                )
                time.sleep(self._rate_limit_delay)

                if not sales:
                    continue

                # Compute metrics
                prices_per_sqft = [
                    s["price"] / s["area"]
                    for s in sales
                    if s.get("price") and s.get("area") and s["area"] > 0
                ]
                sale_prices = [s["price"] for s in sales if s.get("price")]
                rents = [r["price"] for r in rentals if r.get("price")]

                avg_ppsf = median(prices_per_sqft) if prices_per_sqft else 0
                avg_price = median(sale_prices) if sale_prices else 0
                avg_rent = median(rents) if rents else avg_price * 0.06

                # Estimate bedrooms from data (most common)
                bedroom_counts = [s.get("rooms", 1) for s in sales]
                most_common_beds = median(bedroom_counts) if bedroom_counts else 1

                # Estimate size from data
                areas = [s.get("area", 800) for s in sales if s.get("area")]
                avg_size = median(areas) if areas else 800

                gross_yield = round((avg_rent / avg_price) * 100, 2) if avg_price > 0 else 0
                net_yield = self._compute_yield(avg_price, avg_rent, 15.0, avg_size)

                summaries.append(CommunitySummary(
                    community_name=community_name,
                    district="",
                    avg_price_per_sqft=round(avg_ppsf),
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
        # BayutAPI doesn't provide supply pipeline data
        # Fall back to mock data or return empty
        return []

    def health_check(self) -> bool:
        try:
            resp = requests.get(
                f"{BAYUT_BASE}/autocomplete",
                headers=self.headers,
                params={"query": "Dubai Marina"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
