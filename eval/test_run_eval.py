"""Tests for the evaluation harness itself.

The harness is what the CV numbers are read off, so a bug here silently
invalidate every measurement. These cover the two defects that produced
false "number accuracy" failures.
"""

import re
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from run_eval import check_community_attribution, check_number_accuracy  # noqa: E402

DB_PATH = Path(__file__).parent.parent / "data" / "dubai_properties.duckdb"


@pytest.fixture(scope="module")
def conn():
    if not DB_PATH.exists():
        pytest.skip(f"{DB_PATH} missing - run `make setup` first")
    return duckdb.connect(str(DB_PATH), read_only=True)


class TestNumberAccuracy:
    def test_supply_pipeline_not_mistaken_for_roi(self, conn):
        """A pipeline percentage after the word "yield" in an earlier sentence
        used to be reported as an out-of-range ROI claim."""
        answer = (
            "JVC yields well for investors. "
            "Supply risk is high (15.9% pipeline) but the community is still rated INVEST"
        )
        result = check_number_accuracy(answer, conn)
        assert result["valid"], result["issues"]

    def test_net_yield_uses_the_net_yield_range(self, conn):
        """Net yield runs 2.08-8.25; ROI runs 4.9-10.3. Checking a net-yield
        figure against the ROI range flagged a correct answer as wrong."""
        answer = "A 1-BR in Downtown yields roughly 2.78% net annual income (about 5.9% gross ROI)."
        result = check_number_accuracy(answer, conn)
        assert result["valid"], result["issues"]

    @pytest.mark.parametrize(
        "answer",
        ["ROI 4.9%", "ROI 10.3%", "Net Yield: 2.08% (TRX-001)", "Net yield 8.25%"],
    )
    def test_boundary_values_are_in_range(self, conn, answer):
        result = check_number_accuracy(answer, conn)
        assert result["valid"], result["issues"]

    @pytest.mark.parametrize(
        "answer,metric",
        [("ROI 42.0%", "roi"), ("Net yield 55.0%", "net_yield")],
    )
    def test_genuinely_out_of_range_is_caught(self, conn, answer, metric):
        result = check_number_accuracy(answer, conn)
        assert not result["valid"], "a real violation must be reported"
        assert any(metric in i for i in result["issues"]), result["issues"]

    def test_table_cells_are_not_joined_to_a_label(self, conn):
        """Table rows put a pipeline % next to a yield %; the checker must not
        read across the pipe."""
        answer = "| Community | Net Yield | Pipeline | Rec |\n| JVC | 7.07% | 15.9% | INVEST |"
        result = check_number_accuracy(answer, conn)
        assert result["valid"], result["issues"]

    def test_match_does_not_span_sentences(self, conn):
        long_gap = "yield analysis. " + "x" * 40 + " 99.9%"
        result = check_number_accuracy(long_gap, conn)
        assert result["valid"], result["issues"]


class TestCommunityAttribution:
    def test_parenthetical_alias_is_accepted(self):
        valid = ["JVC (Jumeirah Village Circle)", "Dubai Marina"]
        result = check_community_attribution("JVC is attractive", valid)
        assert result["valid_communities"], result["invalid_communities"]

    def test_known_but_absent_community_is_rejected(self):
        """A community-shaped name that is not in the DB must be flagged."""
        result = check_community_attribution(
            "Palm Jumeirah offers the best yields", ["Dubai Marina", "Business Bay"]
        )
        assert not result["valid_communities"]
        assert any("palm jumeirah" in c.lower() for c in result["invalid_communities"])

    def test_unrecognised_prose_is_not_treated_as_a_community(self):
        """extract_communities only scans a known name list, so free text is
        ignored rather than flagged. This is why the 100% attribution figure
        means 'no known community was invented', not 'every noun was checked'."""
        result = check_community_attribution(
            "Downtown Sands is a great place", ["Dubai Marina", "Business Bay"]
        )
        assert result["communities_mentioned"] == []


class TestCommunityListMatchesDatabase:
    def test_hardcoded_list_covers_every_community_in_the_db(self, conn):
        """The attribution check is only meaningful if the hardcoded name list
        has not drifted from the database."""
        from run_eval import extract_communities

        src = (Path(__file__).parent / "run_eval.py").read_text(encoding="utf-8")
        listed = set(re.findall(r'"([^"]+)"', re.search(r"known_communities\s*=\s*\[(.*?)\]", src, re.S).group(1)))
        db = {r[0] for r in conn.execute("SELECT DISTINCT community FROM transactions").fetchall()}

        norm = lambda s: re.sub(r"\s*\(.*\)", "", s).strip().lower()
        missing = {c for c in db if norm(c) not in {norm(x) for x in listed}}
        assert not missing, f"communities in DB missing from known_communities: {missing}"
