"""Run evaluation suite with automated correctness checks."""

import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env so LLM API keys are available (same as api/main.py)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

import duckdb
from rag import rag_query

DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"


def load_eval_set(path: Path) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["eval_set"]


def extract_numbers(text: str) -> List[float]:
    """Extract all numbers from text."""
    patterns = [
        r'[\d,]+\.?\d*%',  # percentages
        r'AED\s*[\d,]+\.?\d*',  # AED amounts
        r'[\d,]+\.?\d*(?:sqft|sq\.ft)',  # square feet
    ]
    numbers = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            cleaned = re.sub(r'[AED\s%sqft\.]', '', m).replace(',', '')
            try:
                numbers.append(float(cleaned))
            except ValueError:
                pass
    return numbers


def extract_communities(text: str) -> List[str]:
    """Extract community names from text."""
    known_communities = [
        "Downtown Dubai", "Dubai Marina", "Palm Jumeirah",
        "Dubai Hills Estate", "JVC", "Business Bay", "Arabian Ranches",
        "Sports City", "Discovery Gardens", "JLT", "The Springs",
        "Al Barsha", "Deira", "Bur Dubai", "International City",
        "Dubai Silicon Oasis", "Tilal Al Ghaf", "DAMAC Hills 2",
        "Dubai Creek Harbour", "Bluewaters Island", "Meydan",
        "Al Furjan", "Dubai South", "Town Square",
    ]
    found = []
    text_lower = text.lower()
    for c in known_communities:
        if c.lower() in text_lower:
            found.append(c)
    return found


def check_keywords(answer: str, keywords: List[str]) -> float:
    answer_lower = answer.lower()
    found = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return found / len(keywords) if keywords else 0.0


def check_number_accuracy(answer: str, db_conn) -> Dict[str, Any]:
    """Validate percentage claims against DuckDB.

    Two things this used to get wrong:

    1. It matched `(?:ROI|yield|return).*?(\\d+)%`, where the lazy `.*?` still
       crossed sentence boundaries. "Supply risk is high (15.9% pipeline)" was
       flagged as an ROI claim purely because the word "yield" appeared in an
       earlier sentence. Matching is now confined to a single clause.
    2. It validated every match against `roi_pct` only. Net yield has its own
       range (2.08-8.25 vs 4.9-10.3), so correct net-yield figures were
       reported as out-of-range. Both metrics are now checked separately.
    """
    extracted = extract_numbers(answer)
    issues = []

    ranges = {
        "roi": db_conn.execute(
            "SELECT MIN(roi_pct), MAX(roi_pct) FROM transactions"
        ).fetchone(),
        "net_yield": db_conn.execute(
            "SELECT MIN(net_yield_pct), MAX(net_yield_pct) FROM v_net_yield"
        ).fetchone(),
    }

    # Metric label -> the range that metric must fall in. "net yield" has to be
    # tested before "yield", otherwise the longer label never matches.
    # The gap between the label and the number excludes sentence terminators,
    # newlines and table pipes, so a match can never span from one sentence to
    # a number in the next.
    gap = r"[^\d%.\n|]{0,24}?"
    num = r"(\d+(?:\.\d+)?)"
    patterns = [
        (rf"net\s+yield{gap}{num}\s*%", "net_yield"),
        (rf"gross\s+(?:roi|yield){gap}{num}\s*%", "roi"),
        (rf"\byield{gap}{num}\s*%", "net_yield"),
        (rf"\broi\b{gap}{num}\s*%", "roi"),
        (rf"\breturn{gap}{num}\s*%", "roi"),
    ]

    checked: set[tuple[str, float]] = set()
    for pattern, metric in patterns:
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            key = (metric, value)
            if key in checked:
                continue
            checked.add(key)

            lo, hi = ranges.get(metric) or (None, None)
            if lo is None:
                continue
            if value < lo - 1 or value > hi + 1:
                issues.append(
                    f"{metric} {value}% outside data range ({lo}-{hi}%)"
                )

    return {
        "numbers_found": len(extracted),
        "issues": issues,
        "valid": len(issues) == 0,
    }


def _normalize_community(name: str) -> str:
    """Strip parenthetical aliases: 'JVC (Jumeirah Village Circle)' -> 'jvc'."""
    return re.sub(r"\s*\(.*\)", "", name).strip().lower()


def check_community_attribution(answer: str, valid_communities: List[str]) -> Dict[str, Any]:
    """Check if community names mentioned in the answer exist in the DB."""
    mentioned = extract_communities(answer)
    valid_set = {_normalize_community(c) for c in valid_communities}
    invalid = [c for c in mentioned if _normalize_community(c) not in valid_set]
    return {
        "communities_mentioned": mentioned,
        "invalid_communities": invalid,
        "valid_communities": len(invalid) == 0,
    }


def run_eval(eval_path: str = None, model: str = None, resume: bool = True):
    """Run full evaluation with correctness checks.

    resume=True keeps previously successful results and only re-runs failures.
    """
    if eval_path is None:
        eval_path = Path(__file__).parent / "eval_set.json"
    else:
        eval_path = Path(eval_path)

    eval_set = load_eval_set(eval_path)
    db_conn = duckdb.connect(str(DB_PATH), read_only=True)
    output_path = eval_path.parent / "eval_results.json"

    # Get valid communities from DB
    valid_communities = [r[0] for r in db_conn.execute(
        "SELECT DISTINCT community FROM transactions"
    ).fetchall()]

    # Resume: load prior successes so a rate-limited run can be completed later
    prior_ok = {}
    if resume and output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                prior = json.load(f)
            for r in prior.get("results", []):
                if r.get("status") == "ok" and r.get("answer"):
                    prior_ok[r["id"]] = r
        except (json.JSONDecodeError, KeyError):
            prior_ok = {}

    results = []
    to_run = []
    for item in eval_set:
        if item["id"] in prior_ok:
            results.append(prior_ok[item["id"]])
        else:
            to_run.append(item)

    print(f"Running evaluation with {len(eval_set)} questions...")
    print(f"Resumed: {len(results)} prior successes | To run: {len(to_run)}")
    print(f"Model: {model}")
    print("=" * 80)

    for i, item in enumerate(to_run, 1):
        print(f"\n[{i}/{len(to_run)}] {item['question']}")

        try:
            result = rag_query(item["question"], model=model)
            answer = result["answer"]

            # Score 1: Keyword matching
            keyword_score = check_keywords(answer, item["expected_keywords"])

            # Score 2: Number accuracy
            number_check = check_number_accuracy(answer, db_conn)

            # Score 3: Community attribution
            community_check = check_community_attribution(answer, valid_communities)

            # Courtesy delay to stay under Groq free-tier TPM limit
            import time
            time.sleep(1.5)

            results.append({
                "id": item["id"],
                "question": item["question"],
                "answer": answer,
                "keyword_score": keyword_score,
                "number_accuracy": number_check["valid"],
                "number_issues": number_check["issues"],
                "communities_valid": community_check["valid_communities"],
                "expected_keywords": item["expected_keywords"],
                "expected_answer_summary": item["expected_answer_summary"],
                # Record what retrieval actually did, so a score can be read in
                # light of whether the question was filtered or left unfiltered.
                "applied_filters": (result.get("structured") or {}).get("applied_filters", {}),
                "skipped_filters": (result.get("structured") or {}).get("skipped_filters", []),
                "relaxed_filters": (result.get("structured") or {}).get("relaxed_filters"),
                "context_rows": len((result.get("structured") or {}).get("transactions", [])),
                "status": "ok",
            })

            status = "PASS" if number_check["valid"] and community_check["valid_communities"] else "WARN"
            print(f"  Keywords: {keyword_score:.0%} | Numbers: {'OK' if number_check['valid'] else 'ISSUES'} | Communities: {'OK' if community_check['valid_communities'] else 'INVALID'} | {status}")

        except Exception as e:
            # Daily quota exhausted — stop early, keep what we have for resume
            if "daily token quota" in str(e) or ("tokens per day" in str(e)):
                results.append({
                    "id": item["id"],
                    "question": item["question"],
                    "answer": "",
                    "keyword_score": 0.0,
                    "number_accuracy": False,
                    "communities_valid": False,
                    "error": str(e),
                    "status": "error",
                })
                print(f"  QUOTA: {e}")
                print("\nDaily LLM quota exhausted. Re-run `make eval` after reset to resume.")
                break

            results.append({
                "id": item["id"],
                "question": item["question"],
                "answer": "",
                "keyword_score": 0.0,
                "number_accuracy": False,
                "communities_valid": False,
                "error": str(e),
                "status": "error",
            })
            print(f"  ERROR: {e}")

    # Preserve eval_set order
    order = {item["id"]: idx for idx, item in enumerate(eval_set)}
    results.sort(key=lambda r: order.get(r["id"], 999))

    # Summary
    valid_results = [r for r in results if r["status"] == "ok"]
    avg_keyword = sum(r["keyword_score"] for r in valid_results) / len(valid_results) if valid_results else 0
    number_accuracy = sum(1 for r in valid_results if r["number_accuracy"]) / len(valid_results) if valid_results else 0
    community_accuracy = sum(1 for r in valid_results if r["communities_valid"]) / len(valid_results) if valid_results else 0

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Questions: {len(eval_set)}")
    print(f"Successful: {len(valid_results)}")
    print(f"Errors: {len(eval_set) - len(valid_results)}")
    print(f"Average Keyword Score: {avg_keyword:.0%}")
    print(f"Number Accuracy: {number_accuracy:.0%}")
    print(f"Community Attribution: {community_accuracy:.0%}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": len(eval_set),
                "successful": len(valid_results),
                "errors": len(eval_set) - len(valid_results),
                "avg_keyword_score": round(avg_keyword, 3),
                "number_accuracy": round(number_accuracy, 3),
                "community_accuracy": round(community_accuracy, 3),
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")
    db_conn.close()
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-path", type=str, default=None)
    parser.add_argument("--model", type=str, default=None, help="Override model (default: provider default from env)")
    parser.add_argument("--fresh", action="store_true", help="Ignore prior results and re-run everything")
    args = parser.parse_args()
    run_eval(eval_path=args.eval_path, model=args.model, resume=not args.fresh)
