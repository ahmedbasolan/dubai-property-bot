"""Answers built from DuckDB alone, for when no LLM is available.

The public demo runs without a server-side LLM key, and the free tier's daily
quota runs out, so this path is what many visitors actually see. It used to
print the top communities by score whatever was asked; "which community has
the highest yield?" then named the top *score*, and a villa question got an
INVEST signal for apartments.

So the answer follows the question, deterministically:

1. Decline what the data doesn't hold (villas, developers, service charges,
   occupancy, other years) instead of showing unrelated numbers.
2. Work out the metric asked about (yield, score, price, price per sq ft,
   momentum, supply, sales volume).
3. Named communities: lead with that metric for each, then a profile table.
   No community: rank all communities by that metric.

Every number comes from the same views the rest of the app serves.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from db_setup import DATA_SOURCE
from filters import extract_filters

DATA_YEAR = 2026

# Topics with no column behind them. Checked before anything else, so a
# question about one never gets an answer about something adjacent.
_UNCOVERED_TOPICS = [
    (r"\bdevelopers?\b|\bdelivery track record\b",
     "Developer track records are not covered: DLD sales records carry no developer field."),
    (r"\bservice charges?\b",
     "Service charges are not covered: DLD doesn't publish them. Net yields here are "
     "before service charges."),
    (r"\b(?:occupancy|vacancy)\b",
     "Occupancy and vacancy rates are not covered: they aren't in DLD's open data."),
]

_METRICS = [
    # Order matters: "price per sq ft" is a price question, but a more specific one.
    ("sqft", r"per\s*(?:sq|square)|sq\.?\s*ft|sqft|psf"),
    ("momentum", r"momentum|moved|moving|rising|falling|trend|appreciat|going (?:up|down)"
                 r"|price (?:change|growth|movement)|increas|decreas"),
    ("supply", r"supply|pipeline|handovers?\b"),
    ("volume", r"most (?:ready )?(?:apartment )?(?:sales|transactions)|busiest|liquid"),
    ("score", r"\bscores?\b|invest|worth|recommend|good (?:buy|place|area)"),
    ("yield", r"yield|\breturns?\b|rental income|\broi\b|landlord"),
    ("price", r"\bcost|price|how much|sell for|\bbudget|afford|cheap|expensive"),
]

_LOW_WORDS = r"lowest|weakest|worst|cheapest|least|bottom|smallest|fewest"
_RANK_WORDS = (r"highest|best|strongest|top|most|biggest|largest|which (?:community|area)"
               r"|where (?:do|does|is|are|can|should)|" + _LOW_WORDS)
_NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10}


def data_only_answer(query: str, reason: str) -> Tuple[str, Dict[str, Any]]:
    """Markdown answer and the structured data it was built from."""
    from rag import known_communities

    extracted = extract_filters(query, known_communities())
    filters = extracted["filters"]
    communities = ([filters["community"]] if filters.get("community")
                   else list(filters.get("communities") or []))
    scores = _scores()
    structured = {
        "community_scores": [scores[c] for c in communities if c in scores]
        or sorted(scores.values(), key=_score_order),
        "transactions": [],
        "applied_filters": filters,
        "skipped_filters": extracted["skipped"],
    }

    lines = [f"**{query}**", "", f"_{reason} This answer is generated from the data only._", ""]
    uncovered = _uncovered(query, extracted["skipped"])
    if uncovered:
        lines += uncovered
    elif communities:
        lines += _community_answer(_metric(query), communities, scores, filters.get("bedrooms"))
    elif any(filters.get(k) is not None for k in ("bedrooms", "min_price", "max_price")):
        # Before rankings: "best area for a 1 bed under 900k" is a budget question.
        lines += _filtered_sales_answer(filters, scores)
    elif _is_ranking(query):
        lines += _ranking_answer(query, _metric(query) or "score", scores)
    else:
        lines += _ranking_answer(query, _metric(query) or "score", scores, default_n=5)

    lines += ["", "---",
              f"Source: {DATA_SOURCE}, Jan-Sep {DATA_YEAR}. Net yields are before service charges."]
    return "\n".join(lines), structured


# --- What was asked ---------------------------------------------------------

def _uncovered(query: str, skipped: List[str]) -> List[str]:
    text = query.lower()
    notes = [note for pattern, note in _UNCOVERED_TOPICS if re.search(pattern, text)]
    other_years = sorted({y for y in re.findall(r"\b(20\d\d)\b", text) if int(y) != DATA_YEAR})
    if other_years:
        notes.append(f"{', '.join(other_years)} isn't covered: the data is DLD's "
                     f"January-September {DATA_YEAR} records only.")
    notes += [_sentence(s) for s in skipped if "isn't covered" in s]
    return notes


def _sentence(skip_note: str) -> str:
    note = skip_note.replace("; left unfiltered", "")
    return note[0].upper() + note[1:] + "."


def _metric(query: str) -> Optional[str]:
    text = query.lower()
    for name, pattern in _METRICS:
        if re.search(pattern, text):
            return name
    return None


def _is_ranking(query: str) -> bool:
    return bool(re.search(rf"\b(?:{_RANK_WORDS})\b", query.lower()))


def _top_n(query: str, default: int) -> int:
    text = query.lower()
    m = re.search(r"\b(?:top|best|first)\s+(\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\b", text) \
        or re.search(r"\b(\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\s+(?:best|top|communities|areas)\b", text)
    if not m:
        return default
    word = m.group(1)
    return int(word) if word.isdigit() else _NUMBER_WORDS[word]


# --- Data -------------------------------------------------------------------

def _scores() -> Dict[str, Dict[str, Any]]:
    from rag import _db

    cursor = _db().execute("SELECT * FROM v_investment_scores")
    cols = [d[0] for d in cursor.description]
    return {row[0]: dict(zip(cols, row)) for row in cursor.fetchall()}


def _score_order(s: Dict[str, Any]):
    return (s["composite_score"] is None, -(s["composite_score"] or 0), s["community"])


# --- Formatting -------------------------------------------------------------

def _pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.2f}%"


def _aed(v: Optional[float]) -> str:
    return "n/a" if v is None else f"AED {v:,.0f}"


def _beds(n: int) -> str:
    return "studio" if n == 0 else f"{n}-bedroom"


_PROFILE_HEADER = [
    "| Community | Gross yield | Net yield | Score | Signal | AED/sq ft | Momentum | Supply risk |",
    "|-----------|------------:|----------:|------:|--------|----------:|---------:|-------------|",
]


def _profile_row(s: Dict[str, Any]) -> str:
    score = "n/a" if s["composite_score"] is None else f"{s['composite_score']:.0f}/100"
    momentum = "n/a" if s["price_momentum_pct"] is None else f"{s['price_momentum_pct']:+.1f}%"
    return (f"| {s['community']} | {_pct(s['avg_roi_pct'])} | {_pct(s['avg_net_yield_pct'])} | "
            f"{score} | {s['recommendation']} | {_aed(s['avg_price_per_sqft'])} | {momentum} | "
            f"{s['supply_risk'] or 'n/a'} |")


def _no_yield(s: Dict[str, Any]) -> str:
    return (f"{s['community']} has insufficient matched rent data for a reliable yield "
            f"({s['matched_contracts'] or 0} Ejari contracts matched to its sales).")


def _lead(metric: Optional[str], s: Dict[str, Any], bedrooms: Optional[int]) -> str:
    c = s["community"]
    if bedrooms is not None:
        from rag import MIN_BEDROOM_SALES, bedroom_median

        median, count = bedroom_median(c, bedrooms)
        if count < MIN_BEDROOM_SALES:
            return (f"{c} had {count} ready {_beds(bedrooms)} sales, too few for a reliable "
                    "median price.")
        return (f"Median ready {_beds(bedrooms)} price in {c}: **{_aed(median)}** "
                f"({count:,} registered sales).")
    if metric == "sqft":
        return f"Median ready price in {c}: **{_aed(s['avg_price_per_sqft'])} per sq ft**."
    if metric == "price":
        return (f"Median ready apartment price in {c}: **{_aed(s['avg_price'])}** "
                f"({_aed(s['avg_price_per_sqft'])} per sq ft).")
    if metric == "momentum":
        if s["price_momentum_pct"] is None:
            return f"{c} has insufficient same-project sales to measure price momentum."
        return (f"Same-project prices in {c} moved **{s['price_momentum_pct']:+.1f}%** "
                f"from Q1 to Q3 {DATA_YEAR}.")
    if metric == "supply":
        return (f"Supply risk in {c}: **{s['supply_risk']}** (off-plan sales to ready sales "
                f"ratio {s['pipeline_ratio']:.1f}).")
    if metric == "volume":
        return f"{c} had **{s['transaction_count']:,}** ready apartment sales in Jan-Sep {DATA_YEAR}."
    if metric == "score" or (metric is None and s["avg_roi_pct"] is not None):
        if s["composite_score"] is None:
            return _no_yield(s) + " It has no investment score."
        return (f"{c} scores **{s['composite_score']:.0f}/100**: **{s['recommendation']}** "
                f"(gross yield {_pct(s['avg_roi_pct'])}).")
    if s["avg_roi_pct"] is None:
        return _no_yield(s)
    return (f"Gross rental yield in {c}: **{_pct(s['avg_roi_pct'])}** "
            f"(net {_pct(s['avg_net_yield_pct'])} before service charges).")


def _community_answer(metric, communities, scores, bedrooms) -> List[str]:
    rows = [scores[c] for c in communities if c in scores]
    lines = [_lead(metric, s, bedrooms) for s in rows]
    with_yield = [s for s in rows if s["avg_roi_pct"] is not None]
    if len(rows) > 1 and metric in (None, "yield") and len(with_yield) > 1:
        best = max(with_yield, key=lambda s: s["avg_roi_pct"])
        lines.append(f"{best['community']} has the higher gross yield.")
    return lines + ["", *_PROFILE_HEADER, *(_profile_row(s) for s in rows)]


_RANK_FIELDS = {
    "yield": ("avg_roi_pct", "gross rental yield", _pct),
    "sqft": ("avg_price_per_sqft", "median ready price per sq ft", _aed),
    "price": ("avg_price_per_sqft", "median ready price per sq ft", _aed),
    "momentum": ("price_momentum_pct", "same-project price change Q1 to Q3", lambda v: f"{v:+.1f}%"),
    "volume": ("transaction_count", "ready apartment sales", lambda v: f"{v:,}"),
    "supply": ("pipeline_ratio", "off-plan to ready sales ratio", lambda v: f"{v:.1f}"),
    "score": ("composite_score", "investment score", lambda v: f"{v:.0f}/100"),
}


def _ranking_answer(query: str, metric: str, scores, default_n: int = 1) -> List[str]:
    field, label, fmt = _RANK_FIELDS[metric]
    low = bool(re.search(rf"\b(?:{_LOW_WORDS})\b", query.lower())) or (
        metric in ("sqft", "price") and "expensive" not in query.lower())
    if metric in ("sqft", "price") and re.search(r"highest|most expensive|priciest", query.lower()):
        low = False
    ranked = sorted((s for s in scores.values() if s[field] is not None),
                    key=lambda s: (s[field], s["community"]), reverse=not low)
    if low:
        ranked = sorted(ranked, key=lambda s: (s[field], s["community"]))
    n = _top_n(query, default_n if not re.search(r"communities|areas|places", query.lower()) else 5)
    top = ranked[:n]
    word = "Lowest" if low else "Highest"
    lines = [f"{word} {label}: **{top[0]['community']}** at **{fmt(top[0][field])}**.", ""]
    show_score = metric != "score"  # the ranked column already is the score
    lines += [f"| Rank | Community | {label[0].upper() + label[1:]} |"
              + (" Score |" if show_score else "") + " Signal |",
              "|-----:|-----------|------:|" + ("------:|" if show_score else "") + "--------|"]
    for i, s in enumerate(top, 1):
        score = "n/a" if s["composite_score"] is None else f"{s['composite_score']:.0f}/100"
        lines.append(f"| {i} | {s['community']} | {fmt(s[field])} |"
                     + (f" {score} |" if show_score else "") + f" {s['recommendation']} |")
    skipped = len(scores) - len(ranked)
    if skipped:
        lines += ["", f"{skipped} communities have insufficient data for this measure and are "
                      "not ranked."]
    return lines


def _filtered_sales_answer(filters: Dict[str, Any], scores) -> List[str]:
    """Budget or bedroom questions with no community: where matching sales happened."""
    from rag import _db

    where, params = ["handover_status = 'Ready'"], []
    if filters.get("bedrooms") is not None:
        where.append("bedrooms = ?")
        params.append(filters["bedrooms"])
    if filters.get("min_price") is not None:
        where.append("price_aed >= ?")
        params.append(filters["min_price"])
    if filters.get("max_price") is not None:
        where.append("price_aed <= ?")
        params.append(filters["max_price"])
    rows = _db().execute(
        f"""SELECT community, COUNT(*), median(price_aed) FROM transactions
            WHERE {' AND '.join(where)} GROUP BY community""",
        params,
    ).fetchall()
    rows = sorted(rows, key=lambda r: (scores.get(r[0], {}).get("avg_roi_pct") is None,
                                       -(scores.get(r[0], {}).get("avg_roi_pct") or 0)))
    if not rows:
        return ["No registered ready sales match those filters."]
    lines = ["Communities with matching ready sales, by gross yield:", "",
             "| Community | Matching sales | Median price | Gross yield | Signal |",
             "|-----------|---------------:|-------------:|------------:|--------|"]
    for community, count, median in rows[:8]:
        s = scores.get(community, {})
        lines.append(f"| {community} | {count:,} | {_aed(median)} | {_pct(s.get('avg_roi_pct'))} | "
                     f"{s.get('recommendation', 'n/a')} |")
    return lines
