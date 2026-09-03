"""pytest 公共 fixture。"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# 测试环境：关闭认证，避免用例需 token
os.environ.setdefault("AUTH_ENABLED", "false")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
