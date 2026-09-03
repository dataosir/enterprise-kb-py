"""F14 认证中间件：可选 Bearer Token，默认关闭与 Demo 行为一致。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import AUTH_ENABLED, DEFAULT_TENANT, JWT_SECRET, JWT_TTL_SECONDS

# 无需鉴权的 API 路径（静态资源由 mount 处理，不在此中间件范围）
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/eval/dashboard",
    "/api/middleware/map",
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(
    user_id: str,
    tenant_id: str | None = None,
    *,
    roles: list[str] | None = None,
    ttl_seconds: int | None = None,
) -> str:
    """生成简易 HMAC JWT（演示用；生产可换 PyJWT + OIDC）。"""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id or DEFAULT_TENANT,
        "roles": roles or ["viewer"],
        "iat": now,
        "exp": now + (ttl_seconds or JWT_TTL_SECONDS),
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, json.JSONDecodeError, KeyError):
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.tenant_id = DEFAULT_TENANT
        request.state.user_id = "anonymous"
        request.state.roles = ["admin"]  # Demo 模式视为全权限

        if not AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/") or path in PUBLIC_API_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "缺少 Authorization: Bearer <token>"})

        token = auth_header[7:].strip()
        payload = verify_access_token(token)
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "无效或已过期的 Token"})

        request.state.user_id = str(payload.get("sub", "unknown"))
        request.state.tenant_id = str(payload.get("tenant_id", DEFAULT_TENANT))
        request.state.roles = list(payload.get("roles") or ["viewer"])
        return await call_next(request)
