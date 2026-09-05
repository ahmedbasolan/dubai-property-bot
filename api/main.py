"""FastAPI backend for Dubai Property Investor Bot."""

import sys
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from rag import structured_search
from calculators import calculate_mortgage, calculate_str
from developer_scorecard import get_all_developer_scores
from price_trends import get_all_trends, get_top_gainers, get_top_volume
from db_setup import get_scoring_engine

app = FastAPI(title="Dubai Property Investor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


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
):
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

    return {"transactions": txns[:limit], "total": len(txns)}


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
        size_sqft=size_sqft,
        service_charge_sqft=service_charge_sqft,
    )
    return {
        "loan_amount": result.loan_amount,
        "monthly_payment": result.monthly_payment,
        "total_interest": result.total_interest,
        "total_acquisition_cost": result.total_acquisition_cost,
        "dld_transfer_fee": result.dld_transfer_fee,
        "equity_at_year_5": result.equity_at_year_5,
        "equity_at_year_10": result.equity_at_year_10,
    }


@app.get("/api/str")
def str_calculator(
    community: str,
    bedrooms: int = 1,
    property_price: float = 1000000,
):
    result = calculate_str(community, bedrooms, property_price)
    if result is None:
        return {"error": f"No STR data for {community} {bedrooms}BR"}
    return {
        "community": result.community,
        "bedrooms": result.bedrooms,
        "avg_daily_rate": result.avg_daily_rate,
        "occupancy_rate": result.occupancy_rate,
        "gross_annual_revenue": result.gross_annual_revenue,
        "net_annual_revenue": result.net_annual_revenue,
        "gross_yield": result.gross_yield,
        "net_yield_after_fees": result.net_yield_after_fees,
        "management_fee_rate": result.management_fee_rate,
        "total_fees": result.total_fees,
        "dtcm_license_fee": result.dtcm_license_fee,
    }


@app.get("/api/developers")
def developers():
    scores = get_all_developer_scores()
    return {"developers": [vars(d) for d in scores]}


@app.get("/api/trends")
def price_trends(community: Optional[str] = None):
    all_trends = get_all_trends()
    if community:
        trend = all_trends.get(community)
        if trend:
            return {"community": community, "data": [vars(t) for t in trend]}
        return {"error": f"No trend data for {community}"}
    return {"trends": {k: [vars(t) for t in v] for k, v in all_trends.items()}}


@app.get("/api/trends/top-gainers")
def top_gainers():
    gainers = get_top_gainers()
    return {"gainers": [vars(g) for g in gainers]}


@app.get("/api/trends/top-volume")
def top_volume():
    volume = get_top_volume()
    return {"volume": [vars(v) for v in volume]}


@app.get("/api/scores")
def investment_scores():
    engine = get_scoring_engine()
    scores = engine.get_community_scores()
    return {"scores": scores}


@app.get("/api/map")
def map_data():
    from generate_data import generate_community_profiles
    profiles = generate_community_profiles()
    engine = get_scoring_engine()
    scores = engine.get_community_scores()

    score_map = {s["community"]: s for s in scores}
    features = []
    for p in profiles:
        s = score_map.get(p["community"], {})
        features.append({
            "community": p["community"],
            "district": p["district"],
            "lat": p["lat"],
            "lng": p["lng"],
            "composite_score": s.get("composite_score", 0),
            "recommendation": s.get("recommendation", "HOLD"),
            "avg_net_yield": s.get("avg_net_yield_pct", 0),
            "avg_price": s.get("avg_price", 0),
        })
    return {"features": features}
