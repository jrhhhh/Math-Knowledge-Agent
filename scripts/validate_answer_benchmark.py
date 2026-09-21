#!/usr/bin/env python3
"""Validate the human-reviewed answer benchmark structure without grading it."""
import json
import sys
from pathlib import Path


ALLOWED = {"correct", "partially_correct", "incorrect", "unverified"}
REQUIRED = {"id", "type", "question", "reference_answer", "required_conditions", "key_steps", "common_errors", "labels"}
LABELS = {"conclusion", "conditions", "reasoning", "citations"}


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/answer_benchmark.chapter1.json")
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise SystemExit("benchmark must be a non-empty JSON list")
    ids = set()
    for index, item in enumerate(items, 1):
        missing = REQUIRED - item.keys()
        if missing:
            raise SystemExit(f"case {index} missing: {sorted(missing)}")
        if item["id"] in ids:
            raise SystemExit(f"duplicate id: {item['id']}")
        ids.add(item["id"])
        if not all(isinstance(item[field], list) and item[field] for field in ("required_conditions", "key_steps", "common_errors")):
            raise SystemExit(f"case {item['id']} must contain non-empty rubric lists")
        if set(item["labels"]) != LABELS or not set(item["labels"].values()) <= ALLOWED:
            raise SystemExit(f"case {item['id']} has invalid review labels")
    print(f"validated {len(items)} reviewed benchmark cases; labels are human-review targets, not automatic proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
