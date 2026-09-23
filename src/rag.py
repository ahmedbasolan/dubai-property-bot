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

from config import DB_PATH, CHROMA_DIR, LLM_TEMPERATURE, LLM_MAX_TOKENS

# Initialize clients
duck_conn = duckdb.connect(str(DB_PATH), read_only=True)
chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)

# Provider configs: base_url + default model
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "openai/gpt-oss-120b",
        "env_key": "GROQ_API_KEY",
    },
    "openai": {
        "base_url": None,
        "default_model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "env_key": "OPENROUTER_API_KEY",
    },
}


def get_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[OpenAI]:
    """Get LLM client for the given provider.

    Priority: explicit api_key > provider env var > auto-detect from env vars.
    """
    # If provider specified, use it
    if provider and provider in PROVIDERS:
        cfg = PROVIDERS[provider]
        key = api_key or os.environ.get(cfg["env_key"], "")
        if key:
            return OpenAI(api_key=key, base_url=cfg["base_url"])
        return None

    # If api_key given but no provider, auto-detect
    if api_key:
        # Try to detect provider from key prefix
        if api_key.startswith("gsk_"):
            return OpenAI(api_key=api_key, base_url=PROVIDERS["groq"]["base_url"])
        return OpenAI(api_key=api_key)

    # Auto-detect from env vars
    for prov_name, cfg in PROVIDERS.items():
        key = os.environ.get(cfg["env_key"])
        if key:
            return OpenAI(api_key=key, base_url=cfg["base_url"])

    return None


def get_model(provider: Optional[str] = None) -> str:
    """Get default model for the given provider."""
    if provider and provider in PROVIDERS:
        return PROVIDERS[provider]["default_model"]

    # Auto-detect
    if os.environ.get("GROQ_API_KEY"):
        return PROVIDERS["groq"]["default_model"]
    if os.environ.get("OPENROUTER_API_KEY"):
        return PROVIDERS["openrouter"]["default_model"]
    if os.environ.get("OPENAI_API_KEY"):
        return PROVIDERS["openai"]["default_model"]
    return PROVIDERS["groq"]["default_model"]


def structured_search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Search DuckDB for structured data (transactions + community scores)."""
    results = {"transactions": [], "community_scores": [], "supply_info": []}

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
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Generate answer using LLM with retrieved context."""
    client = get_llm_client(provider=provider, api_key=api_key)
    if not client:
        providers_list = ", ".join(PROVIDERS.keys())
        return (
            f"LLM not configured. Add one of these API keys to your .env:\n"
            f"  - GROQ_API_KEY (free: console.groq.com/keys)\n"
            f"  - OPENAI_API_KEY (platform.openai.com)\n"
            f"  - OPENROUTER_API_KEY (openrouter.ai)\n\n"
            f"Or enter your key in the chat UI.\n\n"
            f"Based on the data retrieved:\n\n" + context[:1500]
        )

    if model is None:
        model = get_model(provider)

    citations = []
    if structured["community_scores"]:
        for cs in structured["community_scores"][:5]:
            citations.append(
                f"{cs['community']}: Score {cs['composite_score']:.0f}/100, "
                f"Net Yield {cs['avg_net_yield_pct']:.2f}%, "
                f"Recommendation {cs['recommendation']}"
            )
    if structured["transactions"]:
        for tx in structured["transactions"][:5]:
            citations.append(
                f"{tx['transaction_id']}: {tx['community']}, "
                f"{tx['bedrooms']}BR, AED {tx['price_aed']:,}, "
                f"Net Yield {tx['net_yield_pct']:.2f}%"
            )

    system_prompt = """You are a Dubai real estate investment advisor. Answer investor questions using ONLY the provided data.

## YOUR ROLE
- Provide institutional-grade investment analysis for Dubai real estate
- Be concise, direct, and data-driven
- Speak like a trusted financial advisor — confident but not salesy

## RESPONSE RULES
1. NEVER calculate financial metrics yourself. Use only pre-computed values from the data.
2. Always cite specific data points (transaction IDs, community names, scores).
3. Distinguish between GROSS yield (ROI) and NET yield (after service charges, vacancy).
4. When data is insufficient, say so clearly.
5. Flag supply pipeline risks when relevant.

## FORMATTING — STRICT
You MUST use clean markdown formatting. Follow these rules exactly:

### Structure
- Start with a 1-line direct answer (bold the key finding)
- Follow with a short explanation (2-3 sentences max)
- Use a table if comparing 2+ communities
- End with a clear action: **INVEST**, **HOLD**, or **AVOID**

### Tables
When showing multiple communities, ALWAYS use a proper markdown table:
| Community | Score | Net Yield | Signal |
|-----------|-------|-----------|--------|
| JVC | 76 | 7.07% | INVEST |

### Lists
- Use bullet points for quick facts
- Keep each point to one line
- Bold the key metric or label

### What NOT to do
- Do NOT use pipe characters outside of tables
- Do NOT write [CITATIONS] — just cite inline
- Do NOT write long paragraphs — keep it scannable
- Do NOT use headers bigger than ### (h3)

## EXAMPLES

### Good response:
Based on the data, **Dubai Silicon Oasis offers the best risk-adjusted return** with a score of 86/100.

### Key metrics:
- **Net Yield:** 7.30% (above market average)
- **Gross ROI:** 9.3%
- **Supply Risk:** Medium (9.1% pipeline)
- **Occupancy:** 82%

| Community | Score | Net Yield | Supply Risk |
|-----------|-------|-----------|-------------|
| Dubai Silicon Oasis | 86 | 7.30% | Medium |
| Discovery Gardens | 86 | 7.08% | Medium |
| JVC | 76 | 7.07% | High |

**Recommendation: INVEST** — Strong fundamentals with moderate supply pipeline.

### Bad response (avoid this):
Here is a | pipe-delimited | table | that is | hard to read
[citations] [citations] [citations]
Long paragraph with no formatting that goes on and on and on...

## DATA FRESHNESS
All data is from Q1 2024. Always remind users to verify with DLD for current conditions."""

    user_prompt = f"""Question: {query}

=== DATA ===
{context}

=== REFERENCE DATA ===
{chr(10).join(citations)}

Answer using ONLY the data above. Use clean markdown formatting — proper tables, bullet points, bold for key metrics. Never use pipe-delimited text outside of tables. Never write [CITATIONS]."""

    last_err = None
    for attempt in range(4):
        try:
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
        except Exception as e:
            last_err = e
            msg = str(e)
            # Daily quota exhausted — fail fast, retrying won't help
            if "tokens per day" in msg or "TPD" in msg:
                raise RuntimeError(
                    "LLM daily token quota exhausted (Groq free tier 200k TPD). "
                    "Wait for reset, upgrade the tier, or set OPENAI_API_KEY/OPENROUTER_API_KEY."
                ) from e
            # Per-minute rate limit — short backoff then retry
            if "429" in msg or "rate_limit" in msg.lower() or "tokens per minute" in msg:
                import time
                time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s
                continue
            raise
    raise last_err


def rag_query(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Full RAG pipeline: structured + semantic search + generation."""
    structured = structured_search(query, filters=filters)
    semantic = semantic_search(query, n_results=3)
    context = build_context(structured, semantic)
    answer = generate_answer(
        query, context, structured, semantic,
        provider=provider, api_key=api_key, model=model,
    )

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

    api_key = (
        os.environ.get("GROQ_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    checks["api_key"] = bool(api_key)

    return checks
