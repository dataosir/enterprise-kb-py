#!/usr/bin/env python3
"""生成 F14 演示用 Bearer Token。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.middleware.auth import create_access_token


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 JWT Bearer Token（需 AUTH_ENABLED=true）")
    parser.add_argument("--user", default="demo-user", help="用户 ID")
    parser.add_argument("--tenant", default=None, help="租户 ID，默认 DEFAULT_TENANT")
    parser.add_argument("--role", action="append", default=["admin"], help="角色，可多次指定")
    args = parser.parse_args()

    token = create_access_token(args.user, args.tenant, roles=args.role)
    print(token)
    print("\n用法: curl -H 'Authorization: Bearer <token>' http://127.0.0.1:8081/api/documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
