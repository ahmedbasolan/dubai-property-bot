"""Data-only answers: what the API says when no LLM is available.

The public demo has no server key, so these answers are what most visitors
read. They used to be one table of the top communities by score whatever was
asked: "which community has the highest yield?" named the top *score*, a
villa question got an INVEST signal for apartments, and a price question got
no price.

Questions here are worded differently from eval/eval_set.json on purpose, so
passing them says the answer follows the question, not the eval's phrasing.
Expected values are read from the same DuckDB views the app serves.
"""

import sys
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "eval"))

from scoring import aed_amounts, check_label, check_number, percents, refuses, segments  # noqa: E402

DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="database missing - run `make setup` first"
)


@pytest.fixture(scope="module")
def scores():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    cols = [d[0] for d in conn.execute("SELECT * FROM v_investment_scores LIMIT 0").description]
    rows = conn.execute("SELECT * FROM v_investment_scores").fetchall()
    return {r[0]: dict(zip(cols, r)) for r in rows}


@pytest.fixture(scope="module")
def conn():
    return duckdb.connect(str(DB_PATH), read_only=True)


def ask(question: str) -> str:
    from data_answer import data_only_answer

    return data_only_answer(question, "No LLM is available.")[0]


def first_named(text: str, candidates) -> str:
    """The candidate community that appears earliest in the text."""
    lowered = text.lower()
    found = {c: lowered.find(c.split(" (")[0].lower()) for c in candidates}
    return min((c for c, i in found.items() if i >= 0), key=found.get)


def pct(community, value, tol=0.1, **kw):
    return {"community": community, "value": float(value), "kind": "pct", "tol": tol, **kw}


class TestAnswersTheMetricAsked:
    def test_price_per_square_foot(self, scores):
        c = "Business Bay"
        text = ask("What do flats in Business Bay sell for per sq ft?")
        n = {"community": c, "value": float(scores[c]["avg_price_per_sqft"]),
             "kind": "aed", "tol": 0.015, "rel": True}
        assert check_number(text, n, single=True), text

    def test_median_price_for_a_bedroom_count(self, conn):
        c = "Dubai Marina"
        median = conn.execute(
            """SELECT median(price_aed) FROM transactions
               WHERE community = ? AND handover_status = 'Ready' AND bedrooms = 2""", [c],
        ).fetchone()[0]
        text = ask("Typical price of a 2 bedroom flat in Dubai Marina?")
        n = {"community": c, "value": float(median), "kind": "aed", "tol": 0.015, "rel": True}
        assert check_number(text, n, single=True), text

    def test_price_momentum(self, scores):
        c = "Arjan"
        text = ask("Are apartment prices rising or falling in Arjan?")
        assert check_number(text, pct(c, scores[c]["price_momentum_pct"], tol=0.2, abs=True),
                            single=True), text

    def test_supply_risk(self, scores):
        c = "JVT (Jumeirah Village Triangle)"
        text = ask("Is there an oversupply risk in JVT?")
        assert check_label(text, {"community": c, "value": scores[c]["supply_risk"]}, single=True), text


class TestRankings:
    def test_highest_yield_names_the_top_yield_not_the_top_score(self, scores):
        with_yield = {c: s for c, s in scores.items() if s["avg_roi_pct"] is not None}
        best = max(with_yield, key=lambda c: with_yield[c]["avg_roi_pct"])
        text = ask("Where do landlords get the best rental yield?")
        assert first_named(text, scores) == best, text

    def test_lowest_yield(self, scores):
        with_yield = {c: s for c, s in scores.items() if s["avg_roi_pct"] is not None}
        worst = min(with_yield, key=lambda c: with_yield[c]["avg_roi_pct"])
        text = ask("Which area has the weakest rental yield?")
        assert first_named(text, scores) == worst, text

    def test_top_n_by_score_lists_n_in_order(self, scores):
        scored = sorted((c for c, s in scores.items() if s["composite_score"] is not None),
                        key=lambda c: (-scores[c]["composite_score"], c))
        text = ask("Give me the top 4 communities to invest in.")
        rows = [s for s in segments(text) if s.startswith("|") and any(
            c.split(" (")[0] in s for c in scores)]
        named = [first_named(r, scores) for r in rows]
        assert named[:4] == scored[:4], text
        assert len(named) == 4, text

    def test_cheapest_per_square_foot(self, scores):
        cheapest = min(scores, key=lambda c: scores[c]["avg_price_per_sqft"])
        text = ask("Where is the lowest price per square foot?")
        # International City also tops the score table, so naming it first is
        # not enough on its own: the answer has to give the price it was asked.
        assert first_named(text, scores) == cheapest, text
        n = {"community": cheapest, "value": float(scores[cheapest]["avg_price_per_sqft"]),
             "kind": "aed", "tol": 0.015, "rel": True}
        assert check_number(text, n, single=False), text


    def test_ranking_table_has_no_repeated_column(self):
        text = ask("Which communities score highest?")
        header = next(s for s in segments(text) if s.startswith("| Rank"))
        cells = [c.strip().lower() for c in header.strip("|").split("|")]
        assert sum("score" in c for c in cells) == 1, header


class TestBudgetQuestions:
    def test_superlative_with_a_budget_keeps_the_budget(self, conn):
        """'Best area for a 1 bed under 900k' is a budget question with a
        superlative in it; ranking all communities would drop the budget."""
        text = ask("Best area for a 1 bed under AED 900k?")
        assert "Matching sales" in text, text
        biggest = conn.execute(
            """SELECT max(price_aed) FROM transactions
               WHERE handover_status = 'Ready' AND bedrooms = 1 AND price_aed <= 900000"""
        ).fetchone()[0]
        assert all(v <= biggest for v in aed_amounts(text) if v > 10_000), text


class TestDeclinesWhatTheDataDoesNotCover:
    @pytest.mark.parametrize("question", [
        "What yield would a villa in Arabian Ranches give me?",
        "Which developer delivers projects on time?",
        "How much are service charges in Business Bay?",
        "What was the average price in Dubai Marina in 2023?",
        "What's the vacancy rate in JLT?",
    ])
    def test_declines(self, question):
        assert refuses(ask(question)), question

    def test_villa_question_gets_no_investment_signal(self):
        text = ask("What yield would a villa in Arabian Ranches give me?")
        assert not any(w in text for w in ("INVEST", "HOLD", "AVOID")), text

    def test_community_without_rent_data_states_no_yield(self):
        c = "The Greens"
        text = ask("Is The Greens good for rental income?")
        assert refuses(text, c), text
        assert not percents(" ".join(s for s in segments(text) if "Greens" in s and "yield" in s.lower())), text


class TestComparisons:
    def test_comparison_states_both_yields(self, scores):
        a, b = "Town Square", "Dubai South"
        text = ask("Town Square versus Dubai South for yield?")
        assert check_number(text, pct(a, scores[a]["avg_roi_pct"]), single=False), text
        assert check_number(text, pct(b, scores[b]["avg_roi_pct"]), single=False), text


def test_every_answer_cites_the_land_department():
    assert "Dubai Land Department" in ask("Is Meydan worth buying in?")


def test_answers_do_not_need_the_vector_store(monkeypatch):
    """The data-only path must not depend on embeddings: it is the fallback for
    when things are failing, and the embedding model is the slowest part."""
    import rag

    def boom(*a, **k):
        raise AssertionError("semantic search called")

    monkeypatch.setattr(rag, "semantic_search", boom)
    assert aed_amounts(ask("How much does a studio cost in JVC?"))
