#!/usr/bin/env python3
"""Report human-review coverage and agreement for the answer benchmark.

The result file is intentionally separate from the benchmark fixture. A result
record has the case ``id`` and the four reviewed labels. This tool reports
coverage and exact label agreement; it never calls a model and never infers a
human label from an answer.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

DIMENSIONS = ("conclusion", "conditions", "reasoning", "citations")
ALLOWED = {"correct", "partially_correct", "incorrect", "unverified"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default="data/answer_benchmark.chapter1.json")
    parser.add_argument("--results", help="JSON list of reviewed records")
    args = parser.parse_args()
    cases = load_json(Path(args.benchmark))
    expected = {item["id"]: item for item in cases}
    results = load_json(Path(args.results)) if args.results else []
    reviewed = {}
    for item in results:
        case_id = item.get("id")
        if case_id not in expected:
            raise SystemExit(f"unknown benchmark id: {case_id}")
        if case_id in reviewed:
            raise SystemExit(f"duplicate result id: {case_id}")
        labels = item.get("labels", {})
        if set(labels) != set(DIMENSIONS) or not set(labels.values()) <= ALLOWED:
            raise SystemExit(f"invalid labels for result: {case_id}")
        reviewed[case_id] = labels

    print(f"cases: {len(cases)}")
    print(f"reviewed: {len(reviewed)}")
    print(f"unreviewed: {len(cases) - len(reviewed)}")
    if not reviewed:
        print("No human results supplied; no correctness rate is reported.")
        return 0
    for dimension in DIMENSIONS:
        target = [expected[case_id]["labels"][dimension] for case_id in reviewed]
        actual = [reviewed[case_id][dimension] for case_id in reviewed]
        exact = sum(left == right for left, right in zip(target, actual))
        print(f"{dimension}: exact_agreement={exact}/{len(actual)} ({exact / len(actual):.1%})")
        print(f"  target={dict(Counter(target))}")
        print(f"  reviewed={dict(Counter(actual))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
