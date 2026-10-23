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
from filters import extract_filters
from price_trends import get_price_trend, BASIS as TREND_BASIS

# Rows of transaction detail handed to the model. Each row costs roughly 110
# tokens, so 40 stays around 5k tokens including scores, supply and semantic
# context - inside the 8k/min budget of the Groq free tier, which the previous
# single-request limit could already breach.
TX_CONTEXT_LIMIT = 40

# Groq's free tier counts the prompt *and* max_tokens against 8k tokens per
# minute. The request budget below is a safety net for a growing dataset: it
# trims the answer ceiling rather than letting a large context turn into a 413.
MAX_REQUEST_TOKENS = 7600
MIN_ANSWER_TOKENS = 400

# Column order of a transaction row, shared by the RAG context sample and the
# REST listing. Kept as one list so the two cannot drift apart: the API used to
# reuse the context sample and silently returned 40 of 73 rows.
TX_COLUMNS = [
    "transaction_id", "community", "property_type", "bedrooms",
    "price_aed", "size_sqft", "transaction_date", "roi_pct",
    "project", "developer", "handover_status",
    "estimated_annual_rent", "net_yield_pct", "price_per_sqft",
]
_TX_SELECT = ",\n               ".join(TX_COLUMNS)

# Initialize clients
duck_conn = duckdb.connect(str(DB_PATH), read_only=True)


def _db() -> duckdb.DuckDBPyConnection:
    """A cursor of its own for each query.

    FastAPI runs handlers on a thread pool, and one DuckDB connection shared
    across threads interleaves results: two concurrent page loads made one
    query's rows come back from another. A cursor is a separate handle onto
    the same database, so concurrent requests stay isolated.
    """
    return duck_conn.cursor()
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


def _like_param(value: str) -> str:
    """Escape LIKE wildcards so a filter value is matched literally."""
    escaped = str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped


def _relax_empty_filter(
    where_clause: str,
    params: List[Any],
    filters: Optional[Dict[str, Any]],
    results: Dict[str, Any],
) -> tuple[str, List[Any]]:
    """Drop the filter entirely if it matches nothing.

    A filter that selects zero rows is indistinguishable, to the model, from a
    property type that does not exist in the dataset. Rather than let a
    mis-extracted constraint produce "no such property is available", fall
    back to the unbiased sample and record that it happened.
    """
    if not filters or where_clause == "1=1":
        return where_clause, params

    count = _db().execute(
        f"SELECT COUNT(*) FROM v_net_yield WHERE {where_clause}", params
    ).fetchone()[0]
    if count:
        return where_clause, params

    results["relaxed_filters"] = {
        "requested": dict(filters),
        "reason": "filter matched 0 transactions; retried without it",
    }
    return "1=1", []


def structured_search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Search DuckDB for structured data (transactions + community scores)."""
    results = {"transactions": [], "community_scores": [], "supply_info": []}

    where_parts = []
    params = []
    communities = list((filters or {}).get("communities") or [])
    if filters:
        if filters.get("community"):
            # ILIKE, not =: the column holds 'Business Bay' and 'Villa', so a
            # case-mismatched filter would return zero rows and the model would
            # report that no such property exists.
            where_parts.append("community ILIKE ?")
            params.append(_like_param(filters["community"]))
        elif communities:
            # A comparison is scoped to the communities named in the question.
            # Leaving it unfiltered returned 24 scores, then build_context showed
            # the top 8 - both compared communities could be missing, and the
            # model correctly answered "no scores available".
            placeholders = ", ".join("?" for _ in communities)
            where_parts.append(f"community IN ({placeholders})")
            params.extend(communities)
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
            where_parts.append("property_type ILIKE ?")
            params.append(_like_param(filters["property_type"]))

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    where_clause, params = _relax_empty_filter(
        where_clause, params, filters, results
    )

    # A plain "ORDER BY net_yield_pct DESC LIMIT 15" is dominated by the
    # highest-yielding communities: it exposed only 5 of 24 communities, and
    # zero villas or penthouses, so the model correctly reported that no villa
    # data existed while the database held 9.
    #
    # Sample across the distribution instead. Groups are ranked so that rare
    # ones (a single penthouse) are never truncated behind common ones (63
    # apartments), and the per-group cap is derived from the group count so the
    # row budget is actually spent: a hard cap of 2 would show only 2 of a
    # community's 4 transactions when a filter narrowed the set to it.
    #
    # With DLD data every row is an apartment, so the groups are community x
    # ready/off-plan. Within a group, sample across the price range (not the
    # top yields) so the model sees typical units, not only the outliers.
    group_count = _db().execute(
        f"""SELECT COUNT(*) FROM (
              SELECT 1 FROM v_net_yield WHERE {where_clause}
              GROUP BY community, handover_status
            )""",
        params,
    ).fetchone()[0]
    per_group = max(2, -(-TX_CONTEXT_LIMIT // group_count)) if group_count else 2

    tx_query = f"""
        WITH banded AS (
            SELECT *,
                   ntile({per_group}) OVER (
                       PARTITION BY community, handover_status ORDER BY price_aed) AS price_band,
                   count(*) OVER (PARTITION BY community, handover_status) AS group_size
            FROM v_net_yield
            WHERE {where_clause}
        )
        SELECT {_TX_SELECT}
        FROM banded
        QUALIFY row_number() OVER (
            PARTITION BY community, handover_status, price_band
            ORDER BY hash(transaction_id)
        ) = 1
        ORDER BY group_size ASC, community ASC, handover_status ASC, price_aed ASC
        LIMIT {TX_CONTEXT_LIMIT}
    """
    results["_per_group"] = per_group
    tx_rows = _db().execute(tx_query, params).fetchall()
    results["transactions"] = [dict(zip(TX_COLUMNS, row)) for row in tx_rows]

    score_query = """
        SELECT * FROM v_investment_scores
        ORDER BY composite_score DESC
    """
    # Scope scores and supply to the filtered community as well. Returning all
    # 24 communities' scores next to one community's transactions invites the
    # model to attribute another community's yield to the one asked about.
    # Only the community filter applies: v_investment_scores has no price or
    # bedroom columns.
    scope_where, scope_params = ("1=1", [])
    if filters and filters.get("community"):
        scope_where = "community ILIKE ?"
        scope_params = [_like_param(filters["community"])]
    elif communities:
        placeholders = ", ".join("?" for _ in communities)
        scope_where = f"community IN ({placeholders})"
        scope_params = communities

    results["community_scores"] = _rows_as_dicts(
        f"""SELECT * FROM v_investment_scores WHERE {scope_where}
            ORDER BY composite_score DESC NULLS LAST, community""",
        scope_params,
    )

    # Scoped price trend: only for a single-community query. A comparison or a
    # broad question would need 24 series, which is exactly the kind of context
    # bloat that produced the eval's 413. One compact line keeps trend answers
    # anchored to the same DuckDB series that /api/trends serves.
    community = (filters or {}).get("community")
    if community:
        trend = get_price_trend(community)
        if trend.quarters:
            results["price_trend"] = {
                "community": trend.community,
                "first_quarter": trend.quarters[0],
                "first_price": trend.prices[0],
                "latest_quarter": trend.quarters[-1],
                "latest_price": trend.prices[-1],
                "change_pct": trend.change_pct,
                "momentum_pct": trend.momentum_pct,
                "basis": TREND_BASIS,
            }

    # supply_pipeline names the column community_name, not community.
    supply_scope = "1=1"
    supply_params: List[Any] = []
    if filters and filters.get("community"):
        supply_scope = "community_name ILIKE ?"
        supply_params = [_like_param(filters["community"])]
    elif communities:
        placeholders = ", ".join("?" for _ in communities)
        supply_scope = f"community_name IN ({placeholders})"
        supply_params = communities

    results["supply_info"] = _rows_as_dicts(
        f"""SELECT * FROM supply_pipeline WHERE {supply_scope}
            ORDER BY pipeline_ratio DESC""",
        supply_params,
    )

    results["coverage"] = _coverage_summary(where_clause, params)
    return results


def _rows_as_dicts(query: str, params: List[Any]) -> List[Dict[str, Any]]:
    """Run a query and key each row by the view's own column names."""
    cursor = _db().execute(query, params)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def list_transactions(
    community: Optional[str] = None,
    bedrooms: Optional[int] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Full, paginated transaction listing for the REST API.

    Deliberately separate from `structured_search`: that function returns a
    budgeted, representative *sample* for the LLM prompt (TX_CONTEXT_LIMIT
    rows). Reusing it here truncated `/api/transactions` to 40 of 73 rows and
    reported the sample size as the total, so the properties page silently lost
    a third of the dataset.
    """
    where_parts: List[str] = []
    params: List[Any] = []
    if community:
        where_parts.append("community ILIKE ?")
        params.append(_like_param(community))
    if bedrooms is not None:
        where_parts.append("bedrooms = ?")
        params.append(bedrooms)
    if property_type:
        where_parts.append("property_type ILIKE ?")
        params.append(_like_param(property_type))
    if min_price is not None:
        where_parts.append("price_aed >= ?")
        params.append(min_price)
    if max_price is not None:
        where_parts.append("price_aed <= ?")
        params.append(max_price)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    total = _db().execute(
        f"SELECT COUNT(*) FROM v_net_yield WHERE {where_clause}", params
    ).fetchone()[0]

    rows = _db().execute(
        f"""SELECT {_TX_SELECT}
            FROM v_net_yield
            WHERE {where_clause}
            ORDER BY transaction_date DESC, transaction_id ASC
            LIMIT ? OFFSET ?""",
        params + [int(limit), int(offset)],
    ).fetchall()

    return {
        "transactions": [dict(zip(TX_COLUMNS, row)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_transaction(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single transaction by ID, or None if it does not exist."""
    row = _db().execute(
        f"SELECT {_TX_SELECT} FROM v_net_yield WHERE transaction_id = ?",
        [transaction_id],
    ).fetchone()
    return dict(zip(TX_COLUMNS, row)) if row else None


def _coverage_summary(where_clause: str, params: List[Any]) -> Dict[str, Any]:
    """What the dataset holds vs what made it into the prompt.

    Without this the model cannot distinguish "no such property" from
    "not in the rows I was shown", and it answers the second one.
    """
    total = _db().execute(
        f"SELECT COUNT(*) FROM v_net_yield WHERE {where_clause}", params
    ).fetchone()[0]

    by_type = _db().execute(
        f"""SELECT property_type, COUNT(*) FROM v_net_yield
            WHERE {where_clause} GROUP BY 1 ORDER BY 2 DESC""",
        params,
    ).fetchall()
    by_handover = _db().execute(
        f"""SELECT handover_status, COUNT(*) FROM v_net_yield
            WHERE {where_clause} GROUP BY 1 ORDER BY 2 DESC""",
        params,
    ).fetchall()
    by_community = _db().execute(
        f"""SELECT community, COUNT(*) FROM v_net_yield
            WHERE {where_clause} GROUP BY 1 ORDER BY 2 DESC""",
        params,
    ).fetchall()
    by_bedrooms = _db().execute(
        f"""SELECT bedrooms, COUNT(*) FROM v_net_yield
            WHERE {where_clause} GROUP BY 1 ORDER BY 1""",
        params,
    ).fetchall()

    return {
        "total_matching": total,
        "communities_in_dataset": len(by_community),
        "transactions_by_type": {k: v for k, v in by_type},
        "transactions_by_handover": {k: v for k, v in by_handover},
        "transactions_by_bedrooms": {k: v for k, v in by_bedrooms},
        "sample_note": (
            f"{total} transactions match this query. A sample spread across the "
            f"price range of each community (ready and off-plan) is shown below, "
            f"capped at {TX_CONTEXT_LIMIT} rows; totals above are exact."
        ),
    }


def has_report(community: Optional[str]) -> bool:
    """Whether build_reports.py produced a report for this exact community.

    Reports carry the DuckDB community name in their metadata. A community
    without one stays unscoped and the gap is announced, rather than serving
    one community's report as another's.
    """
    if not community:
        return False
    try:
        found = chroma_client.get_collection("market_reports").get(
            where={"community": community}, limit=1)
    except Exception:
        return False
    return bool(found["ids"])


def semantic_search(
    query: str,
    n_results: int = 5,
    community: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search ChromaDB for market reports (semantic).

    When `community` names a community that has its own market report, the
    search is scoped to it. Unscoped, a Downtown question ranked a Dubai Hills
    report first, and a DAMAC Hills 2 question was answered from the Dubai Hills
    report - two different communities presented as one.
    """
    collection = chroma_client.get_collection("market_reports")

    where = {"community": community} if has_report(community) else None
    count = collection.count()

    if count == 0:
        return []

    kwargs: Dict[str, Any] = {
        "query_texts": [query],
        "n_results": min(n_results, count),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

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

    applied = structured.get("applied_filters")
    if applied:
        parts.append("=== FILTERS APPLIED TO THIS QUERY ===")
        parts.append(
            "Restricting to: "
            + ", ".join(f"{k}={v}" for k, v in applied.items())
        )
        parts.append(
            "The counts below apply to this filtered set. Filters are extracted "
            "deterministically and deliberately left off when ambiguous, so a "
            "missing community or property type here may still exist in the "
            "wider dataset - say so rather than claiming it does not exist."
        )

    # Rendered independently of applied_filters: these notes are exactly the
    # cases where the model is most likely to over-claim.
    for note in structured.get("skipped_filters", []):
        parts.append(f"  note: {note}")

    # Reported independently of applied_filters: a filter that had to be dropped
    # is exactly the case where the model is most likely to over-claim.
    if structured.get("relaxed_filters"):
        parts.append("=== FILTER RELAXED ===")
        parts.append(
            f"{structured['relaxed_filters']['reason']} "
            f"(requested: {structured['relaxed_filters']['requested']}). "
            "The rows below are unfiltered, so treat any single-community or "
            "per-property-type figure with care."
        )

    coverage = structured.get("coverage")
    if coverage:
        parts.append("=== DATASET COVERAGE (exact counts, not a sample) ===")
        parts.append(
            f"Transactions matching this query: {coverage['total_matching']} "
            f"across {coverage['communities_in_dataset']} communities."
        )
        if coverage["transactions_by_type"]:
            parts.append(
                "By property type: "
                + ", ".join(
                    f"{k}={v}" for k, v in coverage["transactions_by_type"].items()
                )
            )
        if coverage["transactions_by_handover"]:
            parts.append(
                "By handover status: "
                + ", ".join(
                    f"{k}={v}" for k, v in coverage["transactions_by_handover"].items()
                )
            )
        if coverage.get("transactions_by_bedrooms"):
            parts.append(
                "By bedrooms (exact): "
                + ", ".join(
                    f"{k}BR={v}"
                    for k, v in coverage["transactions_by_bedrooms"].items()
                )
            )
        parts.append(coverage["sample_note"])
        parts.append(
            "IMPORTANT: the counts above are exact totals for the whole matching "
            "set. The rows below are a sample. Never add up the sample rows to "
            "report a total, and never claim data is missing when the counts "
            "above show otherwise."
        )

    if structured["community_scores"]:
        parts.append("\n=== COMMUNITY INVESTMENT SCORES (DLD data, Jan-Sep 2026) ===")
        for cs in structured["community_scores"][:8]:
            if cs["composite_score"] is None:
                yield_part = (f"Yield: INSUFFICIENT DATA (only {cs['yield_projects']} projects with "
                              f"both rents and sales, {cs['matched_contracts']} matched Ejari contracts; "
                              "do not estimate one)")
                score_part = "Recommendation: INSUFFICIENT DATA (no score)"
            else:
                yield_part = (f"Gross yield: {cs['avg_roi_pct']:.2f}%, "
                              f"Net yield before service charges: {cs['avg_net_yield_pct']:.2f}% "
                              f"(same-project: {cs['yield_projects']} projects, "
                              f"{cs['matched_contracts']} new Ejari contracts)")
                score_part = (f"Recommendation: {cs['recommendation']} "
                              f"(Score: {cs['composite_score']:.0f}/100)")
            momentum = ("n/a" if cs["price_momentum_pct"] is None
                        else f"{cs['price_momentum_pct']:+.1f}% (same {cs['paired_projects']} projects, Q1->Q3)")
            parts.append(
                f"[{cs['community']}] "
                f"Median ready price/sqft: AED {cs['avg_price_per_sqft']:,.0f}, "
                f"Ready sales: {cs['transaction_count']}, "
                f"{yield_part}, "
                f"Price momentum: {momentum}, "
                f"Supply: {cs['offplan_sales']} off-plan vs {cs['transaction_count']} ready sales "
                f"(ratio {cs['pipeline_ratio']}, risk {cs['supply_risk']}), "
                f"Grades - Yield:{cs['yield_score'] or 'n/a'} Supply:{cs['supply_risk_score']} "
                f"Momentum:{cs['momentum_score'] or 'n/a'} Liquidity:{cs['liquidity_score']}, "
                f"{score_part}"
            )

    trend = structured.get("price_trend")
    if trend:
        parts.append("\n=== PRICE TREND (DLD ready sales) ===")
        parts.append(
            f"[{trend['community']}] {trend['first_quarter']} "
            f"AED {trend['first_price']:,.0f}/sqft -> "
            f"{trend['latest_quarter']} AED {trend['latest_price']:,.0f}/sqft "
            f"({trend['change_pct']:+.1f}% on community medians). {trend['basis']}"
        )

    if structured["transactions"]:
        parts.append("\n=== SAMPLE DLD TRANSACTIONS ===")
        for tx in structured["transactions"]:
            beds = "Studio" if tx["bedrooms"] == 0 else (
                "unknown beds" if tx["bedrooms"] is None else f"{tx['bedrooms']}BR")
            est = ("estimated gross yield n/a (insufficient rent data)"
                   if tx["roi_pct"] is None else
                   f"estimated gross yield {tx['roi_pct']}% / net {tx['net_yield_pct']:.2f}% "
                   f"(project or community rent per m2 x unit size)")
            parts.append(
                f"[{tx['transaction_id']}] {tx['transaction_date']}, "
                f"{tx['community']}, {beds} {tx['property_type']}, "
                f"{tx['handover_status']}, AED {tx['price_aed']:,.0f}, {tx['size_sqft']:,.0f} sqft "
                f"(AED {tx['price_per_sqft']:,.0f}/sqft), project: {tx['project'] or 'n/a'}, "
                f"{est}"
            )

    high_supply = [
        s for s in structured["supply_info"]
        if str(s["supply_risk"]).lower() == "high"
    ]
    if high_supply:
        parts.append("\n=== HIGH SUPPLY RISK COMMUNITIES ===")
        for s in high_supply[:5]:
            parts.append(
                f"[{s['community_name']}] "
                f"{s['offplan_sales']:,} off-plan vs {s['ready_sales']:,} ready sales in 2026 "
                f"(ratio {s['pipeline_ratio']}): stock still to be handed over. "
                f"{s['units_completed_2026']:,} units handed over so far in 2026. Risk: HIGH"
            )

    if semantic:
        parts.append("\n=== MARKET REPORTS ===")
        for doc in semantic:
            community = doc["metadata"].get("community", "General")
            section = doc["metadata"].get("section", "")
            parts.append(f"[{community} - {section}]\n{doc['text']}\n")

    return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """Conservative token estimate; Groq exposes no tokenizer for this model."""
    return max(1, len(text) // 4)


def _budgeted_max_tokens(*prompts: str) -> int:
    """Fit the answer ceiling under the free tier's prompt + completion limit.

    A 4k max_tokens ceiling used to turn a 6k-token context into a 10k request
    and a deterministic 413. The normal ceiling is LLM_MAX_TOKENS; this only
    lowers it when the context itself grows.
    """
    used = sum(_estimate_tokens(p) for p in prompts)
    return min(LLM_MAX_TOKENS, max(MIN_ANSWER_TOKENS, MAX_REQUEST_TOKENS - used))


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
            if cs["composite_score"] is None:
                citations.append(f"{cs['community']}: insufficient rent data, no score")
            else:
                citations.append(
                    f"{cs['community']}: Score {cs['composite_score']:.0f}/100, "
                    f"Gross Yield {cs['avg_roi_pct']:.2f}%, "
                    f"Recommendation {cs['recommendation']}"
                )
    if structured["transactions"]:
        for tx in structured["transactions"][:5]:
            citations.append(
                f"{tx['transaction_id']}: {tx['community']}, "
                f"{tx['handover_status']}, AED {tx['price_aed']:,.0f}"
            )

    system_prompt = """You are a Dubai real estate investment advisor. Answer investor questions using ONLY the provided data.

## YOUR ROLE
- Provide institutional-grade investment analysis for Dubai real estate
- Be concise, direct, and data-driven
- Speak like a trusted financial advisor — confident but not salesy

## RESPONSE RULES
1. NEVER calculate financial metrics yourself. Use only pre-computed values from the data.
2. Always cite specific data points (transaction IDs, community names, scores).
3. Distinguish GROSS yield from NET yield. Net yield here deducts management and vacancy only; it is BEFORE service charges, which DLD does not publish. Say so when you quote it.
4. When data is insufficient, say so clearly. A community marked INSUFFICIENT DATA has no yield or score: never estimate one for it.
5. Flag supply pipeline risks when relevant (off-plan sales still to be handed over).
6. The data is Dubai Land Department open data: registered apartment sales Jan-Sep 2026 and Ejari rent contracts from 1-22 October 2026. Mention the source when giving numbers.

## FORMATTING — STRICT
You MUST use clean markdown formatting. Follow these rules exactly:

### Structure
- Start with a 1-line direct answer (bold the key finding)
- Follow with a short explanation (2-3 sentences max)
- Use a table if comparing 2+ communities
- End with a clear action: **INVEST**, **HOLD**, or **AVOID** - or **INSUFFICIENT DATA** when the community has no score

### Tables
When showing multiple communities, ALWAYS use a proper markdown table:
| Community | Score | Gross Yield | Signal |
|-----------|-------|-------------|--------|
| JVC | 74 | 7.55% | INVEST |

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
Transaction data covers 2024; the market reports are dated Q1 2024. Always remind users to verify with DLD for current conditions."""

    user_prompt = f"""Question: {query}

=== DATA ===
{context}

=== REFERENCE DATA ===
{chr(10).join(citations)}

Answer using ONLY the data above. Use clean markdown formatting — proper tables, bullet points, bold for key metrics. Never use pipe-delimited text outside of tables. Never write [CITATIONS]."""

    max_tokens = _budgeted_max_tokens(system_prompt, user_prompt)
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
                max_tokens=max_tokens,
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


def dataset_counts() -> Dict[str, int]:
    """Row and community counts, so UI copy never hardcodes the dataset size."""
    transactions, communities = _db().execute(
        "SELECT COUNT(*), COUNT(DISTINCT community) FROM transactions"
    ).fetchone()
    return {"transactions": int(transactions), "communities": int(communities)}


def known_communities() -> List[str]:
    """Community values exactly as stored in DuckDB."""
    return [
        r[0]
        for r in _db().execute(
            "SELECT DISTINCT community FROM transactions ORDER BY 1"
        ).fetchall()
    ]


def rag_query(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    auto_filters: bool = True,
) -> Dict[str, Any]:
    """Full RAG pipeline: structured + semantic search + generation.

    `filters` may be passed explicitly. When it is omitted, filters are derived
    deterministically from the query text - see src/filters.py for the rules and
    for what is deliberately left unfiltered. Set auto_filters=False to bypass.
    """
    extracted = {"filters": {}, "skipped": []}
    if filters is None and auto_filters:
        extracted = extract_filters(query, known_communities())
        filters = extracted["filters"] or None

    structured = structured_search(query, filters=filters)
    structured["applied_filters"] = filters or {}
    structured["skipped_filters"] = extracted["skipped"]

    community = (filters or {}).get("community")
    semantic = semantic_search(query, n_results=3, community=community)
    if community and not has_report(community):
        structured["skipped_filters"] = list(structured["skipped_filters"]) + [
            f"no market report exists for {community}; the notes below cover "
            "other communities and must not be attributed to it"
        ]
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
        _db().execute("SELECT 1")
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
