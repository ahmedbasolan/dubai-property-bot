"""Interface for live data providers.

The analytics read DuckDB, built from DLD open-data exports (db_setup.py).
This interface is for live sources served alongside it: BayutProvider
(bayut_provider.py) implements it for live listings, and the stubs below mark
other sources that could.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


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

    Implementations:
    - BayutProvider (bayut_provider.py, live listings)
    - DLDInteractProvider (future, DXB Interact API)
    - PropertyFinderProvider (future, PF API)
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
