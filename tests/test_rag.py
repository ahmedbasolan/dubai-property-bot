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


def test_bedroom_question_gets_the_exact_bedroom_median():
    """The eval's weakest type: asked for a 2-bedroom price, the model was given
    only the community's overall median and reported that as the answer. The
    bedroom median lived in a report section that semantic search rarely
    surfaced, so it goes into the context directly, like the price trend."""
    import duckdb

    from rag import build_context, structured_search

    community = "JLT (Jumeirah Lake Towers)"
    median, count = duckdb.connect(str(DB_PATH), read_only=True).execute(
        """SELECT median(price_aed), COUNT(*) FROM transactions
           WHERE community = ? AND handover_status = 'Ready' AND bedrooms = 2""",
        [community],
    ).fetchone()

    result = structured_search("2 bed price", filters={"community": community, "bedrooms": 2})
    context = build_context(result, [])

    line = next(l for l in context.splitlines() if "2-bedroom" in l and "median" in l.lower())
    assert f"AED {median:,.0f}" in line
    assert f"{count:,}" in line


def test_no_bedroom_block_without_a_bedroom_filter():
    from rag import build_context, structured_search

    context = build_context(structured_search("prices", filters={"community": "Dubai Marina"}), [])
    assert "BEDROOM MEDIAN" not in context


def _scores():
    import duckdb

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    cols = [d[0] for d in conn.execute("SELECT * FROM v_investment_scores LIMIT 0").description]
    return [dict(zip(cols, r)) for r in conn.execute("SELECT * FROM v_investment_scores").fetchall()]


def _line_for(context: str, community: str) -> str:
    return next(l for l in context.splitlines() if l.startswith(f"[{community}]"))


def test_unscoped_context_covers_every_community():
    """'Lowest yield' and 'most sales' were unanswerable: an unscoped question
    showed only the top 8 communities by score, and Palm Jumeirah (lowest
    yield) and JVC (most sales) rank below that."""
    from rag import build_context, structured_search

    scores = _scores()
    lowest = min((s for s in scores if s["avg_roi_pct"] is not None), key=lambda s: s["avg_roi_pct"])
    busiest = max(scores, key=lambda s: s["transaction_count"])
    context = build_context(structured_search("which community"), [])

    assert f"{lowest['avg_roi_pct']:.2f}%" in _line_for(context, lowest["community"])
    assert f"{busiest['transaction_count']:,}" in _line_for(context, busiest["community"])


def test_unscoped_context_stays_inside_the_request_budget():
    from rag import MAX_REQUEST_TOKENS, MIN_ANSWER_TOKENS, _estimate_tokens, retrieve

    context = retrieve("Which community has the lowest rental yield?")["context"]
    assert _estimate_tokens(context) + MIN_ANSWER_TOKENS <= MAX_REQUEST_TOKENS


def test_no_per_sale_yield_for_a_community_without_one():
    """JBR has no community yield (too few matched rents), but its sample sales
    carried project-level 'estimated yields', inviting the model to quote one."""
    sys.path.insert(0, str(PROJECT_ROOT / "eval"))
    from scoring import states_yield_for

    from rag import build_context, structured_search

    community = "JBR (Jumeirah Beach Residence)"
    context = build_context(structured_search("yield", filters={"community": community}), [])
    assert states_yield_for(context, community) == []


@pytest.mark.parametrize("question", [
    "Which developer has the best delivery track record?",
    "What are the service charges per sqft in JVC?",
    "What's the occupancy rate in Dubai Marina?",
    "What were Dubai Marina apartment prices in 2024?",
])
def test_context_says_when_a_topic_is_not_in_the_data(question):
    """Asked about developers, the model presented the off-plan supply ratio as
    a delivery track record and recommended INVEST. Nothing in the context said
    developer data doesn't exist, so it is now stated, as it is for villas."""
    from rag import retrieve

    notes = [l for l in retrieve(question)["context"].splitlines() if l.strip().startswith("note:")]
    assert any("not covered" in n for n in notes), notes
