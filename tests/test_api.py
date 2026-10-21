"""API contract tests for the endpoints reviewed in REVIEW.md.

These cover the regressions the original suite could not see: the list endpoint
was reusing the LLM's 40-row context sample, errors were returned as HTTP 200,
and the composite score and recommendation were two unrelated rule sets.
"""

import sys
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="database missing - run `make setup` first"
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def conn():
    return duckdb.connect(str(DB_PATH), read_only=True)


def test_list_returns_whole_dataset(client, conn):
    """The list endpoint used to return the LLM's 40-row context sample."""
    expected = conn.execute("SELECT COUNT(*) FROM v_net_yield").fetchone()[0]
    body = client.get("/api/transactions", params={"limit": 500}).json()

    assert body["total"] == expected
    assert len(body["transactions"]) == expected


def test_total_is_filtered_count(client, conn):
    expected = conn.execute(
        "SELECT COUNT(*) FROM v_net_yield WHERE community ILIKE ?", ["Dubai Marina"]
    ).fetchone()[0]
    body = client.get(
        "/api/transactions", params={"community": "dubai marina", "limit": 500}
    ).json()

    assert body["total"] == expected
    assert {t["community"] for t in body["transactions"]} == {"Dubai Marina"}


def test_pagination_does_not_repeat_rows(client):
    first = client.get("/api/transactions", params={"limit": 5, "offset": 0}).json()
    second = client.get("/api/transactions", params={"limit": 5, "offset": 5}).json()

    ids_first = {t["transaction_id"] for t in first["transactions"]}
    ids_second = {t["transaction_id"] for t in second["transactions"]}

    assert len(ids_first) == 5
    assert ids_first.isdisjoint(ids_second)


def test_missing_transaction_returns_404(client):
    response = client.get("/api/transactions/TRX-DOES-NOT-EXIST")

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"


def test_scores_have_letter_grades(client):
    scores = client.get("/api/scores").json()["scores"]

    assert scores
    for score in scores:
        for field in (
            "price_score",
            "yield_score",
            "net_yield_score",
            "service_charge_score",
            "supply_risk_score",
            "occupancy_score",
            "developer_score",
        ):
            assert score[field] in {"A", "B", "C", "D", "F"}, (field, score[field])


def test_recommendation_agrees_with_composite_score(client):
    """Score and signal must come from one rule set, never two.

    Before the fix JVC (76) was INVEST and International City (76) was HOLD,
    because the recommendation counted threshold passes while the score summed
    unrelated weights.
    """
    for score in client.get("/api/scores").json()["scores"]:
        value = score["composite_score"]
        expected = (
            "INVEST" if value >= 70 else "HOLD" if value >= 50 else "AVOID"
        )
        assert score["recommendation"] == expected, (
            score["community"],
            value,
            score["recommendation"],
        )


def test_supply_risk_is_upper_case(client):
    """The UI compares against 'HIGH'/'MEDIUM'/'LOW'."""
    risks = {s["supply_risk"] for s in client.get("/api/scores").json()["scores"]}
    assert risks <= {"LOW", "MEDIUM", "HIGH"}


def test_health_distinguishes_live_and_default_source(client):
    body = client.get("/api/health").json()

    assert body["default_source"] == "mock"
    assert body["data_source"] in {"mock", "bayut"}


def test_chat_get_ignores_api_key(client, monkeypatch):
    """A key in a URL is logged; only POST /api/chat may accept one."""
    from api import main

    captured = {}

    def fake_chat_response(q, provider, api_key, model):
        captured["api_key"] = api_key
        return {"answer": "stub", "communities": [], "transaction_count": 0}

    monkeypatch.setattr(main, "_chat_response", fake_chat_response)

    response = client.get("/api/chat", params={"q": "test question", "api_key": "secret"})

    assert response.status_code == 200
    assert captured["api_key"] is None


def test_every_community_has_supply_and_metadata(conn):
    missing_supply = conn.execute(
        """SELECT DISTINCT t.community FROM transactions t
           LEFT JOIN supply_pipeline sp ON t.community = sp.community_name
           WHERE sp.community_name IS NULL"""
    ).fetchall()
    missing_meta = conn.execute(
        """SELECT DISTINCT t.community FROM transactions t
           LEFT JOIN communities c ON t.community = c.community_name
           WHERE c.community_name IS NULL"""
    ).fetchall()

    assert missing_supply == []
    assert missing_meta == []


def test_unknown_trend_community_returns_404(client):
    response = client.get("/api/trends", params={"community": "Atlantis"})

    assert response.status_code == 404
    assert "Atlantis" in response.json()["detail"]


def test_trends_report_their_source_and_basis(client):
    """/trends must say where the series comes from and what is modelled."""
    body = client.get("/api/trends").json()

    assert body["source"] == "duckdb:price_history"
    assert "modelled" in body["basis"].lower()
    assert body["trends"]


def test_developer_recommendation_matches_its_score(client):
    body = client.get("/api/developers").json()

    assert body["developers"]
    for developer in body["developers"]:
        value = developer["composite_score"]
        expected = "INVEST" if value >= 70 else "HOLD" if value >= 50 else "AVOID"
        assert developer["recommendation"] == expected, developer["name"]

