"""Deterministic natural-language -> SQL filter extraction.

Why deterministic: the financial figures in this project come from SQL views,
never from the model. Letting an LLM decide the filter would put the same
reliability question over the WHERE clause that the architecture avoids for
every number it reports.

Two rules govern everything here:

1. **Never narrow on a guess.** A wrong filter is worse than no filter, because
   it silently removes rows and the model then reports "no such property
   exists" when the data was only filtered away. Anything not matched with
   confidence is left out of the filter and recorded in `skipped`.
2. **Never narrow to nothing.** `structured_search` re-runs without the filter
   if it matches zero rows and reports that it did so, so an extraction miss
   degrades to the unbiased sample rather than to a false "no data" answer.

The community and property-type values are matched case-insensitively and
resolved to the exact strings stored in the database, because
`community = 'business bay'` returns zero rows against a column holding
`'Business Bay'`.
"""

import re
from typing import Any, Dict, List, Optional, Sequence

# Aliases people actually type. Keys are matched case-insensitively against the
# query; values are the canonical community name as stored in DuckDB.
COMMUNITY_ALIASES: Dict[str, str] = {
    "jvc": "JVC (Jumeirah Village Circle)",
    "jumeirah village circle": "JVC (Jumeirah Village Circle)",
    "jvt": "JVT (Jumeirah Village Triangle)",
    "jumeirah village triangle": "JVT (Jumeirah Village Triangle)",
    "jlt": "JLT (Jumeirah Lake Towers)",
    "jumeirah lake towers": "JLT (Jumeirah Lake Towers)",
    "jbr": "JBR (Jumeirah Beach Residence)",
    "jumeirah beach residence": "JBR (Jumeirah Beach Residence)",
    "downtown": "Downtown Dubai",
    "dso": "Dubai Silicon Oasis",
    "silicon oasis": "Dubai Silicon Oasis",
    "dubai hills": "Dubai Hills Estate",
    "damac hills": "DAMAC Hills",
    "creek harbour": "Dubai Creek Harbour",
    "international city": "International City",
    "intl city": "International City",
    "discovery gardens": "Discovery Gardens",
    "sports city": "Sports City",
    "dubai sports city": "Sports City",
    "business bay": "Business Bay",
    "dubai marina": "Dubai Marina",
    "marina": "Dubai Marina",
    "palm jumeirah": "Palm Jumeirah",
    "the palm": "Palm Jumeirah",
    "dubai south": "Dubai South",
    "town square": "Town Square",
    "meydan": "Meydan",
    "al furjan": "Al Furjan",
    "arjan": "Arjan",
    "sobha hartland": "Sobha Hartland",
    "hartland": "Sobha Hartland",
    "majan": "Majan",
    "production city": "Dubai Production City",
    "impz": "Dubai Production City",
    "dubai land residence complex": "Dubai Land Residence Complex",
    "dlrc": "Dubai Land Residence Complex",
    "motor city": "Motor City",
    "liwan": "Liwan",
    "the greens": "The Greens",
    "healthcare city": "Dubai Healthcare City",
    "dhcc": "Dubai Healthcare City",
    "studio city": "Dubai Studio City",
}

# Communities dropped from v1 (villa-only, or too few registered apartment
# sales). A mention is reported as not covered instead of being matched to a
# similar name: "DAMAC Hills 2" must never become DAMAC Hills.
NOT_COVERED_COMMUNITIES: Dict[str, str] = {
    "damac hills 2": "villa community; v1 covers apartments only",
    "arabian ranches": "villa community; v1 covers apartments only",
    "the springs": "villa community; v1 covers apartments only",
    "springs": "villa community; v1 covers apartments only",
    "tilal al ghaf": "villa community; v1 covers apartments only",
    "bluewaters": "too few registered apartment sales in 2026 to analyse",
    "al barsha": "too few registered apartment sales in 2026 to analyse",
    "deira": "not in the v1 community list",
    "bur dubai": "not in the v1 community list",
}

# DLD apartment data only: every row is an apartment, so these words never
# narrow anything. Villas and penthouses aren't separately covered.
PROPERTY_TYPE_ALIASES: Dict[str, str] = {
    "apartment": "Apartment",
    "apartments": "Apartment",
    "flat": "Apartment",
    "flats": "Apartment",
}
NOT_COVERED_PROPERTY_TYPES = ("villa", "villas", "townhouse", "townhouses", "penthouse", "penthouses")

_NUMBER_WORDS = {
    "zero": 0, "studio": 0, "studios": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}

_MAX_WORDS = r"under|below|less\s+than|lower\s+than|cheaper\s+than|up\s+to|at\s+most|no\s+more\s+than|maximum|max"
_MIN_WORDS = r"over|above|more\s+than|higher\s+than|starting\s+(?:at|from)|at\s+least|minimum|min"


_MAGNITUDES = {
    "k": 1_000, "thousand": 1_000, "thousands": 1_000,
    "m": 1_000_000, "million": 1_000_000, "mn": 1_000_000,
    "bn": 1_000_000_000, "b": 1_000_000_000, "billion": 1_000_000_000,
}


def _to_aed(value: float, suffix: str) -> float:
    """Normalise a money figure to AED, honouring K/M/mn/bn suffixes."""
    factor = _MAGNITUDES.get(suffix.lower(), 1)
    return float(int(value * factor))


def _find_money(text: str) -> List[Dict[str, Any]]:
    """Pull money figures with an explicit unit, ignoring percentages."""
    out = []
    alt = "|".join(sorted(_MAGNITUDES, key=len, reverse=True))
    # Requires AED or an explicit magnitude, and refuses anything followed by %
    # so that "ROI 10.3%" is never read as a price.
    pattern = re.compile(
        r"(?:AED|A\.E\.D\.?|dhs|dirham)?\s*"
        r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
        rf"({alt})?\b(?!\s*%)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        raw, suffix = m.group(1), (m.group(2) or "")
        if not suffix and not re.search(r"aed|dhs|dirham", m.group(0), re.IGNORECASE):
            # A bare number with no currency marker and no magnitude is far too
            # ambiguous to use as a price ("top 3 communities", "1BR").
            continue
        try:
            amount = _to_aed(float(raw.replace(",", "")), suffix)
        except ValueError:
            continue
        out.append({"amount": amount, "start": m.start(), "end": m.end(), "text": m.group(0)})
    return out


def _extract_prices(query: str) -> tuple[Optional[int], Optional[int], List[str]]:
    """Return (min_price, max_price, skipped)."""
    skipped: List[str] = []
    text = query
    monies = _find_money(text)
    if not monies:
        return None, None, skipped

    lower = text.lower()
    min_price: Optional[int] = None
    max_price: Optional[int] = None

    for m in monies:
        window = lower[max(0, m["start"] - 45): m["start"]]
        if re.search(_MAX_WORDS, window):
            max_price = m["amount"] if max_price is None else min(max_price, m["amount"])
        elif re.search(_MIN_WORDS, window):
            min_price = m["amount"] if min_price is None else max(min_price, m["amount"])

    if min_price is None and max_price is None:
        # "AED 1M budget", "with a AED 1.5M budget" - a budget is a ceiling for
        # a buyer. A bare "AED 1.35M price" is not, so it is left unfiltered.
        if re.search(r"budget", lower):
            for m in monies:
                if re.search(r"budget", lower[m["end"]: m["end"] + 25]):
                    max_price = m["amount"]
                    break
            if max_price is None:
                max_price = monies[0]["amount"]
        else:
            skipped.append(
                "price mentioned without a directional word (under/over/budget); "
                f"left unfiltered rather than guessed: {monies[0]['text'].strip()}"
            )

    if min_price is not None and max_price is not None and min_price > max_price:
        skipped.append(f"inverted price range {min_price}-{max_price}; dropped both bounds")
        min_price = max_price = None

    return (
        int(min_price) if min_price is not None else None,
        int(max_price) if max_price is not None else None,
        skipped,
    )


def _extract_bedrooms(query: str) -> tuple[Optional[int], List[str]]:
    """Return (bedrooms, skipped). Only explicit bedroom wording counts."""
    text = query.lower()

    m = re.search(r"\bstudio\b", text)
    if m:
        return 0, []

    m = re.search(r"(\d)\s*[- ]?\s*(?:br|bed|beds|bedroom|bedrooms)\b", text)
    if m:
        return int(m.group(1)), []

    m = re.search(r"\b(" + "|".join(_NUMBER_WORDS) + r")\s*[- ]?\s*(?:bed|beds|bedroom|bedrooms)\b", text)
    if m:
        return _NUMBER_WORDS[m.group(1)], []

    # "1.5M" must not become 1 bedroom: digits only count next to bedroom words.
    m = re.search(r"(\d)\s*[- ]?\s*(?:br)\b", text)
    if m:
        return int(m.group(1)), []

    return None, []


def _extract_property_type(query: str) -> tuple[Optional[str], List[str]]:
    """Return (property_type, skipped). Ambiguous mentions are not filtered."""
    text = query.lower()
    uncovered = [w for w in NOT_COVERED_PROPERTY_TYPES if re.search(rf"\b{w}\b", text)]
    if uncovered:
        return None, [
            f"'{uncovered[0]}' isn't covered: the data is DLD-registered apartment sales "
            "only; left unfiltered"
        ]
    found = {
        canonical
        for alias, canonical in PROPERTY_TYPE_ALIASES.items()
        if re.search(rf"\b{re.escape(alias)}\b", text)
    }
    if not found:
        return None, []
    if len(found) > 1:
        return None, [f"multiple property types mentioned ({', '.join(sorted(found))}); left unfiltered"]
    return found.pop(), []


def _extract_community(query: str, known: Sequence[str]) -> tuple[List[str], List[str]]:
    """Resolve community mentions to their exact database strings.

    `known` should be the community values from the database. One match is a
    filter; two or more are a comparison, returned as a list so retrieval can
    scope scores and rows to the communities being compared. Leaving that
    comparison unfiltered returned all 24 scores and then showed only the top
    8, so both communities could be missing from the context.
    """
    text = query.lower()
    by_norm = {c.lower(): c for c in known}
    by_norm.update({c.lower().strip(): c for c in known})

    # Report uncovered communities, then blank them out so a covered alias
    # inside them ("damac hills" in "damac hills 2") can't match.
    skipped: List[str] = []
    for name, reason in sorted(NOT_COVERED_COMMUNITIES.items(), key=lambda kv: -len(kv[0])):
        pattern = rf"\b{re.escape(name)}\b"
        if re.search(pattern, text):
            skipped.append(f"'{name}' isn't covered ({reason})")
            text = re.sub(pattern, " ", text)

    matches: Dict[str, str] = {}
    for alias, canonical in COMMUNITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text) and canonical in known:
            matches[canonical] = canonical
    for name, canonical in by_norm.items():
        if name and re.search(rf"\b{re.escape(name)}\b", text):
            matches[canonical] = canonical

    if not matches:
        return [], skipped
    if len(matches) > 1:
        names = sorted(matches)
        return names, skipped + [
            f"query names {len(names)} communities ({', '.join(names)}); "
            "comparison scoped to those communities"
        ]
    return [next(iter(matches))], skipped


def extract_filters(
    query: str,
    known_communities: Sequence[str] = (),
) -> Dict[str, Any]:
    """Extract SQL filters from a natural-language query.

    Returns ``{"filters": {...}, "skipped": [...]}``. The filters dict contains
    only high-confidence extractions; ``skipped`` explains anything ambiguous
    that was deliberately not filtered on.
    """
    skipped: List[str] = []

    communities, s = _extract_community(query, known_communities)
    skipped += s
    property_type, s = _extract_property_type(query)
    skipped += s
    bedrooms, s = _extract_bedrooms(query)
    skipped += s
    min_price, max_price, s = _extract_prices(query)
    skipped += s

    filters: Dict[str, Any] = {}
    if len(communities) == 1:
        filters["community"] = communities[0]
    elif len(communities) > 1:
        filters["communities"] = communities
    if property_type:
        filters["property_type"] = property_type
    if bedrooms is not None:
        filters["bedrooms"] = bedrooms
    if min_price is not None:
        filters["min_price"] = min_price
    if max_price is not None:
        filters["max_price"] = max_price

    return {"filters": filters, "skipped": skipped}
