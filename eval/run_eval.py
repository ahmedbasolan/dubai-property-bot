"""Run evaluation suite with automated correctness checks."""

import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import duckdb
from rag import rag_query

PROJECT_ROOT = Path(__file__).parent.parent
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
    """Validate numbers in answer against DuckDB data."""
    extracted = extract_numbers(answer)
    issues = []

    # Check if ROI claims match data
    roi_matches = re.findall(r'(?:ROI|yield|return).*?(\d+\.?\d*)%', answer, re.IGNORECASE)
    for roi_str in roi_matches:
        try:
            roi_val = float(roi_str)
            # Verify against DB
            result = db_conn.execute(
                "SELECT MIN(roi_pct), MAX(roi_pct) FROM transactions"
            ).fetchone()
            if result and (roi_val < result[0] - 1 or roi_val > result[1] + 1):
                issues.append(f"ROI {roi_val}% outside data range ({result[0]}-{result[1]}%)")
        except ValueError:
            pass

    return {
        "numbers_found": len(extracted),
        "issues": issues,
        "valid": len(issues) == 0,
    }


def check_community_attribution(answer: str, expected_communities: List[str]) -> Dict[str, Any]:
    """Check if community names mentioned are valid."""
    mentioned = extract_communities(answer)
    return {
        "communities_mentioned": mentioned,
        "valid_communities": all(c in expected_communities for c in mentioned) if mentioned else True,
    }


def run_eval(eval_path: str = None, model: str = "openai/gpt-4o-mini"):
    """Run full evaluation with correctness checks."""
    if eval_path is None:
        eval_path = Path(__file__).parent / "eval_set.json"
    else:
        eval_path = Path(eval_path)

    eval_set = load_eval_set(eval_path)
    db_conn = duckdb.connect(str(DB_PATH), read_only=True)

    # Get valid communities from DB
    valid_communities = [r[0] for r in db_conn.execute(
        "SELECT DISTINCT community FROM transactions"
    ).fetchall()]

    results = []
    print(f"Running evaluation with {len(eval_set)} questions...")
    print(f"Model: {model}")
    print("=" * 80)

    for i, item in enumerate(eval_set, 1):
        print(f"\n[{i}/{len(eval_set)}] {item['question']}")

        try:
            result = rag_query(item["question"], model=model)
            answer = result["answer"]

            # Score 1: Keyword matching
            keyword_score = check_keywords(answer, item["expected_keywords"])

            # Score 2: Number accuracy
            number_check = check_number_accuracy(answer, db_conn)

            # Score 3: Community attribution
            community_check = check_community_attribution(answer, valid_communities)

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
                "status": "ok",
            })

            status = "PASS" if number_check["valid"] and community_check["valid_communities"] else "WARN"
            print(f"  Keywords: {keyword_score:.0%} | Numbers: {'OK' if number_check['valid'] else 'ISSUES'} | Communities: {'OK' if community_check['valid_communities'] else 'INVALID'} | {status}")

        except Exception as e:
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

    output_path = eval_path.parent / "eval_results.json"
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
    parser.add_argument("--model", type=str, default="openai/gpt-4o-mini")
    args = parser.parse_args()
    run_eval(eval_path=args.eval_path, model=args.model)
