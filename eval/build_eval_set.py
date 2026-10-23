"""Build eval/eval_set.json from DuckDB.

Questions are written here; every expected value is read from the same views
the app serves, so the set is rebuilt (not hand-edited) whenever the data
changes: `python eval/build_eval_set.py`. A question whose ground truth the
data can't supply (e.g. a community losing its yield) fails the build loudly
rather than silently testing nothing.

Expectations per question (see scoring.py):
  filters    applied_filters that retrieval must produce
  numbers    values that must appear next to their community (with tolerance)
  labels     words that must appear next to their community (INVEST, HIGH...)
  communities  communities the answer must name
  refuse     the answer must decline (insufficient data / out of scope)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import duckdb  # noqa: E402

from config import DB_PATH  # noqa: E402

OUT = Path(__file__).parent / "eval_set.json"

JVC = "JVC (Jumeirah Village Circle)"
JLT = "JLT (Jumeirah Lake Towers)"
JVT = "JVT (Jumeirah Village Triangle)"
JBR = "JBR (Jumeirah Beach Residence)"
DSO = "Dubai Silicon Oasis"

YIELD_TOL = 0.1      # percentage points; answers round 7.39 to 7.4
MOMENTUM_TOL = 0.2   # percentage points
PRICE_TOL = 0.015    # relative; reports round prices >= AED 1M to 0.01M (<= 0.5%)
PPSF_TOL = 0.015     # relative
SCORE_TOL = 0.5


class Truth:
    def __init__(self, conn):
        cols = [d[0] for d in conn.execute("SELECT * FROM v_investment_scores LIMIT 0").description]
        self.scores = {r[0]: dict(zip(cols, r)) for r in conn.execute("SELECT * FROM v_investment_scores").fetchall()}
        self.conn = conn

    def row(self, community, field, required=True):
        value = self.scores[community][field]
        if value is None and required:
            raise ValueError(f"{community} has no {field}; pick another community for this question")
        return value

    def bedroom_price(self, community, bedrooms):
        row = self.conn.execute(
            """SELECT median(price_aed), COUNT(*) FROM transactions
               WHERE community = ? AND handover_status = 'Ready' AND bedrooms = ?""",
            [community, bedrooms],
        ).fetchone()
        if row[1] < 20:  # build_reports.py only publishes buckets with >= 20 sales
            raise ValueError(f"{community} {bedrooms}BR has {row[1]} ready sales")
        return float(row[0])

    def scored(self):
        return [c for c, s in self.scores.items() if s["composite_score"] is not None]


def pct(community, value, tol=YIELD_TOL, **kw):
    return {"community": community, "value": float(value), "kind": "pct", "tol": tol, **kw}


def item(qid, qtype, question, **expect):
    expect.setdefault("filters", {})
    return {"id": qid, "type": qtype, "question": question, "expect": expect}


def build(t: Truth):
    items = []

    def add(qtype, question, **expect):
        items.append(item(f"{qtype}_{sum(i['type'] == qtype for i in items) + 1:02d}", qtype, question, **expect))

    # 1. Yield lookups, with the aliases people type
    for q, c in [
        ("What rental yield can I expect in JVC?", JVC),
        ("What's the gross rental yield in downtown?", "Downtown Dubai"),
        ("Rental yield for apartments in Dubai Marina?", "Dubai Marina"),
        ("How much rental yield does Business Bay give?", "Business Bay"),
        ("What yield do DSO apartments return?", DSO),
        ("Gross yield in International City?", "International City"),
        ("What is the rental yield in JLT?", JLT),
        ("What return can a landlord expect in Sports City?", "Sports City"),
        ("Rental yield in Arjan?", "Arjan"),
        ("What's the yield in Dubai Creek Harbour?", "Dubai Creek Harbour"),
        ("How is the rental yield in Palm Jumeirah?", "Palm Jumeirah"),
        ("What yield does Meydan offer landlords?", "Meydan"),
        ("Rental yield in Majan?", "Majan"),
        ("What's the gross yield in JVT?", JVT),
        ("Yield on an apartment in Dubai Hills?", "Dubai Hills Estate"),
    ]:
        add("yield_lookup", q, filters={"community": c}, communities=[c],
            numbers=[pct(c, t.row(c, "avg_roi_pct"))])

    # 2. Communities without enough matched rent data: must decline
    for name, c in [("JBR", JBR), ("Discovery Gardens", "Discovery Gardens"),
                    ("Motor City", "Motor City"), ("Liwan", "Liwan"), ("The Greens", "The Greens")]:
        assert t.row(c, "avg_roi_pct", required=False) is None, f"{c} now has a yield"
        add("yield_unavailable", f"What rental yield can I expect in {name}?",
            filters={"community": c}, refuse=True, refuse_for=[c])

    # 3. Comparisons
    for a, b, q in [
        (JVC, "Dubai Marina", "Compare rental yields in JVC and Dubai Marina."),
        ("Business Bay", "Downtown Dubai", "Business Bay or Downtown: which gives the better yield?"),
        (DSO, "International City", "Compare the rental yield of DSO and International City."),
        (JLT, "Dubai Marina", "JLT vs Dubai Marina for rental yield?"),
        ("Arjan", JVT, "Is Arjan or JVT the better yield play?"),
        ("Sports City", "Dubai South", "Compare yields in Sports City and Dubai South."),
        ("Dubai Hills Estate", "Dubai Creek Harbour", "Dubai Hills or Creek Harbour for rental income?"),
        ("Meydan", "Sobha Hartland", "Compare Meydan and Sobha Hartland rental yields."),
        ("Palm Jumeirah", "Downtown Dubai", "Palm Jumeirah vs downtown yield?"),
        ("Town Square", "DAMAC Hills", "Which yields more, Town Square or DAMAC Hills?"),
    ]:
        add("compare_yield", q, filters={"communities": sorted([a, b])}, communities=[a, b],
            numbers=[pct(a, t.row(a, "avg_roi_pct")), pct(b, t.row(b, "avg_roi_pct"))])

    # 4. Recommendation and score
    for c, name in [
        ("International City", "International City"), (DSO, "Dubai Silicon Oasis"),
        ("Sports City", "Sports City"), ("Arjan", "Arjan"), ("Dubai Marina", "Dubai Marina"),
        ("Town Square", "Town Square"), ("Business Bay", "Business Bay"), (JVC, "JVC"),
        ("Dubai Production City", "Dubai Production City"), ("Downtown Dubai", "Downtown Dubai"),
        ("Palm Jumeirah", "Palm Jumeirah"), ("Majan", "Majan"),
    ]:
        add("recommendation", f"Is {name} a good investment right now?",
            filters={"community": c}, communities=[c],
            labels=[{"community": c, "value": t.row(c, "recommendation")}],
            numbers=[{"community": c, "value": float(t.row(c, "composite_score")),
                      "kind": "score", "tol": SCORE_TOL}])

    # 5. Median price by unit type (only in the generated reports: tests semantic retrieval)
    beds_word = {0: "a studio", 1: "a 1-bedroom apartment", 2: "a 2-bedroom apartment"}
    for c, name, b in [
        (JVC, "JVC", 1), (JVC, "JVC", 0), ("Business Bay", "Business Bay", 2),
        ("Dubai Marina", "Dubai Marina", 1), ("Downtown Dubai", "Downtown Dubai", 1),
        ("International City", "International City", 0), ("Arjan", "Arjan", 1),
        (DSO, "Dubai Silicon Oasis", 1), (JLT, "JLT", 2), ("Dubai Hills Estate", "Dubai Hills", 2),
    ]:
        add("price_by_bedrooms", f"How much does {beds_word[b]} cost in {name}?",
            filters={"community": c, "bedrooms": b}, communities=[c],
            numbers=[{"community": c, "value": t.bedroom_price(c, b), "kind": "aed",
                      "tol": PRICE_TOL, "rel": True}])

    # 6. Median price per sqft
    for c, name in [(JVC, "JVC"), ("Business Bay", "Business Bay"), ("Downtown Dubai", "Downtown Dubai"),
                    ("Dubai Marina", "Dubai Marina"), ("Palm Jumeirah", "Palm Jumeirah"),
                    ("International City", "International City"), ("Dubai Creek Harbour", "Creek Harbour"),
                    ("Al Furjan", "Al Furjan")]:
        add("price_per_sqft", f"What's the median price per square foot in {name}?",
            filters={"community": c}, communities=[c],
            numbers=[{"community": c, "value": float(t.row(c, "avg_price_per_sqft")), "kind": "aed",
                      "tol": PPSF_TOL, "rel": True}])

    # 7. Same-project price momentum
    for c, name in [("Business Bay", "Business Bay"), (JVC, "JVC"), ("Downtown Dubai", "Downtown Dubai"),
                    ("Dubai Marina", "Dubai Marina"), (DSO, "DSO"), ("Arjan", "Arjan"),
                    ("Dubai Hills Estate", "Dubai Hills"), ("Dubai Healthcare City", "Dubai Healthcare City")]:
        add("momentum", f"How have apartment prices in {name} moved this year?",
            filters={"community": c}, communities=[c],
            numbers=[pct(c, t.row(c, "price_momentum_pct"), tol=MOMENTUM_TOL, abs=True)])

    # 8. Supply risk
    for c, name in [("Dubai Land Residence Complex", "Dubai Land Residence Complex"), (JVT, "JVT"),
                    ("Majan", "Majan"), ("Dubai Marina", "Dubai Marina"), ("Sobha Hartland", "Sobha Hartland"),
                    (JVC, "JVC"), ("Business Bay", "Business Bay"), ("Dubai Production City", "Production City")]:
        add("supply_risk", f"What's the supply risk in {name}?",
            filters={"community": c}, communities=[c],
            labels=[{"community": c, "value": t.row(c, "supply_risk")}])

    # 9. Rankings across all communities
    scored = t.scored()
    by_yield = sorted(scored, key=lambda c: t.row(c, "avg_roi_pct"))
    by_score = sorted(scored, key=lambda c: (-t.row(c, "composite_score"), c))
    hi, lo = by_yield[-1], by_yield[0]
    add("ranking", "Which community has the highest rental yield?", communities=[hi],
        numbers=[pct(hi, t.row(hi, "avg_roi_pct"))])
    add("ranking", "Which community has the lowest rental yield?", communities=[lo],
        numbers=[pct(lo, t.row(lo, "avg_roi_pct"))])
    top = by_score[0]
    if t.row(top, "composite_score") == t.row(by_score[1], "composite_score"):
        raise ValueError("top score is tied; the question has no single answer")
    add("ranking", "Which community has the highest investment score?", communities=[top],
        numbers=[{"community": top, "value": float(t.row(top, "composite_score")), "kind": "score", "tol": SCORE_TOL}])
    top3 = by_score[:3]
    if t.row(top3[2], "composite_score") == t.row(by_score[3], "composite_score"):
        raise ValueError("third place is tied; the question has no single answer")
    add("ranking", "What are the top 3 communities by investment score?", communities=top3,
        numbers=[{"community": c, "value": float(t.row(c, "composite_score")), "kind": "score", "tol": SCORE_TOL}
                 for c in top3])
    cheapest = min(t.scores, key=lambda c: t.row(c, "avg_price_per_sqft"))
    add("ranking", "Where are apartments cheapest per square foot?", communities=[cheapest],
        numbers=[{"community": cheapest, "value": float(t.row(cheapest, "avg_price_per_sqft")),
                  "kind": "aed", "tol": PPSF_TOL, "rel": True}])
    busiest = max(t.scores, key=lambda c: t.row(c, "transaction_count"))
    add("ranking", "Which community had the most ready apartment sales this year?", communities=[busiest],
        numbers=[{"community": busiest, "value": float(t.row(busiest, "transaction_count")),
                  "kind": "number", "tol": 0}])

    # 10. Budget and bedroom filters (filter extraction; no single numeric answer)
    for q, f in [
        ("Best rental yield for a 1-bedroom under AED 1M?", {"bedrooms": 1, "max_price": 1_000_000}),
        ("Studio apartments under AED 600K in JVC", {"community": JVC, "bedrooms": 0, "max_price": 600_000}),
        ("2BR in Dubai Marina over AED 2M", {"community": "Dubai Marina", "bedrooms": 2, "min_price": 2_000_000}),
        ("What can I buy in Business Bay with a AED 1.5M budget?", {"community": "Business Bay", "max_price": 1_500_000}),
        ("Compare 1BR prices in JLT and Dubai Marina", {"communities": sorted([JLT, "Dubai Marina"]), "bedrooms": 1}),
    ]:
        add("budget_filter", q, filters=f)

    # 11. Out of scope: the answer must decline rather than invent
    for q, refuse_in_context, allowed in [
        ("What's the rental yield on villas in Arabian Ranches?", True, ["Arabian Ranches"]),
        ("Is DAMAC Hills 2 a good investment?", True, ["DAMAC Hills 2"]),
        ("What rental yield does Bluewaters offer?", True, ["Bluewaters"]),
        ("How much do penthouses on Palm Jumeirah cost?", True, []),
        ("Which developer has the best delivery track record?", False, []),
        ("What are the service charges per sqft in JVC?", False, []),
        ("What's the occupancy rate in Dubai Marina?", False, []),
        ("What were Dubai Marina apartment prices in 2024?", False, []),
    ]:
        add("out_of_scope", q, refuse=True, refuse_in_context=refuse_in_context, allowed_mentions=allowed)

    return items


def main():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    items = build(Truth(conn))
    data_window = conn.execute(
        "SELECT min(transaction_date), max(transaction_date) FROM transactions").fetchone()
    OUT.write_text(json.dumps({
        "version": 2,
        "source": "DuckDB views built from DLD open data; regenerate with eval/build_eval_set.py",
        "sales_window": [str(d) for d in data_window],
        "eval_set": items,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {}
    for i in items:
        counts[i["type"]] = counts.get(i["type"], 0) + 1
    print(f"Wrote {len(items)} questions to {OUT}")
    for k, v in counts.items():
        print(f"  {k:20} {v}")


if __name__ == "__main__":
    main()
