"""Run the DLD eval set (eval/eval_set.json) and score retrieval and answers.

  python eval/run_eval.py --retrieval-only   # no LLM calls: is each answer reachable?
  python eval/run_eval.py                    # full run against the configured LLM
  python eval/run_eval.py --fresh            # ignore prior results
  python eval/run_eval.py --rescore          # re-score saved answers after a scorer fix

Two scores per question (eval/scoring.py):
  retrieval  the right filters applied, and the expected numbers/labels are in
             the context next to the right community
  answer     the model stated them correctly, declined where it should, named
             no communities the data doesn't have; DLD citation tracked separately

A full run resumes: questions answered in a previous run are kept, so a run
cut short by the provider's daily quota can be finished after the reset.
Results go to eval/eval_results.json (full) or eval/retrieval_results.json.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

try:  # LLM keys, as api/main.py loads them
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from scoring import score_answer, score_retrieval  # noqa: E402

EVAL_DIR = Path(__file__).parent
REQUEST_DELAY_S = 1.5  # courtesy gap for the Groq free tier's tokens-per-minute cap


def load_eval_set(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 2:
        raise SystemExit(f"{path} is not a v2 eval set; run eval/build_eval_set.py")
    return data["eval_set"]


def summarize(results: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    """Pass rate overall and per question type for results[key]."""
    scored = [r for r in results if r.get(key)]
    by_type: Dict[str, List[bool]] = defaultdict(list)
    for r in scored:
        by_type[r["type"]].append(r[key]["pass"])
    summary = {
        "questions": len(scored),
        "pass_rate": round(sum(r[key]["pass"] for r in scored) / len(scored), 3) if scored else 0.0,
        "by_type": {t: {"n": len(v), "pass_rate": round(sum(v) / len(v), 3)} for t, v in by_type.items()},
    }
    if key == "answer":
        summary["cites_source_rate"] = round(sum(r[key]["cites_source"] for r in scored) / len(scored), 3) if scored else 0.0
        summary["invented_community_answers"] = sum(bool(r[key]["invented_communities"]) for r in scored)
    return summary


def print_summary(title: str, s: Dict[str, Any]):
    print(f"\n{title}: {s['pass_rate']:.0%} of {s['questions']} questions pass")
    for t, v in s["by_type"].items():
        print(f"  {t:20} {v['pass_rate']:>5.0%}  (n={v['n']})")
    if "cites_source_rate" in s:
        print(f"  cites DLD as source  {s['cites_source_rate']:>5.0%}")
        print(f"  answers naming communities not in the data: {s['invented_community_answers']}")


def run_retrieval_only(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    from rag import retrieve

    results = []
    for item in items:
        retrieved = retrieve(item["question"])
        results.append({"id": item["id"], "type": item["type"], "question": item["question"],
                        "retrieval": score_retrieval(item, retrieved)})
    summary = summarize(results, "retrieval")
    out = EVAL_DIR / "retrieval_results.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print_summary("RETRIEVAL", summary)
    print(f"\nSaved to {out}")
    return summary


def _save(out: Path, items: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Write results in eval-set order with a summary over the answered ones."""
    order = {item["id"]: i for i, item in enumerate(items)}
    results.sort(key=lambda r: order.get(r["id"], 10_000))
    ok = [r for r in results if r.get("status") == "ok"]
    summary = {
        "total": len(items),
        "answered": len(ok),
        "errors": sum(r.get("status") == "error" for r in results),
        "retrieval": summarize(ok, "retrieval"),
        "answer": summarize(ok, "answer"),
    }
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(out)  # atomic: an interrupted write never corrupts the resume file
    return summary


def run_full(items: List[Dict[str, Any]], model: str = None, resume: bool = True) -> Dict[str, Any]:
    from rag import generate_answer, known_communities, retrieve

    out = EVAL_DIR / "eval_results.json"
    known = known_communities()
    prior = {}
    if resume and out.exists():
        for r in json.loads(out.read_text(encoding="utf-8")).get("results", []):
            if r.get("status") == "ok":
                prior[r["id"]] = r

    results = []
    todo = []
    for item in items:
        if item["id"] in prior:
            results.append(prior[item["id"]])
        else:
            todo.append(item)
    print(f"{len(items)} questions | resumed {len(results)} | to run {len(todo)} | model {model or 'default'}")

    for n, item in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {item['id']}: {item['question']}")
        record = {"id": item["id"], "type": item["type"], "question": item["question"]}
        try:
            retrieved = retrieve(item["question"])
            answer = generate_answer(item["question"], retrieved["context"], retrieved["structured"],
                                     retrieved["semantic"], model=model)
            record.update({
                "answer_text": answer,
                "retrieval": score_retrieval(item, retrieved),
                "answer": score_answer(item, answer, known),
                "status": "ok",
            })
            print(f"   retrieval {'PASS' if record['retrieval']['pass'] else 'FAIL'} | "
                  f"answer {'PASS' if record['answer']['pass'] else 'FAIL'}", flush=True)
            results.append(record)
            # Saved after every answer: a run spread over days (free-tier quota)
            # must not lose a day's answers to a crash or a closed terminal.
            summary = _save(out, items, results)
            time.sleep(REQUEST_DELAY_S)
        except Exception as e:  # keep going; quota errors stop the run below
            record.update({"status": "error", "error": str(e)})
            print(f"   ERROR: {e}", flush=True)
            results.append(record)
            summary = _save(out, items, results)
            if "tokens per day" in str(e) or "daily" in str(e).lower():
                print("Daily quota reached: re-run the same command after the reset to resume.")
                break

    summary = _save(out, items, results)
    print_summary("RETRIEVAL", summary["retrieval"])
    print_summary("ANSWERS", summary["answer"])
    print(f"\nSaved to {out}")
    return summary


def rescore(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Re-score saved answers with the current scorer; no LLM calls.

    Used after a scorer fix so every answer in a multi-day run is judged by the
    same rules. Retrieval scores are kept (the context isn't stored).
    """
    from rag import known_communities

    out = EVAL_DIR / "eval_results.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in items}
    known = known_communities()
    changed = 0
    for r in data["results"]:
        if r.get("status") == "ok" and r["id"] in by_id:
            new = score_answer(by_id[r["id"]], r["answer_text"], known)
            changed += new["pass"] != r["answer"]["pass"]
            r["answer"] = new
    summary = _save(out, items, data["results"])
    print(f"Re-scored {summary['answered']} answers; {changed} changed pass/fail")
    print_summary("ANSWERS", summary["answer"])
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-path", type=Path, default=EVAL_DIR / "eval_set.json")
    parser.add_argument("--retrieval-only", action="store_true", help="score retrieval only; no LLM calls")
    parser.add_argument("--model", default=None, help="override the provider's default model")
    parser.add_argument("--fresh", action="store_true", help="ignore prior results and re-run everything")
    parser.add_argument("--only", default=None, help="comma-separated question types to run")
    parser.add_argument("--rescore", action="store_true", help="re-score saved answers; no LLM calls")
    args = parser.parse_args()

    eval_items = load_eval_set(args.eval_path)
    if args.only:
        wanted = set(args.only.split(","))
        eval_items = [i for i in eval_items if i["type"] in wanted]
    if args.rescore:
        rescore(eval_items)
    elif args.retrieval_only:
        run_retrieval_only(eval_items)
    else:
        run_full(eval_items, model=args.model, resume=not args.fresh)
