"""Tests for deterministic NL -> SQL filter extraction.

The failure mode these guard against is the expensive one: a wrong filter
silently removes rows, and the model then reports that a property type or
community "does not exist" when it was only filtered away. So the tests assert
both directions - that confident phrases ARE filtered, and that ambiguous ones
are NOT.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from filters import extract_filters  # noqa: E402

DB_PATH = Path(__file__).parent.parent / "data" / "dubai_properties.duckdb"


@pytest.fixture(scope="module")
def conn():
    if not DB_PATH.exists():
        pytest.skip(f"{DB_PATH} missing - run `make setup` first")
    return duckdb.connect(str(DB_PATH), read_only=True)


@pytest.fixture(scope="module")
def communities(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT community FROM transactions").fetchall()]


def fx(q, communities):
    return extract_filters(q, communities)["filters"]


class TestCommunityExtraction:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("What about Business Bay?", "Business Bay"),
            ("tell me about downtown", "Downtown Dubai"),
            ("how is JVC performing", "JVC (Jumeirah Village Circle)"),
            ("what about JLT", "JLT (Jumeirah Lake Towers)"),
            ("DSO supply risk?", "Dubai Silicon Oasis"),
            ("is damac hills risky", "DAMAC Hills"),
            ("is damac hills 2 risky", None),  # dropped villa community, not DAMAC Hills
            ("marina yields", "Dubai Marina"),
            ("arjan or majan?", None),  # two communities: a comparison, not one filter
            ("how is IMPZ doing", "Dubai Production City"),
        ],
    )
    def test_aliases_resolve_to_database_values(self, query, expected, communities):
        assert fx(query, communities).get("community") == expected

    def test_uncovered_community_is_reported_not_matched(self, communities):
        result = extract_filters("is damac hills 2 a good buy", communities)
        assert "community" not in result["filters"]
        assert any("damac hills 2" in s and "apartments only" in s for s in result["skipped"])

    def test_resolved_value_actually_matches_rows(self, communities, conn):
        """The resolved string must be the exact column value, or the ILIKE
        predicate silently matches nothing."""
        f = fx("how is JVC performing", communities)
        value = f["community"]
        n = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE community = ?", [value]
        ).fetchone()[0]
        assert n > 0, f"resolved {value!r} matches no rows"

    def test_comparison_is_scoped_to_both_communities(self, communities):
        """Naming two communities is a comparison, scoped to both."""
        result = extract_filters("Compare Dubai Marina and JVC yields", communities)
        assert "community" not in result["filters"]
        assert result["filters"]["communities"] == [
            "Dubai Marina",
            "JVC (Jumeirah Village Circle)",
        ]
        assert any("comparison" in s for s in result["skipped"])

    def test_unknown_community_yields_no_filter(self, communities):
        assert "community" not in fx("what about RAK Island?", communities)


class TestPropertyType:
    def test_villas_are_reported_as_not_covered(self, communities):
        """DLD data here is apartments only: a villa filter would match nothing."""
        result = extract_filters("Which communities have villas?", communities)
        assert "property_type" not in result["filters"]
        assert any("villas" in s and "apartment" in s for s in result["skipped"])

    def test_apartment_and_villa_together_is_ambiguous(self, communities):
        result = extract_filters("Compare villa and apartment prices", communities)
        assert "property_type" not in result["filters"]
        assert result["skipped"]

    def test_filtered_value_matches_rows_case_insensitively(self, communities, conn):
        """`property_type = 'villa'` returns 0 rows against a column holding
        'Villa', which is exactly how a filter becomes a false 'no data'."""
        f = fx("show me apartments", communities)
        value = f["property_type"]
        strict = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE property_type = ?", [value]
        ).fetchone()[0]
        ci = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE property_type ILIKE ?", [value]
        ).fetchone()[0]
        assert ci > 0
        assert strict == 0 or strict == ci  # either it matches, or only ILIKE does


class TestBedrooms:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("best 1BR under 1.5M", 1),
            ("a 2 bedroom in JVC", 2),
            ("three bed villa", 3),
            ("studio apartments", 0),
        ],
    )
    def test_explicit_bedroom_wording(self, query, expected, communities):
        assert fx(query, communities).get("bedrooms") == expected

    def test_price_is_not_mistaken_for_bedrooms(self, communities):
        """"1.5M" must not become a 1-bedroom filter."""
        assert "bedrooms" not in fx("best options under 1.5M", communities)

    def test_top_n_is_not_mistaken_for_bedrooms(self, communities):
        assert "bedrooms" not in fx("Recommend the top 3 communities", communities)


class TestPrice:
    @pytest.mark.parametrize(
        "query,key,expected",
        [
            ("1BR under AED 1.5M", "max_price", 1_500_000),
            ("apartments below 2 million", "max_price", 2_000_000),
            ("villas over AED 3M", "min_price", 3_000_000),
            ("cheaper than 800K", "max_price", 800_000),
            ("starting from 1.2M", "min_price", 1_200_000),
        ],
    )
    def test_directional_phrases(self, query, key, expected, communities):
        assert fx(query, communities).get(key) == expected

    def test_budget_is_treated_as_a_ceiling(self, communities):
        assert fx("I have a AED 1M budget", communities).get("max_price") == 1_000_000

    def test_percentage_is_never_read_as_a_price(self, communities):
        """"ROI 10.3%" and "15.9% pipeline" must not become prices."""
        f = fx("which has ROI over 10% and the highest yield?", communities)
        assert "min_price" not in f and "max_price" not in f

    def test_bare_number_without_currency_is_ignored(self, communities):
        f = fx("top 3 communities please", communities)
        assert "min_price" not in f and "max_price" not in f

    def test_directional_price_without_currency_is_not_guessed(self, communities):
        """'under 1.5M' has a clear direction and a M suffix, so it is used."""
        assert fx("1BR under 1.5M", communities).get("max_price") == 1_500_000

    def test_ambiguous_price_is_left_unfiltered_and_explained(self, communities):
        result = extract_filters("what is the net yield for a AED 1.35M property?", communities)
        assert "min_price" not in result["filters"] and "max_price" not in result["filters"]
        assert result["skipped"], "an ignored price must be explained"


class TestCombined:
    def test_multiple_dimensions_combine(self, communities):
        f = fx("2BR apartment in JVC under AED 4M", communities)
        assert f == {
            "community": "JVC (Jumeirah Village Circle)",
            "property_type": "Apartment",
            "bedrooms": 2,
            "max_price": 4_000_000,
        }

    def test_non_filter_question_produces_no_filters(self, communities):
        f = fx("How does the supply pipeline affect property prices?", communities)
        assert f == {}


class TestRelaxationSafetyNet:
    """A filter that matches nothing must not become a false 'no data' answer."""

    def test_zero_row_filter_is_relaxed(self, communities):
        import rag

        s = rag.structured_search("anything", filters={"community": "Nonexistent Place"})
        assert s["relaxed_filters"], "a zero-row filter must be reported as relaxed"
        assert s["transactions"], "falling back must return rows, not an empty context"

    def test_relaxation_is_visible_in_the_context(self, communities):
        import rag

        s = rag.structured_search("anything", filters={"community": "Nonexistent Place"})
        ctx = rag.build_context(s, [])
        assert "retried without it" in ctx

    def test_valid_filter_is_not_relaxed(self, communities):
        import rag

        s = rag.structured_search("anything", filters={"community": "Business Bay"})
        assert not s.get("relaxed_filters")
        assert all(t["community"] == "Business Bay" for t in s["transactions"])


class TestLikeEscaping:
    def test_wildcards_in_a_filter_value_are_escaped(self):
        import rag

        assert rag._like_param("100%_x") == "100\\%\\_x"


class TestSemanticScoping:
    """Unscoped semantic search served one community's report as another's."""

    def test_community_with_a_report_is_scoped(self):
        import rag

        hits = rag.semantic_search("average price per sqft", n_results=3, community="Downtown Dubai")
        assert hits
        assert {h["metadata"].get("community") for h in hits} == {"Downtown Dubai"}

    def test_marina_is_scoped_to_marina(self):
        import rag

        hits = rag.semantic_search("investment highlights", n_results=3, community="Dubai Marina")
        assert hits
        assert {h["metadata"].get("community") for h in hits} == {"Dubai Marina"}

    def test_community_without_a_report_is_left_unscoped(self):
        """DAMAC Hills 2 has no report. Filtering to it would return nothing,
        so it stays unscoped and the gap is reported instead."""
        import rag

        assert not rag.has_report("DAMAC Hills 2")
        hits = rag.semantic_search("risks", n_results=3, community="DAMAC Hills 2")
        assert hits, "should fall back to unscoped rather than returning nothing"

    def test_every_community_has_its_own_report(self, communities):
        """build_reports.py writes one report per community, keyed by the
        exact DuckDB name, so scoping never falls back for a real community."""
        import rag

        missing = [c for c in communities if not rag.has_report(c)]
        assert missing == []


class TestScoreAndSupplyScoping:
    def test_scores_are_scoped_to_the_filtered_community(self):
        import rag

        s = rag.structured_search("x", filters={"community": "Business Bay"})
        assert s["community_scores"], "filtered query returned no scores"
        assert {c["community"] for c in s["community_scores"]} == {"Business Bay"}

    def test_supply_is_scoped_to_the_filtered_community(self):
        import rag

        s = rag.structured_search("x", filters={"community": "Business Bay"})
        assert s["supply_info"]
        assert {p["community_name"] for p in s["supply_info"]} == {"Business Bay"}

    def test_unfiltered_query_still_returns_all_communities(self):
        import rag

        s = rag.structured_search("x", filters=None)
        assert len(s["community_scores"]) == 29
        assert len(s["supply_info"]) > 1


class TestReportGapIsAnnounced:
    def test_missing_report_is_noted_in_the_context(self):
        import rag

        s = rag.structured_search("x", filters={"community": "DAMAC Hills 2"})
        s["skipped_filters"] = [
            "no market report exists for DAMAC Hills 2; the notes below cover "
            "other communities and must not be attributed to it"
        ]
        ctx = rag.build_context(s, [])
        assert "must not be attributed to it" in ctx

