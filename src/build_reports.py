"""Write one market report per community from the DLD views in DuckDB.

Every figure in a report comes from a query against the same views the API
serves, so the semantic (ChromaDB) branch of the RAG can't contradict the
structured one. Reports land in data/reports/ and are embedded by ingest.py.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import duckdb

from config import DB_PATH, REPORTS_DIR

MIN_BUCKET_SALES = 20  # bedroom or project rows below this are left out
WINDOW = "January–September 2026"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _aed(v: float) -> str:
    return f"AED {v / 1e6:.2f}M" if v >= 1e6 else f"AED {v:,.0f}"


def _beds(n) -> str:
    return "Studio" if n == 0 else f"{n}BR"


def build_report(conn, community: str) -> str:
    s = dict(zip(
        [d[0] for d in conn.execute("SELECT * FROM v_investment_scores LIMIT 0").description],
        conn.execute("SELECT * FROM v_investment_scores WHERE community = ?", [community]).fetchone(),
    ))
    quarters = conn.execute("""
        SELECT quarter, avg_price_per_sqft, market_volume FROM price_history
        WHERE community = ? ORDER BY quarter_start
    """, [community]).fetchall()
    beds = conn.execute(f"""
        SELECT bedrooms, median(price_aed), median(price_aed / size_sqft), COUNT(*)
        FROM transactions WHERE community = ? AND handover_status = 'Ready' AND bedrooms IS NOT NULL
        GROUP BY bedrooms HAVING COUNT(*) >= {MIN_BUCKET_SALES} ORDER BY bedrooms
    """, [community]).fetchall()
    projects = conn.execute(f"""
        SELECT project, COUNT(*), median(price_aed / size_sqft) FROM transactions
        WHERE community = ? AND handover_status = 'Ready' AND project IS NOT NULL
        GROUP BY project HAVING COUNT(*) >= {MIN_BUCKET_SALES} ORDER BY 2 DESC LIMIT 5
    """, [community]).fetchall()
    handovers = conn.execute("""
        SELECT project, units, completion_date FROM dld_projects
        WHERE community = ? AND status = 'FINISHED' AND units > 0
        ORDER BY units DESC LIMIT 5
    """, [community]).fetchall()

    lines = [f"# {community} Market Report (DLD data, {WINDOW})", ""]

    lines += ["## Summary", ""]
    signal = (
        f"Investment signal: {s['recommendation']} (score {s['composite_score']:.0f}/100)."
        if s["composite_score"] is not None else
        "Investment signal: insufficient data. Too few Ejari rent contracts to compute a "
        "rental yield, so no score is given."
    )
    lines += [
        f"{community} recorded {s['transaction_count']:,} ready and {s['offplan_sales']:,} "
        f"off-plan apartment sales registered with the Dubai Land Department in {WINDOW}. "
        f"The median ready apartment sold for {_aed(s['avg_price'])} "
        f"(AED {s['avg_price_per_sqft']:,.0f} per sqft). {signal}",
        "",
    ]

    lines += ["## Prices", ""]
    if quarters:
        lines.append("Median ready price per sqft by quarter: " + "; ".join(
            f"{q} AED {p:,.0f} ({n:,} sales)" for q, p, n in quarters) + ".")
    if beds:
        lines.append("Median ready price by unit type: " + "; ".join(
            f"{_beds(b)} {_aed(p)} (AED {ppsf:,.0f}/sqft, {n:,} sales)" for b, p, ppsf, n in beds) + ".")
    lines.append("")

    lines += ["## Rental Yield", ""]
    if s["avg_roi_pct"] is None:
        lines.append(
            f"Not enough matched rent data for a reliable yield: {s['yield_projects']} projects here "
            f"have both new Ejari contracts and ready sales ({s['matched_contracts']} contracts); "
            f"3 projects and 30 contracts are needed. {s['rent_contracts']:,} rent contracts in total "
            "are linked to this community."
        )
    else:
        lines.append(
            f"Gross rental yield is {s['avg_roi_pct']:.2f}%. For each of {s['yield_projects']} "
            f"projects with both new Ejari contracts ({s['matched_contracts']:,} in total, 1–22 "
            "October 2026) and ready sales, median annual rent per square metre is divided by the "
            "same project's median sale price per square metre; this is the median across those "
            "projects. Comparing the same buildings avoids setting one tower's rents against "
            f"another's prices. Net of management and vacancy it is {s['avg_net_yield_pct']:.2f}%, "
            "before service charges, which DLD does not publish."
        )
    lines.append("")

    lines += ["## Price Momentum", ""]
    if s["price_momentum_pct"] is None:
        lines.append(
            "Not measured: fewer than 5 projects had at least 3 ready sales in both Q1 and Q3 2026."
        )
    else:
        direction = "rose" if s["price_momentum_pct"] > 0 else "fell"
        lines.append(
            f"Comparing the same {s['paired_projects']} projects in Q1 and Q3 2026, prices per sqft "
            f"{direction} by a median of {abs(s['price_momentum_pct']):.1f}%. This compares like with "
            "like, unlike the quarterly medians above, which move with which buildings sold."
        )
    lines.append("")

    lines += ["## Supply", ""]
    if s["offplan_sales"]:
        lines.append(
            f"{s['offplan_sales']:,} off-plan apartments were sold against {s['transaction_count']:,} "
            f"ready ones (ratio {s['pipeline_ratio']:.2f}), so supply risk is {s['supply_risk']}: "
            "off-plan units sold now are stock still to be handed over."
        )
    else:
        lines.append(
            "No off-plan apartments were sold here in 2026, so the data shows no new supply "
            f"pipeline. Supply risk is {s['supply_risk']}."
        )
    if handovers:
        lines.append(
            f"DLD registered {s['units_completed_2026']:,} apartments here as completed in 2026, "
            "including " + "; ".join(f"{p} ({u:,} units, {d})" for p, u, d in handovers) + "."
        )
    lines.append("")

    if projects:
        lines += ["## Most Active Ready Projects", ""]
        lines.append("; ".join(
            f"{p}: {n:,} sales at a median AED {ppsf:,.0f}/sqft" for p, n, ppsf in projects) + ".")
        lines.append("")

    lines += [
        "## Source and Method", "",
        f"Dubai Land Department open data: registered apartment sales ({WINDOW}) and Ejari rent "
        "contracts (1–22 October 2026), cleaned by src/dld_loader.py (duplicates, non-apartments "
        "and price outliers removed). Figures are medians. Generated by src/build_reports.py.",
        "",
    ]
    return "\n".join(lines)


def build_all() -> int:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    communities = [r[0] for r in conn.execute(
        "SELECT community FROM v_investment_scores ORDER BY community").fetchall()]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for old in REPORTS_DIR.glob("*.md"):
        old.unlink()
    for community in communities:
        (REPORTS_DIR / f"{_slug(community)}.md").write_text(build_report(conn, community), encoding="utf-8")
    conn.close()
    return len(communities)


if __name__ == "__main__":
    print(f"Wrote {build_all()} community reports to {REPORTS_DIR}")
