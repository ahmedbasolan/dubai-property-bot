"""Scoring for the DLD eval set (eval/eval_set.json).

Each question carries ground truth computed from DuckDB by build_eval_set.py.
The same checks run against two texts:

* the **context** the model was given (retrieval: was the answer reachable?)
* the **answer** it wrote (generation: did it state it correctly?)

A number or label only counts when it sits in a segment (a line, a table row
or a sentence) that names the community it belongs to, so "JVC 7.39%" can't be
satisfied by Marina's 7.39% in another sentence. With a single expected
community the whole text is in scope.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from filters import COMMUNITY_ALIASES  # noqa: E402

REFUSAL_MARKERS = (
    "insufficient", "not enough", "isn't enough", "aren't enough", "no reliable",
    "not available", "unavailable", "no data",
    "don't have", "do not have", "doesn't have", "does not have", "isn't covered",
    "is not covered", "not covered", "doesn't publish", "does not publish",
    "not published", "no yield", "cannot", "can't", "not in the data",
    "isn't in the data", "not part of", "outside the", "no rent data",
    "lack", "too few",
)
SOURCE_MARKERS = ("dld", "dubai land department")

_PCT = re.compile(r"([+\-−–]?\d+(?:\.\d+)?)\s*%")
_AED = re.compile(
    r"(?:AED|Dhs?\.?)\s*([\d,]+(?:\.\d+)?)\s*(m|mn|million|k|thousand)?\b"
    r"|([\d,]+(?:\.\d+)?)\s*(m|mn|million|k)\s*AED\b",
    re.IGNORECASE,
)
_SCORE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:/\s*100|points?\b)", re.IGNORECASE)
_BARE = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\d%])")


# --- Text handling ---------------------------------------------------------

# Models write "Palm Jumeirah" and "ready‑sale": a narrow no-break
# space defeats `\b...\b` matching on the community name, and a non-breaking
# hyphen hides "not-enough"-style markers. Normalise both before matching.
_NORMALISE = str.maketrans({
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "‐": "-", "‑": "-",
})


def normalise(text: str) -> str:
    return text.translate(_NORMALISE)


def segments(text: str) -> List[str]:
    """Lines, then sentences. A table row is one line, so its cells stay together."""
    text = normalise(text)
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Split on sentence ends, never inside a decimal ("7.39").
        out.extend(p for p in re.split(r"(?<=[.!?])\s+(?=[A-Z*|(\[])", line) if p.strip())
    return out


def community_aliases(community: str) -> List[str]:
    """Lower-case strings that refer to a community in free text."""
    names = {community.lower(), re.sub(r"\s*\(.*\)", "", community).strip().lower()}
    inner = re.search(r"\((.*)\)", community)
    if inner:
        names.add(inner.group(1).lower())
    names.update(alias for alias, canonical in COMMUNITY_ALIASES.items() if canonical == community)
    return sorted(names, key=len, reverse=True)


def mentions(text: str, community: str) -> bool:
    low = normalise(text).lower()
    return any(re.search(rf"\b{re.escape(a)}\b", low) for a in community_aliases(community))


# A sample-sale line ("[11-21083-2026] 2026-07-08, JVC, ..."). Every expected
# value is a community-level figure, so a single sale's price or estimated
# yield landing within tolerance is a coincidence, not an answer.
_SALE_LINE = re.compile(r"^\[\d+-\d+-\d{4}\]")


def scope(text: str, community: Optional[str], single: bool, strict: bool = False) -> List[str]:
    """Segments a value for `community` may come from.

    With one expected community an answer may name it once and give the figure
    in the next sentence, so its whole text is in scope. `strict` (used for the
    retrieval context, where every row names its community) always requires
    the community in the same segment.
    """
    segs = [s for s in segments(text) if not _SALE_LINE.match(s)]
    if community is None or (single and not strict):
        return segs
    return [s for s in segs if mentions(s, community)]


def percents(text: str) -> List[float]:
    return [float(m.group(1).replace("−", "-").replace("–", "-")) for m in _PCT.finditer(text)]


def aed_amounts(text: str) -> List[float]:
    vals = []
    for m in _AED.finditer(text):
        raw, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        v = float(raw.replace(",", ""))
        unit = (unit or "").lower()
        if unit in ("m", "mn", "million"):
            v *= 1_000_000
        elif unit in ("k", "thousand"):
            v *= 1_000
        vals.append(v)
    return vals


def scores(text: str) -> List[float]:
    vals = [float(m.group(1)) for m in _SCORE.finditer(text)]
    # "Score: 74" or a table cell "| 74 |" next to the word score
    if "score" in text.lower():
        vals += [float(m.group(1).replace(",", "")) for m in _BARE.finditer(text)]
    return vals


def bare_numbers(text: str) -> List[float]:
    return [float(m.group(1).replace(",", "")) for m in _BARE.finditer(text)]


EXTRACTORS = {"pct": percents, "aed": aed_amounts, "score": scores, "number": bare_numbers}


def _close(found: float, expected: float, tol: float, rel: bool, absolute: bool = False) -> bool:
    if absolute:  # "fell 9.6%" states -9.6% as a positive number
        found, expected = abs(found), abs(expected)
    return abs(found - expected) <= (abs(expected) * tol if rel else tol)


# --- Checks ------------------------------------------------------------------

def check_number(text: str, n: Dict[str, Any], single: bool, strict: bool = False) -> bool:
    """n = {community, value, kind: pct|aed|score|number, tol, rel, abs}."""
    extract = EXTRACTORS[n["kind"]]
    for seg in scope(text, n.get("community"), single, strict):
        for v in extract(seg):
            if _close(v, n["value"], n["tol"], n.get("rel", False), n.get("abs", False)):
                return True
    return False


def check_label(text: str, label: Dict[str, Any], single: bool, strict: bool = False) -> bool:
    """label = {community, value}. Word match, case-insensitive."""
    pattern = rf"\b{re.escape(label['value'].lower())}\b"
    return any(re.search(pattern, s.lower()) for s in scope(text, label.get("community"), single, strict))


def refuses(text: str, community: Optional[str] = None) -> bool:
    """A refusal marker, near the community when one is given."""
    segs = segments(text)
    if community:
        near = [s for s in segs if mentions(s, community)]
        segs = near or segs
    return any(m in s.lower() for s in segs for m in REFUSAL_MARKERS)


def states_yield_for(text: str, community: str) -> List[float]:
    """Percentages stated as a yield for `community` (must be none when unavailable)."""
    found = []
    for s in segments(text):
        low = s.lower()
        if mentions(s, community) and ("yield" in low or "roi" in low or "return" in low):
            if not any(m in low for m in REFUSAL_MARKERS):
                found += percents(s)
    return found


def mentions_source(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in SOURCE_MARKERS)


def invented_communities(text: str, known: Iterable[str], allowed: Sequence[str] = ()) -> List[str]:
    """Dubai place names the answer presents that the data doesn't have.

    Checks a fixed list of well-known areas not in v1, so an answer naming one
    (other than one the question itself raised) is flagged as invented data.
    """
    outside_v1 = ["Arabian Ranches", "The Springs", "Tilal Al Ghaf", "DAMAC Hills 2",
                  "Bluewaters", "Al Barsha", "Deira", "Bur Dubai", "Emirates Hills",
                  "Jumeirah Golf Estates", "Mudon", "Dubai Islands", "Al Quoz"]
    allowed_low = {a.lower() for a in allowed}
    known_low = {k.lower() for k in known}
    low = text.lower()
    return [p for p in outside_v1
            if p.lower() not in allowed_low and p.lower() not in known_low
            and re.search(rf"\b{re.escape(p.lower())}\b", low)]


# --- Scoring a question -----------------------------------------------------

def score_text(item: Dict[str, Any], text: str, in_context: bool = False) -> Dict[str, Any]:
    """Score `text` (context or answer) against an item's expectations.

    In the context, a refusal is only required where retrieval itself should
    flag the gap (an INSUFFICIENT DATA row, a "not covered" note); some
    out-of-scope questions (developers, service charges) have nothing for
    retrieval to flag and are judged on the answer alone.
    """
    text = normalise(text)
    exp = item["expect"]
    single = len(exp.get("communities", [])) <= 1
    numbers = [dict(n, ok=check_number(text, n, single, strict=in_context)) for n in exp.get("numbers", [])]
    labels = [dict(l, ok=check_label(text, l, single, strict=in_context)) for l in exp.get("labels", [])]
    missing_mentions = [c for c in exp.get("communities", []) if not mentions(text, c)]

    refusal_ok = True
    leaked = []
    if exp.get("refuse") and (not in_context or exp.get("refuse_in_context", True)):
        targets = exp.get("refuse_for") or [None]
        refusal_ok = all(refuses(text, c) for c in targets)
        for c in exp.get("refuse_for", []):
            leaked += states_yield_for(text, c)

    passed = (all(n["ok"] for n in numbers) and all(l["ok"] for l in labels)
              and not missing_mentions and refusal_ok and not leaked)
    return {
        "pass": passed,
        "numbers": numbers,
        "labels": labels,
        "missing_mentions": missing_mentions,
        "refusal_ok": refusal_ok,
        "leaked_yields": leaked,
    }


def filters_match(expected: Dict[str, Any], applied: Dict[str, Any]) -> bool:
    """Every expected filter key is applied with the expected value.

    A comparison's community list compares as a set, since its order means nothing.
    """
    for key, value in expected.items():
        got = applied.get(key)
        if isinstance(value, list):
            if sorted(got or []) != sorted(value):
                return False
        elif got != value:
            return False
    return True


def score_retrieval(item: Dict[str, Any], retrieved: Dict[str, Any]) -> Dict[str, Any]:
    """Was the expected answer reachable from what retrieval handed the model?"""
    structured = retrieved["structured"]
    applied = structured.get("applied_filters") or {}
    filt_ok = filters_match(item["expect"].get("filters", {}), applied)
    ctx = score_text(item, retrieved["context"], in_context=True)
    return {
        "pass": filt_ok and ctx["pass"],
        "filters_ok": filt_ok,
        "applied_filters": applied,
        "skipped_filters": structured.get("skipped_filters", []),
        "context": ctx,
    }


def score_answer(item: Dict[str, Any], answer: str, known: Iterable[str]) -> Dict[str, Any]:
    answer = normalise(answer)
    result = score_text(item, answer)
    invented = invented_communities(answer, known, item["expect"].get("allowed_mentions", []))
    result["invented_communities"] = invented
    result["cites_source"] = mentions_source(answer)
    result["pass"] = result["pass"] and not invented
    return result
