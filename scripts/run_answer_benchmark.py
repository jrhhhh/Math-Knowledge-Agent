#!/usr/bin/env python3
"""Run the answer benchmark against a live Math-Agent API and save raw results.

This script records model output and execution metadata only. It does not infer
mathematical correctness; human labels remain a separate review artifact.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit
import uuid


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def post_json(url: str, payload: dict, timeout: float) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, timeout: float) -> dict:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_base_url(value: str) -> str:
    parts = urlsplit(value)
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path.rstrip("/"), "", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Math-Agent API base URL")
    parser.add_argument("--benchmark", default="data/answer_benchmark.chapter1.json")
    parser.add_argument("--output-dir", help="Output directory; defaults to evaluation/runs/<UTC timestamp>")
    parser.add_argument("--mode", choices=("direct", "agent-run"), default="direct", help="Run the direct answer endpoint or the bounded agent loop")
    parser.add_argument("--limit", type=int, help="Run only the first N cases (useful for a smoke run)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--pause", type=float, default=0.0, help="Seconds to wait between model requests")
    parser.add_argument("--max-steps", type=int, default=3, help="Agent loop step limit when --mode agent-run is selected")
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark)
    cases = read_json(benchmark_path)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        cases = cases[:args.limit]
    if not cases:
        parser.error("benchmark contains no cases")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.pause < 0:
        parser.error("--pause cannot be negative")
    if args.mode == "agent-run" and not 1 <= args.max_steps <= 8:
        parser.error("--max-steps must be between 1 and 8")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir) if args.output_dir else Path("evaluation/runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    benchmark_hash = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()
    try:
        health = get_json(f"{args.api_url.rstrip('/')}/ai/health", args.timeout)
        model_config = {key: health.get(key) for key in (
            "primary_model", "primary_model_configured", "primary_timeout_seconds",
            "request_budget_seconds", "backup_model_configured",
        )}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        model_config = {"available": False, "reason": "health_endpoint_unavailable"}
    metadata = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "api_url": safe_base_url(args.api_url),
        "endpoint": "/ai/agent/run" if args.mode == "agent-run" else "/ai/ask",
        "benchmark": str(benchmark_path),
        "benchmark_sha256": benchmark_hash,
        "case_count": len(cases),
        "mode": args.mode,
        "max_steps": args.max_steps if args.mode == "agent-run" else None,
        "model_config": model_config,
        "correctness_scoring": "not_scored; requires independent human review",
    }
    (output_dir / "config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results_path = output_dir / "responses.jsonl"
    completed = 0
    failed = 0
    with results_path.open("w", encoding="utf-8") as results_file:
        for index, case in enumerate(cases, 1):
            request_id = uuid.uuid4().hex[:12]
            started = time.perf_counter()
            record = {
                "id": case.get("id"),
                "type": case.get("type"),
                "question": case.get("question", ""),
                "request_id": request_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                endpoint = "/ai/agent/run" if args.mode == "agent-run" else "/ai/ask"
                payload = {"question": record["question"], "max_steps": args.max_steps} if args.mode == "agent-run" else {"question": record["question"], "agent_mode": False}
                answer = post_json(
                    f"{args.api_url.rstrip('/')}{endpoint}",
                    payload,
                    args.timeout,
                )
                record["response"] = answer
                semantic_failure = args.mode == "agent-run" and answer.get("status") == "failed"
                record["outcome"] = "failed" if semantic_failure else "succeeded"
                record["api_request"] = "succeeded"
                completed += int(not semantic_failure)
                failed += int(semantic_failure)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                record["outcome"] = "failed"
                record["api_request"] = "failed"
                record["error"] = type(exc).__name__
                failed += 1
            record["duration_seconds"] = round(time.perf_counter() - started, 3)
            results_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            results_file.flush()
            print(f"[{index}/{len(cases)}] {record['id']}: {record['outcome']} ({record['duration_seconds']}s)")
            if args.pause and index < len(cases):
                time.sleep(max(0.0, args.pause))

    metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
    metadata["completed"] = completed
    metadata["failed"] = failed
    (output_dir / "config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Run saved to {output_dir}; completed={completed}, failed={failed}. Human review is still required.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
