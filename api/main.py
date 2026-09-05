"""FastAPI backend for Dubai Property Investor Bot.

Supports two data modes:
  - Mock data (default): local DuckDB with synthetic transactions
  - BayutAPI: real DLD-registered data via RapidAPI (set BAYUT_API_KEY in .env)
"""

import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from rag import structured_search
from calculators import calculate_mortgage, calculate_str
from developer_scorecard import get_all_developer_scores
from price_trends import get_all_trends, get_top_gainers, get_top_volume
from data_provider import MockDataProvider

app = FastAPI(title="Dubai Property Investor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data source selection ---
BAYUT_KEY = os.getenv("BAYUT_API_KEY", "")
_provider = None


def get_provider():
    """Lazy-init the appropriate data provider."""
    global _provider
    if _provider is not None:
        return _provider

    if BAYUT_KEY:
        try:
            from bayut_provider import BayutProvider
            _provider = BayutProvider(BAYUT_KEY)
            print("[API] Using BayutAPI (real DLD data)")
        except Exception as e:
            print(f"[API] BayutAPI init failed, falling back to mock: {e}")
            _provider = MockDataProvider()
    else:
        _provider = MockDataProvider()
        print("[API] Using mock data (set BAYUT_API_KEY for real data)")

    return _provider


@app.get("/api/health")
def health():
    provider = get_provider()
    data_source = "bayut" if BAYUT_KEY and "Bayut" in type(provider).__name__ else "mock"
    return {
        "status": "ok",
        "version": "2.0.0",
        "data_source": data_source,
        "bayut_configured": bool(BAYUT_KEY),
    }


@app.get("/api/data-source")
def data_source_info():
    """Return current data source status."""
    provider = get_provider()
    is_bayut = BAYUT_KEY and "Bayut" in type(provider).__name__
    return {
        "source": "bayut" if is_bayut else "mock",
        "bayut_configured": bool(BAYUT_KEY),
        "message": (
            "Real DLD-registered transaction data via BayutAPI"
            if is_bayut
            else "Synthetic mock data (set BAYUT_API_KEY in .env for real data)"
        ),
    }


@app.get("/api/communities")
def get_communities():
    result = structured_search("", filters=None)
    return {"communities": result["community_scores"], "total": len(result["community_scores"])}


@app.get("/api/transactions")
def get_transactions(
    community: Optional[str] = None,
    bedrooms: Optional[int] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = Query(default=50, le=200),
    use_live: bool = Query(default=False, description="Use live BayutAPI data"),
):
    if use_live and BAYUT_KEY:
        provider = get_provider()
        txns = provider.get_transactions(
            community=community,
            bedrooms=bedrooms,
            property_type=property_type,
            min_price=int(min_price) if min_price else None,
            max_price=int(max_price) if max_price else None,
            limit=limit,
        )
        return {"transactions": [vars(t) for t in txns], "total": len(txns), "source": "bayut"}

    # Default: use DuckDB (mock or pre-ingested data)
    result = structured_search("", filters=None)
    txns = result["transactions"]

    if community:
        txns = [t for t in txns if t["community"].lower() == community.lower()]
    if bedrooms is not None:
        txns = [t for t in txns if t["bedrooms"] == bedrooms]
    if property_type:
        txns = [t for t in txns if t["property_type"].lower() == property_type.lower()]
    if min_price is not None:
        txns = [t for t in txns if t["price_aed"] >= min_price]
    if max_price is not None:
        txns = [t for t in txns if t["price_aed"] <= max_price]

    return {"transactions": txns[:limit], "total": len(txns), "source": "mock"}


@app.get("/api/transactions/{transaction_id}")
def get_transaction(transaction_id: str):
    result = structured_search("", filters=None)
    for tx in result["transactions"]:
        if tx["transaction_id"] == transaction_id:
            return {"transaction": tx}
    return {"error": "Transaction not found"}, 404


@app.get("/api/mortgage")
def mortgage_calculator(
    property_price: float,
    down_payment_pct: float = 20,
    interest_rate: float = 4.5,
    tenure_years: int = 25,
    size_sqft: float = 800,
    service_charge_sqft: float = 15,
):
    result = calculate_mortgage(
        property_price=property_price,
        down_payment_pct=down_payment_pct / 100,
        interest_rate=interest_rate,
        tenure_years=tenure_years,
        size_sqft=int(size_sqft),
        service_charge_sqft=service_charge_sqft,
    )
    return {
        "loan_amount": result.loan_amount,
        "monthly_payment": result.monthly_payment,
        "total_interest": result.total_interest,
        "total_acquisition_cost": result.total_acquisition_cost,
        "dld_transfer_fee": result.dld_transfer_fee,
        "monthly_service_charges": result.monthly_service_charges,
        "down_payment": result.down_payment,
    }


@app.get("/api/str")
def str_calculator(
    community: str,
    bedrooms: int = 1,
    property_price: float = 1000000,
    size_sqft: float = 750,
    service_charge_sqft: float = 15,
):
    result = calculate_str(
        community, bedrooms, int(property_price), int(size_sqft), service_charge_sqft
    )
    if result is None:
        return {"error": f"No STR data for {community} {bedrooms}BR"}
    return {
        "community": result.community,
        "bedrooms": result.bedrooms,
        "avg_daily_rate": result.avg_daily_rate,
        "occupancy_rate": result.occupancy_rate,
        "gross_annual_revenue": result.annual_revenue,
        "net_annual_revenue": result.net_revenue,
        "gross_yield": result.gross_yield,
        "net_yield_after_fees": result.net_yield,
        "management_fee_rate": result.management_fee_pct,
        "total_fees": result.management_fee + result.annual_service_charges,
        "dtcm_license_fee": result.dtcm_license,
    }


@app.get("/api/developers")
def developers():
    scores = get_all_developer_scores()
    return {"developers": [vars(d) for d in scores]}


def _trend_to_points(t):
    """Convert a PriceTrend to a list of point dicts."""
    return [
        {"quarter": q, "avg_price": p, "transactions": v}
        for q, p, v in zip(t.quarters, t.prices, t.volumes)
    ]


@app.get("/api/trends")
def price_trends(community: Optional[str] = None):
    all_trends = get_all_trends()
    if community:
        trend = all_trends.get(community)
        if trend:
            return {"community": community, "data": _trend_to_points(trend)}
        return {"error": f"No trend data for {community}"}
    return {"trends": {k: _trend_to_points(v) for k, v in all_trends.items()}}


@app.get("/api/trends/top-gainers")
def top_gainers():
    gainers = get_top_gainers()
    return {"gainers": [
        {"community": g.community, "yoy_change_pct": g.yoy_change_pct, "trend_direction": g.trend_direction}
        for g in gainers
    ]}


@app.get("/api/trends/top-volume")
def top_volume():
    volume = get_top_volume()
    return {"volume": [
        {"community": v.community, "total_volume": sum(v.volumes), "yoy_change_pct": v.yoy_change_pct}
        for v in volume
    ]}


@app.get("/api/scores")
def investment_scores():
    result = structured_search("", filters=None)
    return {"scores": result["community_scores"]}


COMMUNITY_COORDS = {
    "Downtown Dubai": (25.1972, 55.2744),
    "Dubai Marina": (25.0800, 55.1400),
    "Palm Jumeirah": (25.1120, 55.1390),
    "Dubai Hills Estate": (25.1330, 55.2460),
    "JVC (Jumeirah Village Circle)": (25.0600, 55.2100),
    "Business Bay": (25.1850, 55.2650),
    "Arabian Ranches": (25.0500, 55.2800),
    "Sports City": (25.0400, 55.2200),
    "Discovery Gardens": (25.0800, 55.1400),
    "JLT (Jumeirah Lake Towers)": (25.0780, 55.1410),
    "The Springs": (25.0500, 55.1500),
    "Al Barsha": (25.1100, 55.2000),
    "Deira": (25.2600, 55.3000),
    "Bur Dubai": (25.2300, 55.2800),
    "International City": (25.1600, 55.4000),
    "Dubai Silicon Oasis": (25.1200, 55.3900),
    "Tilal Al Ghaf": (25.0200, 55.2500),
    "DAMAC Hills 2": (25.0100, 55.2700),
    "Dubai Creek Harbour": (25.2100, 55.3400),
    "Bluewaters Island": (25.0800, 55.1200),
    "Meydan": (25.1700, 55.2700),
    "Al Furjan": (25.0500, 55.1200),
    "Dubai South": (24.9200, 55.1600),
    "Town Square": (25.0700, 55.2500),
    "DIFC": (25.2100, 55.2800),
}


@app.get("/api/map")
def map_data():
    result = structured_search("", filters=None)
    scores = result["community_scores"]

    score_map = {s["community"]: s for s in scores}
    features = []
    for name, coords in COMMUNITY_COORDS.items():
        s = score_map.get(name, {})
        features.append({
            "community": name,
            "district": s.get("district", ""),
            "lat": coords[0],
            "lng": coords[1],
            "composite_score": s.get("composite_score", 0),
            "recommendation": s.get("recommendation", "HOLD"),
            "avg_net_yield": s.get("avg_net_yield_pct", 0),
            "avg_price": s.get("avg_price", 0),
        })
    return {"features": features}


@app.get("/api/chat")
def chat(q: str = Query(..., description="Investor question")):
    """RAG chat: retrieves data + generates answer via Groq/OpenAI."""
    from rag import rag_query
    result = rag_query(q)
    return {
        "answer": result["answer"],
        "communities": [s["community"] for s in result["structured"]["community_scores"][:5]],
        "transaction_count": len(result["structured"]["transactions"]),
    }
