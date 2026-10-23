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


def test_list_reports_the_whole_dataset(client, conn):
    """The list endpoint used to return the LLM's 40-row context sample. With
    ~48k DLD sales it pages, but `total` must still be the full count."""
    expected = conn.execute("SELECT COUNT(*) FROM v_net_yield").fetchone()[0]
    body = client.get("/api/transactions", params={"limit": 500}).json()

    assert body["total"] == expected
    assert len(body["transactions"]) == min(500, expected)


def test_total_is_filtered_count(client, conn):
    expected = conn.execute(
        "SELECT COUNT(*) FROM v_net_yield WHERE community ILIKE ?", ["Dubai Marina"]
    ).fetchone()[0]
    body = client.get(
        "/api/transactions", params={"community": "dubai marina", "limit": 500}
    ).json()

    assert body["total"] == expected
    assert len(body["transactions"]) == min(500, expected)
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
    """Supply and liquidity always grade. Yield and momentum grade when the data
    supports them and are null otherwise, never a made-up letter."""
    scores = client.get("/api/scores").json()["scores"]

    assert scores
    for score in scores:
        for field in ("supply_risk_score", "liquidity_score"):
            assert score[field] in {"A", "B", "C", "D", "F"}, (field, score[field])
        for field in ("yield_score", "momentum_score"):
            assert score[field] in {"A", "B", "C", "D", "F", None}, (field, score[field])
        assert (score["yield_score"] is None) == (score["avg_roi_pct"] is None)
        assert (score["momentum_score"] is None) == (score["price_momentum_pct"] is None)


def test_recommendation_agrees_with_composite_score(client):
    """Score and signal must come from one rule set, never two.

    Before the fix JVC (76) was INVEST and International City (76) was HOLD,
    because the recommendation counted threshold passes while the score summed
    unrelated weights.
    """
    for score in client.get("/api/scores").json()["scores"]:
        value = score["composite_score"]
        expected = (
            "INSUFFICIENT DATA" if value is None
            else "INVEST" if value >= 70 else "HOLD" if value >= 50 else "AVOID"
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

    assert body["default_source"] == "dld"
    assert body["data_source"] in {"dld", "bayut"}


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


def test_every_community_has_supply_and_a_score_row(conn):
    missing_supply = conn.execute(
        """SELECT DISTINCT t.community FROM transactions t
           LEFT JOIN supply_pipeline sp ON t.community = sp.community_name
           WHERE sp.community_name IS NULL"""
    ).fetchall()
    missing_score = conn.execute(
        """SELECT DISTINCT t.community FROM transactions t
           LEFT JOIN v_investment_scores s USING (community)
           WHERE s.community IS NULL"""
    ).fetchall()

    assert missing_supply == []
    assert missing_score == []


def test_unknown_trend_community_returns_404(client):
    response = client.get("/api/trends", params={"community": "Atlantis"})

    assert response.status_code == 404
    assert "Atlantis" in response.json()["detail"]


def test_trends_report_their_source_and_basis(client, conn):
    """/trends must say where the series comes from, and its volume must be the
    real count of registered ready sales."""
    body = client.get("/api/trends").json()

    assert body["source"] == "dld:price_history"
    assert "dld" in body["basis"].lower()
    assert body["trends"]

    marina = body["trends"]["Dubai Marina"]
    expected = conn.execute(
        """SELECT COUNT(*) FROM transactions
           WHERE community = 'Dubai Marina' AND handover_status = 'Ready'"""
    ).fetchone()[0]
    assert sum(p["market_volume"] for p in marina) == expected


def test_concurrent_requests_do_not_share_query_results(client):
    """One DuckDB connection shared across FastAPI's worker threads mixed up
    result sets: the dashboard's two parallel fetches crashed with rows from
    the other query. Each query now runs on its own cursor."""
    from concurrent.futures import ThreadPoolExecutor

    paths = ["/api/communities", "/api/transactions?limit=8", "/api/scores", "/api/map"] * 4
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda p: client.get(p).status_code, paths))

    assert statuses == [200] * len(paths)


def test_developers_are_reported_unavailable_not_invented(client):
    """DLD sales carry no developer; the endpoint must say so, not score guesses."""
    body = client.get("/api/developers").json()

    assert body["developers"] == []
    assert "not available" in body["basis"].lower()

