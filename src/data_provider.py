"""DLD data adapter pattern.

Defines an interface for data providers so the mock data can be swapped
for real DLD data, Property Finder API, or Bayut API in the future.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import csv


@dataclass
class Transaction:
    """Standardized transaction record."""
    transaction_id: str
    community: str
    property_type: str
    bedrooms: int
    price_aed: int
    size_sqft: int
    transaction_date: str
    roi_pct: float
    developer: str
    handover_status: str
    floor_level: Optional[int] = None
    view_type: Optional[str] = None
    service_charge_aed_sqft: Optional[float] = None
    parking_spots: Optional[int] = None
    completion_year: Optional[int] = None
    furnishing: Optional[str] = None
    amenities: Optional[str] = None


@dataclass
class CommunitySummary:
    """Community-level aggregated data."""
    community_name: str
    district: str
    avg_price_per_sqft: float
    avg_roi_pct: float
    avg_net_yield_pct: float
    avg_service_charge: float
    transaction_count: int
    supply_risk: str
    composite_score: float
    recommendation: str


class DataProvider(ABC):
    """Abstract base class for data providers.

    Implement this interface to connect to real data sources:
    - MockDataProvider (current, local CSV/DuckDB)
    - DLDInteractProvider (future, DXB Interact API)
    - PropertyFinderProvider (future, PF API)
    - BayutProvider (future, Bayut API)
    """

    @abstractmethod
    def get_transactions(
        self,
        community: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        """Fetch transactions with optional filters."""
        pass

    @abstractmethod
    def get_community_summaries(self) -> List[CommunitySummary]:
        """Fetch aggregated community data."""
        pass

    @abstractmethod
    def get_supply_pipeline(self) -> List[Dict[str, Any]]:
        """Fetch supply pipeline data."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verify data source is accessible."""
        pass


class MockDataProvider(DataProvider):
    """Current implementation using local DuckDB."""

    def __init__(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from config import DB_PATH
        import duckdb
        self.conn = duckdb.connect(str(DB_PATH), read_only=True)

    def get_transactions(
        self,
        community: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        where_parts = []
        params = []
        if community:
            where_parts.append("community = ?")
            params.append(community)
        if min_price is not None:
            where_parts.append("price_aed >= ?")
            params.append(min_price)
        if max_price is not None:
            where_parts.append("price_aed <= ?")
            params.append(max_price)
        if bedrooms is not None:
            where_parts.append("bedrooms = ?")
            params.append(bedrooms)
        if property_type:
            where_parts.append("property_type = ?")
            params.append(property_type)

        where = " AND ".join(where_parts) if where_parts else "1=1"
        query = f"""
            SELECT transaction_id, community, property_type, bedrooms,
                   price_aed, size_sqft, transaction_date, roi_pct,
                   developer, handover_status, floor_level, view_type,
                   service_charge_aed_sqft, parking_spots, completion_year,
                   furnishing, amenities
            FROM transactions
            WHERE {where}
            ORDER BY net_yield_pct DESC
            LIMIT {limit}
        """
        rows = self.conn.execute(query, params).fetchall()
        return [
            Transaction(
                transaction_id=r[0], community=r[1], property_type=r[2],
                bedrooms=r[3], price_aed=r[4], size_sqft=r[5],
                transaction_date=str(r[6]), roi_pct=r[7], developer=r[8],
                handover_status=r[9], floor_level=r[10], view_type=r[11],
                service_charge_aed_sqft=r[12], parking_spots=r[13],
                completion_year=r[14], furnishing=r[15], amenities=r[16],
            )
            for r in rows
        ]

    def get_community_summaries(self) -> List[CommunitySummary]:
        rows = self.conn.execute("SELECT * FROM v_investment_scores ORDER BY composite_score DESC").fetchall()
        cols = [
            "community", "district", "transaction_count", "avg_price_per_sqft",
            "avg_roi_pct", "avg_net_yield_pct", "avg_service_charge", "avg_price",
            "supply_risk", "pipeline_pct_of_stock", "occupancy_rate",
            "master_developer", "price_score", "yield_score", "net_yield_score",
            "service_charge_score", "supply_risk_score", "occupancy_score",
            "developer_score", "recommendation", "composite_score",
        ]
        return [
            CommunitySummary(
                community_name=r[0], district=r[1],
                avg_price_per_sqft=r[3], avg_roi_pct=r[4],
                avg_net_yield_pct=r[5], avg_service_charge=r[6],
                transaction_count=r[2], supply_risk=r[8],
                composite_score=r[20], recommendation=r[19],
            )
            for r in rows
        ]

    def get_supply_pipeline(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM supply_pipeline").fetchall()
        cols = [
            "community_name", "existing_stock_units", "units_under_construction",
            "units_completed_last_12_months", "units_expected_next_24_months",
            "pipeline_pct_of_stock", "supply_risk",
        ]
        return [dict(zip(cols, row)) for row in rows]

    def health_check(self) -> bool:
        try:
            self.conn.execute("SELECT 1")
            return True
        except Exception:
            return False


# --- Future Provider Stubs ---

class DLDInteractProvider(DataProvider):
    """Future: Connect to DXB Interact API.

    Implementation notes:
    - DXB Interact provides community-level transaction summaries
    - Free tier: no API key required, rate-limited
    - Data format: JSON with monthly transaction volumes and price indices
    - Limitation: no building-level granularity, 2-4 week lag
    """

    def get_transactions(self, **kwargs) -> List[Transaction]:
        raise NotImplementedError("DLDInteractProvider not yet implemented")

    def get_community_summaries(self) -> List[CommunitySummary]:
        raise NotImplementedError("DLDInteractProvider not yet implemented")

    def get_supply_pipeline(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("DLDInteractProvider not yet implemented")

    def health_check(self) -> bool:
        return False


class PropertyFinderProvider(DataProvider):
    """Future: Connect to Property Finder API.

    Implementation notes:
    - PF provides listing data (asking prices, not transaction prices)
    - Requires API key (paid)
    - Data format: REST API with property listings
    - Limitation: asking prices 8-15% above actual transactions
    """

    def get_transactions(self, **kwargs) -> List[Transaction]:
        raise NotImplementedError("PropertyFinderProvider not yet implemented")

    def get_community_summaries(self) -> List[CommunitySummary]:
        raise NotImplementedError("PropertyFinderProvider not yet implemented")

    def get_supply_pipeline(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("PropertyFinderProvider not yet implemented")

    def health_check(self) -> bool:
        return False


def get_provider(provider_name: str = "mock") -> DataProvider:
    """Factory function to get the appropriate data provider."""
    providers = {
        "mock": MockDataProvider,
        "dld": DLDInteractProvider,
        "property_finder": PropertyFinderProvider,
    }
    provider_cls = providers.get(provider_name)
    if not provider_cls:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(providers.keys())}")
    return provider_cls()
