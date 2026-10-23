"""Tests for the eval scorer (eval/scoring.py).

Every eval number is read off these functions, so a scorer bug silently
corrupts the measurement. The cases below are the ways an answer can look
right while being wrong (a number next to the wrong community, a yield stated
for a community with no data) and the ways a right answer can be misread
(table rows, "fell 9.6%", AED in millions).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from scoring import (  # noqa: E402
    aed_amounts,
    filters_match,
    invented_communities,
    mentions,
    percents,
    score_answer,
    score_text,
    segments,
)

JVC = "JVC (Jumeirah Village Circle)"


def yield_item(*communities, values):
    return {"id": "t", "type": "yield", "question": "q", "expect": {
        "communities": list(communities),
        "numbers": [{"community": c, "value": v, "kind": "pct", "tol": 0.1}
                    for c, v in zip(communities, values)],
    }}


class TestExtraction:
    def test_segments_keep_decimals_and_table_rows_intact(self):
        text = "JVC yields 7.39% gross. Marina yields 5.81%.\n| JVC | 7.39% | HOLD |"
        assert segments(text) == ["JVC yields 7.39% gross.", "Marina yields 5.81%.", "| JVC | 7.39% | HOLD |"]

    @pytest.mark.parametrize("text,expected", [
        ("AED 950,000", [950_000]),
        ("AED 1.5M", [1_500_000]),
        ("AED 0.95 million", [950_000]),
        ("AED 610K", [610_000]),
        ("about AED 1,275/sqft", [1_275]),
    ])
    def test_aed_formats(self, text, expected):
        assert aed_amounts(text) == expected

    def test_percent_signs_and_dashes(self):
        assert percents("fell −9.6% while JVT moved -1.3% and +2%") == [-9.6, -1.3, 2.0]

    def test_no_break_spaces_and_hyphens_are_normalised(self):
        """gpt-oss writes 'Palm\\u202fJumeirah'; a real answer failed on it."""
        assert mentions("Palm Jumeirah yields 4.64%", "Palm Jumeirah")
        assert mentions("The Greens", "The Greens")
        item = {"id": "t", "type": "yield_unavailable", "question": "q",
                "expect": {"refuse": True, "refuse_for": ["The Greens"]}}
        text = "You cannot derive a yield for The Greens: the data is insufficient.\nThe Greens has 289 sales."
        assert score_text(item, text)["refusal_ok"]

    def test_aliases_count_as_mentions(self):
        assert mentions("Yields in jvc are strong", JVC)
        assert mentions("Jumeirah Village Circle", JVC)
        assert not mentions("JVT is different", JVC)


class TestNumbersAreAttributed:
    def test_number_must_sit_with_its_own_community(self):
        """Two communities: JVC's figure next to Marina doesn't count for JVC."""
        item = yield_item(JVC, "Dubai Marina", values=[7.39, 5.81])
        wrong = "JVC yields 5.81%. Dubai Marina yields 7.39%."
        right = "JVC yields 7.39%. Dubai Marina yields 5.81%."
        assert not score_text(item, wrong)["pass"]
        assert score_text(item, right)["pass"]

    def test_table_rows_attribute_by_line(self):
        item = yield_item(JVC, "Dubai Marina", values=[7.39, 5.81])
        table = "| Community | Gross |\n|---|---|\n| JVC | 7.4% |\n| Dubai Marina | 5.8% |"
        assert score_text(item, table)["pass"]

    def test_rounding_within_tolerance(self):
        item = yield_item(JVC, values=[7.39])
        assert score_text(item, "JVC's gross yield is about 7.4%.")["pass"]
        assert not score_text(item, "JVC's gross yield is about 7.6%.")["pass"]

    def test_missing_community_name_fails(self):
        item = yield_item(JVC, "Dubai Marina", values=[7.39, 5.81])
        assert not score_text(item, "JVC yields 7.39%.")["pass"]

    def test_a_single_sale_does_not_stand_in_for_a_median(self):
        """A sample sale at AED 970,000 sat within tolerance of the 997,700 median."""
        item = {"id": "t", "type": "price", "question": "q", "expect": {
            "communities": [JVC],
            "numbers": [{"community": JVC, "value": 997_700, "kind": "aed", "tol": 0.03, "rel": True}]}}
        sale = "[11-21083-2026] 2026-07-08, JVC (Jumeirah Village Circle), 1BR Apartment, Ready, AED 970,000"
        assert not score_text(item, sale, in_context=True)["pass"]
        assert score_text(item, "[JVC] Median ready price: 1BR AED 997,700", in_context=True)["pass"]

    def test_context_figures_must_name_their_community(self):
        """Palm's 4.64% was 'found' as a Dubai Marina row's 4.67%."""
        item = yield_item("Palm Jumeirah", values=[4.64])
        ctx = "[Dubai Marina] Gross yield: 4.67%\n[Palm Jumeirah] Median price/sqft: AED 2,660"
        assert not score_text(item, ctx, in_context=True)["pass"]

    def test_momentum_accepts_unsigned_fall(self):
        item = {"id": "t", "type": "momentum", "question": "q", "expect": {
            "communities": [JVC],
            "numbers": [{"community": JVC, "value": -9.3, "kind": "pct", "tol": 0.2, "abs": True}]}}
        assert score_text(item, "Prices in JVC fell 9.3% across the same projects.")["pass"]


class TestRefusals:
    unavailable = {"id": "t", "type": "yield_unavailable", "question": "q",
                   "expect": {"refuse": True, "refuse_for": ["The Greens"]}}

    def test_declining_passes(self):
        assert score_text(self.unavailable, "There isn't enough rent data for The Greens to compute a yield.")["pass"]

    def test_stating_a_yield_fails_even_with_a_hedge(self):
        text = "Rent data is insufficient overall. The Greens yield is about 6.2% though."
        result = score_text(self.unavailable, text)
        assert result["leaked_yields"] == [6.2]
        assert not result["pass"]

    def test_out_of_scope_refusal_is_only_required_in_context_when_flagged(self):
        item = {"id": "t", "type": "out_of_scope", "question": "q",
                "expect": {"refuse": True, "refuse_in_context": False}}
        assert score_text(item, "JVC net yield 6.4%", in_context=True)["pass"]
        assert not score_text(item, "JVC developers are great")["pass"]


class TestAnswerLevelChecks:
    def test_invented_community_fails_the_answer(self):
        item = yield_item(JVC, values=[7.39])
        result = score_answer(item, "JVC yields 7.39%, better than Arabian Ranches.", known=[JVC])
        assert result["invented_communities"] == ["Arabian Ranches"]
        assert not result["pass"]

    def test_community_raised_by_the_question_is_allowed(self):
        assert invented_communities("Arabian Ranches is villas only.", known=[], allowed=["Arabian Ranches"]) == []

    def test_source_citation_is_tracked_not_required(self):
        item = yield_item(JVC, values=[7.39])
        result = score_answer(item, "JVC yields 7.39%.", known=[JVC])
        assert result["pass"] and not result["cites_source"]


class TestFilters:
    def test_comparison_lists_compare_as_sets(self):
        assert filters_match({"communities": ["A", "B"]}, {"communities": ["B", "A"]})

    def test_missing_or_wrong_filter_fails(self):
        assert not filters_match({"bedrooms": 1}, {})
        assert not filters_match({"max_price": 1_000_000}, {"max_price": 1_500_000})


class TestGeneratedSet:
    """The committed eval set must be well-formed and match the database."""

    path = Path(__file__).parent / "eval_set.json"

    def test_shape(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        assert data["version"] == 2
        ids = [i["id"] for i in data["eval_set"]]
        assert len(ids) == len(set(ids)) >= 90
        for i in data["eval_set"]:
            assert i["question"] and i["type"] and "expect" in i

    def test_ground_truth_matches_the_database(self):
        import duckdb

        db = Path(__file__).parent.parent / "data" / "dubai_properties.duckdb"
        if not db.exists():
            pytest.skip("database missing - run `make setup`")
        conn = duckdb.connect(str(db), read_only=True)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for item in data["eval_set"]:
            if item["type"] != "yield_lookup":
                continue
            n = item["expect"]["numbers"][0]
            actual = conn.execute(
                "SELECT avg_roi_pct FROM v_investment_scores WHERE community = ?", [n["community"]]
            ).fetchone()[0]
            assert actual == pytest.approx(n["value"]), f"{item['id']}: rebuild with eval/build_eval_set.py"
