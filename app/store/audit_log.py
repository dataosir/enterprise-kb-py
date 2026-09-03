"""审计日志：append-only JSONL，记录上传/删除/设置变更。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import AUDIT_DIR

AUDIT_FILE = AUDIT_DIR / "audit.jsonl"


def append_audit(
    action: str,
    *,
    user_id: str = "anonymous",
    tenant_id: str = "default",
    resource: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "resource": resource,
        "detail": detail or {},
    }
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
