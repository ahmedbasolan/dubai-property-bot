"""FastAPI backend for Dubai Property Investor Bot.

Analytics read DuckDB, built from Dubai Land Department open data (registered
sales, Ejari rents, projects) by src/dld_loader.py and src/db_setup.py.
`/api/transactions?use_live=true` can instead serve live listings from BayutAPI
(asking prices, not registered sales) when BAYUT_API_KEY is set.
"""

import csv

import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag import get_transaction, list_transactions, structured_search
from calculators import calculate_mortgage, calculate_str
from db_setup import DATA_SOURCE
from config import COMMUNITY_MAP_PATH
from price_trends import (
    BASIS as TREND_BASIS,
    SOURCE as TREND_SOURCE,
    get_all_trends,
    get_price_trend,
    get_top_gainers,
    get_top_volume,
)

app = FastAPI(title="Dubai Property Investor API", version="2.0.0")

# Origins are configurable because the hardcoded localhost pair breaks any
# deployment. Comma-separated, e.g. CORS_ORIGINS="https://app.example.com".
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Chat rate limit ---
# Keyed by client IP. The endpoint spends real LLM credit, so an unauthenticated
# caller could otherwise run up the owner's bill. Set to 0 to disable.
CHAT_RATE_LIMIT_PER_MIN = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "20"))
_chat_hits: Dict[str, List[float]] = {}
_chat_hits_lock = threading.Lock()


def _check_chat_rate_limit(client_ip: str) -> None:
    if CHAT_RATE_LIMIT_PER_MIN <= 0:
        return
    now = time.time()
    with _chat_hits_lock:
        hits = [t for t in _chat_hits.get(client_ip, []) if now - t < 60]
        if len(hits) >= CHAT_RATE_LIMIT_PER_MIN:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Chat rate limit reached ({CHAT_RATE_LIMIT_PER_MIN}/min). "
                    "Wait a minute or raise CHAT_RATE_LIMIT_PER_MIN."
                ),
            )
        hits.append(now)
        _chat_hits[client_ip] = hits

# --- Data source selection ---
BAYUT_KEY = os.getenv("BAYUT_API_KEY", "")
_provider = None


def get_provider():
    """Lazy-init the live-listings provider; None when Bayut isn't available.

    Analytics never go through this: they always read DuckDB (DLD data).
    """
    global _provider
    if _provider is not None or not BAYUT_KEY:
        return _provider
    try:
        from bayut_provider import BayutProvider
        _provider = BayutProvider(BAYUT_KEY)
        print("[API] BayutAPI configured for live listings")
    except Exception as e:
        print(f"[API] BayutAPI init failed; live listings unavailable: {e}")
    return _provider


@app.get("/api/health")
def health():
    live = get_provider() is not None
    return {
        "status": "ok",
        "version": "2.0.0",
        # What /api/transactions?use_live=true would serve.
        "data_source": "bayut" if live else "dld",
        # What the analytics endpoints (/api/communities, /api/scores, /api/map)
        # actually read. They always query DuckDB, even when Bayut is configured,
        # so reporting a single "bayut" source here mislabelled the whole app.
        "default_source": "dld",
        "bayut_configured": bool(BAYUT_KEY),
    }


@app.get("/api/data-source")
def data_source_info():
    """Return current data source status."""
    is_bayut = get_provider() is not None
    return {
        "source": "bayut" if is_bayut else "dld",
        "bayut_configured": bool(BAYUT_KEY),
        "message": (
            "Live listings via BayutAPI (asking prices)"
            if is_bayut
            else f"{DATA_SOURCE}: apartment sales Jan-Sep 2026"
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
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    use_live: bool = Query(default=False, description="Use live BayutAPI data"),
):
    provider = get_provider() if use_live else None
    if provider is not None:
        txns = provider.get_transactions(
            community=community,
            bedrooms=bedrooms,
            property_type=property_type,
            min_price=int(min_price) if min_price else None,
            max_price=int(max_price) if max_price else None,
            limit=limit,
        )
        return {"transactions": [vars(t) for t in txns], "total": len(txns), "source": "bayut"}

    # Paginated listing over DuckDB. Not structured_search: that returns a
    # budgeted sample for the LLM and used to cap this endpoint at 40 of 73 rows.
    result = list_transactions(
        community=community,
        bedrooms=bedrooms,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset,
    )
    return {**result, "source": "dld"}


@app.get("/api/transactions/{transaction_id}")
def get_transaction_by_id(transaction_id: str):
    tx = get_transaction(transaction_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"transaction": tx}


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
        raise HTTPException(
            status_code=404,
            detail=f"No STR data for {community} {bedrooms}BR",
        )
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
    # DLD sales carry no developer, and the projects export only covers
    # projects completed in 2026, so a developer scorecard would rest on a few
    # percent of sales. Reported as unavailable rather than guessed.
    return {
        "developers": [],
        "source": "dld",
        "basis": ("Not available: DLD sale records have no developer field, and "
                  "the projects export links only projects completed in 2026."),
    }


def _trend_to_points(t):
    """Convert a PriceTrend to a list of point dicts."""
    return [
        {"quarter": q, "avg_price": p, "market_volume": v}
        for q, p, v in zip(t.quarters, t.prices, t.volumes)
    ]


@app.get("/api/trends")
def price_trends(community: Optional[str] = None):
    if community:
        trend = get_price_trend(community)
        if not trend.quarters:
            raise HTTPException(status_code=404, detail=f"No trend data for {community}")
        return {
            "community": trend.community,
            "data": _trend_to_points(trend),
            "source": TREND_SOURCE,
            "basis": TREND_BASIS,
        }
    all_trends = get_all_trends()
    return {
        "trends": {k: _trend_to_points(v) for k, v in all_trends.items()},
        "source": TREND_SOURCE,
        "basis": TREND_BASIS,
    }


@app.get("/api/trends/top-gainers")
def top_gainers():
    gainers = get_top_gainers()
    return {
        "gainers": [
            {"community": g.community, "momentum_pct": g.momentum_pct,
             "change_pct": g.change_pct, "trend_direction": g.trend_direction}
            for g in gainers
        ],
        "source": TREND_SOURCE,
    }


@app.get("/api/trends/top-volume")
def top_volume():
    volume = get_top_volume()
    return {
        "volume": [
            {"community": v.community, "total_volume": sum(v.volumes), "change_pct": v.change_pct}
            for v in volume
        ],
        "source": TREND_SOURCE,
    }


@app.get("/api/scores")
def investment_scores():
    result = structured_search("", filters=None)
    return {"scores": result["community_scores"]}


def _load_coords() -> Dict[str, tuple]:
    """Community -> (lat, lng), from OpenStreetMap (data/reference/community_coords.csv)."""
    with open(COMMUNITY_MAP_PATH.parent / "community_coords.csv", encoding="utf-8") as f:
        return {r["community"]: (float(r["lat"]), float(r["lng"])) for r in csv.DictReader(f)}


COMMUNITY_COORDS = _load_coords()


@app.get("/api/map")
def map_data():
    result = structured_search("", filters=None)
    scores = result["community_scores"]

    score_map = {s["community"]: s for s in scores}
    features = []
    for name, coords in COMMUNITY_COORDS.items():
        s = score_map.get(name)
        if not s:
            continue
        features.append({
            "community": name,
            "lat": coords[0],
            "lng": coords[1],
            # None when the community lacks rent data; the map shows it grey.
            "composite_score": s.get("composite_score"),
            "recommendation": s.get("recommendation"),
            "avg_net_yield": s.get("avg_net_yield_pct"),
            "avg_price": s.get("avg_price"),
            "avg_price_per_sqft": s.get("avg_price_per_sqft"),
        })
    return {"features": features}


class ChatRequest(BaseModel):
    """Chat payload.

    The API key travels in the request body, never in the query string: a key in
    a URL ends up in uvicorn access logs, browser history and proxy logs.
    """

    q: str = Field(..., min_length=2, max_length=1000)
    provider: Optional[str] = Field(default=None, pattern="^(groq|openai|openrouter)$")
    api_key: Optional[str] = Field(default=None, max_length=200)
    model: Optional[str] = Field(default=None, max_length=100)


def _chat_response(
    q: str,
    provider: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
) -> dict:
    from rag import get_llm_client, rag_query, retrieve

    if get_llm_client(provider=provider, api_key=api_key) is None:
        # No server key (the public demo runs without one) and none supplied:
        # answer from the data rather than returning a configuration error.
        structured = retrieve(q)["structured"]
        answer = _data_only_answer(
            q, structured,
            "No LLM key is configured on this server. Add your own Groq, OpenAI or "
            "OpenRouter key in the chat settings for written answers.",
        )
        return _chat_payload(answer, structured)

    try:
        result = rag_query(q, provider=provider, api_key=api_key, model=model)
        answer = result["answer"]
        structured = result["structured"]
    except Exception as e:
        # Graceful degradation: never 500 the chat UI — answer from DuckDB only
        structured = retrieve(q)["structured"]
        answer = _data_only_answer(
            q, structured, "The LLM is temporarily unavailable (likely its daily quota).")
        print(f"[CHAT] LLM unavailable, data-only fallback: {e}")

    return _chat_payload(answer, structured)


def _chat_payload(answer: str, structured: dict) -> dict:
    return {
        "answer": answer,
        "communities": [s["community"] for s in structured["community_scores"][:5]],
        "transaction_count": len(structured["transactions"]),
    }


@app.post("/api/chat")
def chat(chat_request: ChatRequest, request: Request):
    """RAG chat: retrieves data + generates answer via LLM."""
    _check_chat_rate_limit(request.client.host if request.client else "unknown")
    return _chat_response(
        chat_request.q, chat_request.provider, chat_request.api_key, chat_request.model
    )


@app.get("/api/chat", deprecated=True)
def chat_get(
    request: Request,
    q: str = Query(..., description="Investor question"),
    provider: Optional[str] = Query(None, description="LLM provider: groq, openai, openrouter"),
    model: Optional[str] = Query(None, description="Model override"),
):
    """Deprecated GET variant, kept for old links.

    It deliberately does not accept `api_key`: use POST /api/chat so keys are
    not written into access logs.
    """
    _check_chat_rate_limit(request.client.host if request.client else "unknown")
    if provider not in (None, "groq", "openai", "openrouter"):
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")
    return _chat_response(q, provider, None, model)


def _data_only_answer(query: str, structured: dict, reason: str) -> str:
    """Build a readable markdown answer from DuckDB when the LLM is unavailable."""
    scores = structured.get("community_scores", [])
    txns = structured.get("transactions", [])
    lines = [
        f"**{query}**",
        "",
        f"_{reason} This answer is generated from the data only._",
        "",
    ]
    pct = lambda v: "n/a" if v is None else f"{v:.2f}%"
    if scores:
        lines += [
            "### Communities by investment score",
            "",
            "| Community | Score | Gross Yield | Signal |",
            "|-----------|------:|------------:|--------|",
        ]
        for s in scores[:6]:
            score = "n/a" if s["composite_score"] is None else f"{s['composite_score']:.0f}"
            lines.append(
                f"| {s['community']} | {score} | {pct(s['avg_roi_pct'])} | {s['recommendation']} |"
            )
        lines.append("")
        top = scores[0]
        if top["composite_score"] is not None:
            lines.append(
                f"**Recommendation: {top['recommendation']}** - "
                f"**{top['community']}** leads with a score of "
                f"**{top['composite_score']:.0f}/100** and gross yield "
                f"**{top['avg_roi_pct']:.2f}%**."
            )
    if txns:
        lines += [
            "",
            "### Sample DLD transactions",
            "",
            "| ID | Date | Community | Status | Price |",
            "|----|------|-----------|--------|------:|",
        ]
        for t in txns[:5]:
            lines.append(
                f"| {t['transaction_id']} | {t['transaction_date']} | {t['community']} | "
                f"{t['handover_status']} | AED {t['price_aed']:,.0f} |"
            )
    lines += [
        "",
        "---",
        f"Source: {DATA_SOURCE}, Jan-Sep 2026. Net yields are before service charges.",
    ]
    return "\n".join(lines)
