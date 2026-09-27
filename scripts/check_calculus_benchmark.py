#!/usr/bin/env python3
"""Check recorded tool contracts, not general mathematical correctness."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses", type=Path)
    parser.add_argument("--benchmark", type=Path, default=Path("data/agent_benchmark.calculus.json"))
    args = parser.parse_args()
    cases = json.loads(args.benchmark.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in args.responses.read_text(encoding="utf-8").splitlines() if line.strip()]
    indexed = {}
    for row in rows:
        if row.get("id") in indexed:
            parser.error(f"duplicate response id: {row.get('id')}")
        indexed[row.get("id")] = row
    known = {case["id"] for case in cases}
    if set(indexed) - known:
        parser.error("responses contain unknown case ids")
    counts = {"exact_results": 0, "refutations": 0, "clarifications": 0, "expected_rejections": 0, "mismatches": 0, "missing": 0, "human_review_required": 0}
    categories = {"completed_with_evidence": "exact_results", "refuted": "refutations", "needs_clarification": "clarifications", "failed": "expected_rejections"}
    for case in cases:
        if case.get("requires_human_review"):
            counts["human_review_required"] += 1
            continue
        row = indexed.get(case["id"])
        if row is None:
            counts["missing"] += 1
            continue
        body = row.get("response") or {}
        result = (body.get("trace") or [{}])[0].get("result") or {}
        matched = body.get("status") == case["expected_status"]
        matched = matched and all(result.get(key) == value for key, value in case.get("expected_result", {}).items())
        if "expected_missing" in case:
            matched = matched and sorted(result.get("missing") or []) == sorted(case["expected_missing"])
        if case["expected_status"] == "failed":
            matched = matched and not body.get("evidence") and bool(body.get("failed_attempt"))
        counts[categories[case["expected_status"]] if matched else "mismatches"] += 1
        print(f"{case['id']}: {'contract_matched' if matched else 'MISMATCH'}")
    print(json.dumps(counts, ensure_ascii=False))
    print("Expected rejections are safety checks, not solved math problems. Proof correctness is not scored.")
    return int(bool(counts["mismatches"] or counts["missing"]))


if __name__ == "__main__":
    raise SystemExit(main())
