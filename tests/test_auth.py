"""F14 认证 token 单元测试。"""

from __future__ import annotations

import os


def test_create_and_verify_token() -> None:
    os.environ["JWT_SECRET"] = "unit-test-secret"
    from importlib import reload

    import app.config as config_module
    import app.middleware.auth as auth_module

    reload(config_module)
    reload(auth_module)

    token = auth_module.create_access_token("user-1", "tenant-a", roles=["editor"])
    payload = auth_module.verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-1"
    assert payload["tenant_id"] == "tenant-a"
    assert "editor" in payload["roles"]


def test_invalid_token_returns_none() -> None:
    os.environ["JWT_SECRET"] = "unit-test-secret"
    from importlib import reload

    import app.config as config_module
    import app.middleware.auth as auth_module

    reload(config_module)
    reload(auth_module)

    assert auth_module.verify_access_token("not-a-valid-token") is None
