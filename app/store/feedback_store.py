from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import BASE_DIR

FEEDBACK_FILE = BASE_DIR / "data" / "eval" / "feedback.jsonl"


def append_feedback(
    *,
    rating: str,
    question: str | None = None,
    answer: str | None = None,
    conversation_id: str | None = None,
    comment: str | None = None,
    expected_filename: str | None = None,
) -> dict:
    record = {
        "id": str(uuid4()),
        "rating": rating,
        "question": question,
        "answer": answer,
        "conversation_id": conversation_id,
        "comment": comment,
        "expected_filename": expected_filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
