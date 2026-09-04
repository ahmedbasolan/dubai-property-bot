"""RAG pipeline: DuckDB for structured queries + ChromaDB for semantic search."""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))

import duckdb
import chromadb
from chromadb.config import Settings
from openai import OpenAI

from config import DB_PATH, CHROMA_DIR, DEFAULT_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

# Initialize clients
duck_conn = duckdb.connect(str(DB_PATH), read_only=True)
chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)


def get_openai_client() -> OpenAI:
    """Get OpenAI client, using OpenRouter if OPENROUTER_API_KEY is set."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = None
    if os.environ.get("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"
    return OpenAI(api_key=api_key, base_url=base_url)


def structured_search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Search DuckDB for structured data (transactions + community scores)."""
    results = {"transactions": [], "community_scores": [], "supply_info": []}

    # Build WHERE clause
    where_parts = []
    params = []
    if filters:
        if filters.get("community"):
            where_parts.append("community = ?")
            params.append(filters["community"])
        if filters.get("min_price") is not None:
            where_parts.append("price_aed >= ?")
            params.append(filters["min_price"])
        if filters.get("max_price") is not None:
            where_parts.append("price_aed <= ?")
            params.append(filters["max_price"])
        if filters.get("bedrooms") is not None:
            where_parts.append("bedrooms = ?")
            params.append(filters["bedrooms"])
        if filters.get("property_type"):
            where_parts.append("property_type = ?")
            params.append(filters["property_type"])

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    # Query transactions with net yield
    tx_query = f"""
        SELECT transaction_id, community, property_type, bedrooms,
               price_aed, size_sqft, roi_pct, floor_level, view_type,
               service_charge_aed_sqft, parking_spots, completion_year,
               furnishing, developer, handover_status,
               estimated_annual_rent, annual_service_charges,
               net_yield_pct, price_per_sqft
        FROM v_net_yield
        WHERE {where_clause}
        ORDER BY net_yield_pct DESC
        LIMIT 15
    """
    tx_rows = duck_conn.execute(tx_query, params).fetchall()
    tx_cols = [
        "transaction_id", "community", "property_type", "bedrooms",
        "price_aed", "size_sqft", "roi_pct", "floor_level", "view_type",
        "service_charge_aed_sqft", "parking_spots", "completion_year",
        "furnishing", "developer", "handover_status",
        "estimated_annual_rent", "annual_service_charges",
        "net_yield_pct", "price_per_sqft",
    ]
    results["transactions"] = [dict(zip(tx_cols, row)) for row in tx_rows]

    # Query community investment scores
    score_query = """
        SELECT * FROM v_investment_scores
        ORDER BY composite_score DESC
        LIMIT 10
    """
    score_rows = duck_conn.execute(score_query).fetchall()
    score_cols = [
        "community", "district", "transaction_count", "avg_price_per_sqft",
        "avg_roi_pct", "avg_net_yield_pct", "avg_service_charge", "avg_price",
        "supply_risk", "pipeline_pct_of_stock", "occupancy_rate",
        "master_developer", "price_score", "yield_score", "net_yield_score",
        "service_charge_score", "supply_risk_score", "occupancy_score",
        "developer_score", "recommendation", "composite_score",
    ]
    results["community_scores"] = [dict(zip(score_cols, row)) for row in score_rows]

    # Supply pipeline info
    supply_query = """
        SELECT * FROM supply_pipeline
        ORDER BY pipeline_pct_of_stock DESC
    """
    supply_rows = duck_conn.execute(supply_query).fetchall()
    supply_cols = [
        "community_name", "existing_stock_units", "units_under_construction",
        "units_completed_last_12_months", "units_expected_next_24_months",
        "pipeline_pct_of_stock", "supply_risk",
    ]
    results["supply_info"] = [dict(zip(supply_cols, row)) for row in supply_rows]

    return results


def semantic_search(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Search ChromaDB for market reports (semantic)."""
    collection = chroma_client.get_collection("market_reports")
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    docs = []
    for i in range(len(results["ids"][0])):
        docs.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return docs


def build_context(
    structured: Dict[str, Any],
    semantic: List[Dict[str, Any]],
) -> str:
    """Build context string from both search results."""
    parts = []

    # Community scores (most valuable for investment decisions)
    if structured["community_scores"]:
        parts.append("=== COMMUNITY INVESTMENT SCORES ===")
        for cs in structured["community_scores"][:8]:
            parts.append(
                f"[{cs['community']}] "
                f"District: {cs['district']}, "
                f"Avg Price/sqft: AED {cs['avg_price_per_sqft']:,.0f}, "
                f"ROI: {cs['avg_roi_pct']:.1f}%, "
                f"Net Yield: {cs['avg_net_yield_pct']:.2f}%, "
                f"Service Charge: AED {cs['avg_service_charge']:.1f}/sqft, "
                f"Supply Risk: {cs['supply_risk']} ({cs['pipeline_pct_of_stock']:.1f}% pipeline), "
                f"Occupancy: {cs['occupancy_rate']:.0%}, "
                f"Developer: {cs['master_developer']}, "
                f"Scores - Price:{cs['price_score']} Yield:{cs['yield_score']} Net:{cs['net_yield_score']} "
                f"SC:{cs['service_charge_score']} Supply:{cs['supply_risk_score']} "
                f"Occ:{cs['occupancy_score']} Dev:{cs['developer_score']}, "
                f"Recommendation: {cs['recommendation']} (Score: {cs['composite_score']:.0f}/100)"
            )

    # Filtered transactions
    if structured["transactions"]:
        parts.append("\n=== MATCHING TRANSACTIONS ===")
        for tx in structured["transactions"][:10]:
            parts.append(
                f"[{tx['transaction_id']}] "
                f"{tx['community']}, {tx['bedrooms']}BR {tx['property_type']}, "
                f"AED {tx['price_aed']:,}, {tx['size_sqft']}sqft, "
                f"ROI {tx['roi_pct']}%, Net Yield {tx['net_yield_pct']:.2f}%, "
                f"Price/sqft: AED {tx['price_per_sqft']:,.0f}, "
                f"Floor: {tx['floor_level']}, View: {tx['view_type']}, "
                f"Service Charge: AED {tx['service_charge_aed_sqft']}/sqft, "
                f"Parking: {tx['parking_spots']}, "
                f"Furnishing: {tx['furnishing']}, "
                f"Developer: {tx['developer']}, {tx['handover_status']}"
            )

    # Supply pipeline (risk context)
    high_supply = [s for s in structured["supply_info"] if s["supply_risk"] == "high"]
    if high_supply:
        parts.append("\n=== HIGH SUPPLY RISK COMMUNITIES ===")
        for s in high_supply[:5]:
            parts.append(
                f"[{s['community_name']}] "
                f"Pipeline: {s['pipeline_pct_of_stock']:.1f}% of existing stock "
                f"({s['units_expected_next_24_months']:,} units in 24 months), "
                f"Risk: HIGH"
            )

    # Market reports (semantic)
    if semantic:
        parts.append("\n=== MARKET REPORTS ===")
        for doc in semantic:
            community = doc["metadata"].get("community", "General")
            section = doc["metadata"].get("section", "")
            parts.append(f"[{community} - {section}]\n{doc['text']}\n")

    return "\n".join(parts)


def generate_answer(
    query: str,
    context: str,
    structured: Dict[str, Any],
    semantic: List[Dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> str:
    """Generate answer using LLM with retrieved context."""
    client = get_openai_client()

    # Build citations
    citations = []
    if structured["community_scores"]:
        for cs in structured["community_scores"][:5]:
            citations.append(
                f"- {cs['community']}: {cs['recommendation']} "
                f"(Score: {cs['composite_score']:.0f}/100, "
                f"Net Yield: {cs['avg_net_yield_pct']:.2f}%, "
                f"Supply Risk: {cs['supply_risk']})"
            )
    if structured["transactions"]:
        for tx in structured["transactions"][:5]:
            citations.append(
                f"- Transaction {tx['transaction_id']}: {tx['community']}, "
                f"{tx['bedrooms']}BR, AED {tx['price_aed']:,}, "
                f"Net Yield {tx['net_yield_pct']:.2f}%"
            )

    system_prompt = """You are a Dubai real estate investment advisor. Answer investor questions using ONLY the provided data.

CRITICAL RULES:
1. NEVER calculate financial metrics yourself. Use only pre-computed values from the data.
2. Always cite specific data points (transaction IDs, community scores).
3. When discussing yield, always distinguish between GROSS yield (ROI) and NET yield (after service charges, management fees, vacancy).
4. When data is insufficient, say so clearly.
5. Show confidence level based on data completeness.
6. Flag supply pipeline risks when relevant.

Data freshness: All data is from Q1 2024 mock dataset. Verify with DLD for current market conditions.

Response format:
- Start with a direct answer
- Support with specific data points
- Mention any caveats or risks
- End with a clear recommendation (Invest/Hold/Avoid) if applicable"""

    user_prompt = f"""Investor Question: {query}

=== RETRIEVED DATA ===
{context}

=== CITATIONS ===
{chr(10).join(citations)}

Answer the question using ONLY the data above. Cite specific sources."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )

    return response.choices[0].message.content


def rag_query(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Full RAG pipeline: structured + semantic search + generation."""
    # Structured search (DuckDB)
    structured = structured_search(query, filters=filters)

    # Semantic search (ChromaDB)
    semantic = semantic_search(query, n_results=3)

    # Build context
    context = build_context(structured, semantic)

    # Generate answer
    answer = generate_answer(query, context, structured, semantic, model=model)

    return {
        "answer": answer,
        "structured": structured,
        "semantic": semantic,
        "context": context,
    }


def health_check() -> Dict[str, bool]:
    """Verify all dependencies are working."""
    checks = {}
    try:
        duck_conn.execute("SELECT 1")
        checks["duckdb"] = True
    except duckdb.Error:
        checks["duckdb"] = False

    try:
        chroma_client.get_collection("transactions")
        checks["chromadb_transactions"] = True
    except Exception:
        checks["chromadb_transactions"] = False

    try:
        chroma_client.get_collection("market_reports")
        checks["chromadb_reports"] = True
    except Exception:
        checks["chromadb_reports"] = False

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    checks["api_key"] = bool(api_key)

    return checks
