"""RAG context contracts: scoped trends and the request-size guard.

The chat used to answer price-trend questions from the market-report chunks
while /api/trends read DuckDB, so the two could disagree. A 4k max_tokens
ceiling also turned a 6k-token prompt into a 10k request and a deterministic
413 from the Groq free tier.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="database missing - run `make setup` first"
)


def test_scoped_query_includes_the_duckdb_price_trend():
    from rag import build_context, structured_search

    result = structured_search("price trend", filters={"community": "Dubai Marina"})
    trend = result["price_trend"]

    assert trend["community"] == "Dubai Marina"
    assert trend["latest_price"] > 0
    assert trend["latest_quarter"] == "Q3 2026"

    context = build_context(result, [])
    assert "PRICE TREND (DLD ready sales)" in context
    assert "same projects" in context.lower()


def test_unscoped_query_has_no_trend_block():
    from rag import structured_search

    result = structured_search("best communities")

    # 24 series would be context bloat; trends are scoped to a community.
    assert not result.get("price_trend")


def test_comparison_context_contains_both_communities():
    from filters import extract_filters
    from rag import build_context, known_communities, structured_search

    query = "Compare the investment scores of Dubai Hills Estate and Business Bay."
    extracted = extract_filters(query, known_communities())
    filters = extracted["filters"]

    assert filters["communities"] == ["Business Bay", "Dubai Hills Estate"]

    result = structured_search(query, filters=filters)
    scores = {s["community"] for s in result["community_scores"]}
    assert scores == {"Business Bay", "Dubai Hills Estate"}

    context = build_context(result, [])
    assert "Dubai Hills Estate" in context
    assert "Business Bay" in context
    # The old top-8 truncation could drop both compared communities.
    assert "COMMUNITY INVESTMENT SCORES" in context


def test_answer_budget_fits_the_free_tier_request_limit():
    from config import LLM_MAX_TOKENS
    from rag import (
        MAX_REQUEST_TOKENS,
        MIN_ANSWER_TOKENS,
        _budgeted_max_tokens,
        _estimate_tokens,
    )

    assert _budgeted_max_tokens("short") == LLM_MAX_TOKENS

    # A worst-case context must still leave the minimum answer room inside the
    # 8k TPM request limit.
    context = "x" * (6_000 * 4)
    max_tokens = _budgeted_max_tokens(context)
    assert max_tokens >= MIN_ANSWER_TOKENS
    assert _estimate_tokens(context) + max_tokens <= MAX_REQUEST_TOKENS
