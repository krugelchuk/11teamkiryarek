"""Evaluation on independent questions: paraphrasing, typos, out-of-scope, foreign data, security."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.assistant import answer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def evaluate_independent(dataset_path=None):
    if dataset_path is None:
        dataset_path = ROOT / "content/assistant-eval-independent.json"
    dataset_file = Path(dataset_path)
    if not dataset_file.is_absolute():
        dataset_file = ROOT / dataset_file

    pack = json.loads((ROOT / "content/learning-pack.json").read_text(encoding="utf-8"))
    payload = json.loads(dataset_file.read_text(encoding="utf-8"))
    cases = payload["cases"]
    articles = [{**item["data"], "id": index + 1000, "slug": item["slug"]} for index, item in enumerate(pack["documents"])]
    by_id = {article["id"]: article["slug"] for article in articles}
    results = []

    for case in cases:
        visible = [article for article in articles if case["role"] in article["roles"]]
        response = answer(case["question"], visible, {"id": 7, "vacation_balance": 18})
        actual = ["profile" if source["url"] == "/api/profile" else by_id.get(source["id"]) for source in response["sources"]]
        expected = case["expected_source"]
        passed = not response["found"] if expected is None else response["found"] and expected in actual
        results.append({
            **case,
            "passed": bool(passed),
            "found": response["found"],
            "actual_sources": actual,
            "mode": response["mode"]
        })

    positive = [r for r in results if r["expected_source"] is not None]
    negative = [r for r in results if r["expected_source"] is None]

    return {
        "dataset": payload.get("description", dataset_file.stem),
        "dataset_file": dataset_file.name,
        "total": len(results),
        "passed": sum(r["passed"] for r in results),
        "positive_passed": sum(r["passed"] for r in positive),
        "positive_total": len(positive),
        "refusals_passed": sum(r["passed"] for r in negative),
        "refusals_total": len(negative),
        "false_answers": sum(r["found"] for r in negative),
        "results": results
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="?", default="content/assistant-eval-independent.json", help="Path to evaluation JSON dataset")
    parser.add_argument("--dataset", dest="dataset_opt", type=Path, default=None, help="Explicit path to evaluation JSON dataset")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    chosen_dataset = args.dataset_opt if args.dataset_opt is not None else args.dataset

    old = os.environ.get("JANAMEN_AI_PROVIDER")
    os.environ["JANAMEN_AI_PROVIDER"] = "disabled"
    try:
        report = evaluate_independent(chosen_dataset)
    finally:
        if old is None:
            os.environ.pop("JANAMEN_AI_PROVIDER", None)
        else:
            os.environ["JANAMEN_AI_PROVIDER"] = old

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))
    for r in report["results"]:
        if not r["passed"]:
            print("MISS", r["id"], r["question"], "expected", r["expected_source"], "got", r["actual_sources"])


if __name__ == "__main__":
    main()
