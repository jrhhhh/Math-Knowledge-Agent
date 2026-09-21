#!/usr/bin/env python3
"""Import selected, human-reviewed PDF pages into the local knowledge API.

This intentionally imports only pages explicitly supplied by the operator. It
does not commit the source PDF or silently mark arbitrary OCR as approved.
"""

import argparse
import json
import urllib.request
from pathlib import Path

from pypdf import PdfReader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", required=True, help="1-based inclusive range, e.g. 14-16")
    parser.add_argument("--title", required=True)
    parser.add_argument("--course", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--review-status", choices=("draft", "approved"), default="draft")
    args = parser.parse_args()

    start, end = (int(value) for value in args.pages.split("-", 1))
    if start < 1 or end < start:
        raise SystemExit("pages 必须是合法的 1-based 范围")
    reader = PdfReader(str(args.pdf))
    if end > len(reader.pages):
        raise SystemExit(f"PDF 只有 {len(reader.pages)} 页")

    chunks = []
    for page_number in range(start, end + 1):
        content = (reader.pages[page_number - 1].extract_text() or "").strip()
        if not content:
            raise SystemExit(f"第 {page_number} 页没有可提取文本，请人工处理")
        chunks.append({
            "page_start": page_number,
            "page_end": page_number,
            "heading": args.chapter,
            "chunk_type": "chapter_excerpt",
            "content": content,
            "review_status": args.review_status,
        })

    payload = {
        "title": args.title,
        "course": args.course,
        "chapter": args.chapter,
        "source_uri": str(args.pdf.resolve()),
        "review_status": args.review_status,
        "chunks": chunks,
    }
    request = urllib.request.Request(
        f"{args.api.rstrip('/')}/knowledge/documents",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
