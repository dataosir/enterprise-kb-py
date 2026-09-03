"""健康检查与指标端点冒烟。"""

from __future__ import annotations


def test_health_returns_up(client) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UP"
    assert "documents" in data
    assert "retrievalMode" in data


def test_metrics_prometheus_format(client) -> None:
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("content-type", "")
