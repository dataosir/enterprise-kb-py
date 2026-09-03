#!/usr/bin/env python3
"""将用户差评导出为 benchmark 用例候选，供人工审核后合并进 benchmark_cases.json。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FEEDBACK = ROOT / "data" / "eval" / "feedback.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "eval" / "bad_cases_candidates.json"


def load_feedback(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def to_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    question = (row.get("question") or "").strip()
    if not question:
        return None
    return {
        "question": question,
        "expected_filename": row.get("expected_filename") or "TODO.md",
        "expected_answer": row.get("answer") or row.get("expected_answer"),
        "tags": ["feedback", "bad_case"],
        "difficulty": "medium",
        "source": {
            "feedback_id": row.get("id"),
            "rating": row.get("rating"),
            "comment": row.get("comment"),
            "created_at": row.get("created_at"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导出差评为 benchmark 候选用例")
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rating", default="down", help="筛选 rating，默认 down")
    args = parser.parse_args()

    feedback_rows = load_feedback(args.feedback)
    negatives = [r for r in feedback_rows if r.get("rating") == args.rating]
    candidates = [c for row in negatives if (c := to_candidate(row))]

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(args.feedback),
        "rating_filter": args.rating,
        "total_feedback": len(feedback_rows),
        "negative_count": len(negatives),
        "candidates": candidates,
        "note": "请人工填写 expected_filename 并审核后合并到 scripts/benchmark_cases.json",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"反馈总数: {len(feedback_rows)}")
    print(f"差评数 ({args.rating}): {len(negatives)}")
    print(f"候选用例: {len(candidates)}")
    print(f"已写入: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
