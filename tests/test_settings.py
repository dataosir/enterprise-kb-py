"""RAG 设置 API 冒烟。"""

from __future__ import annotations


def test_get_rag_settings(client) -> None:
    res = client.get("/api/settings/rag")
    assert res.status_code == 200
    data = res.json()
    assert "topK" in data
    assert "chunkSize" in data
    assert "retrievalMode" in data


def test_update_top_k(client) -> None:
    original = client.get("/api/settings/rag").json()
    new_top_k = 5 if original["topK"] != 5 else 6
    res = client.put("/api/settings/rag", json={"topK": new_top_k})
    assert res.status_code == 200
    assert res.json()["topK"] == new_top_k
    # 恢复
    client.put("/api/settings/rag", json={"topK": original["topK"]})
