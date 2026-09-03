"""问答与检索 API 冒烟（不调用 LLM 的路径）。"""

from __future__ import annotations


def test_preview_sources(client) -> None:
    res = client.get("/api/chat/sources", params={"question": "退款多久到账？"})
    assert res.status_code == 200
    sources = res.json()
    assert isinstance(sources, list)
    if sources:
        assert "filename" in sources[0]
        assert "snippet" in sources[0]


def test_new_conversation(client) -> None:
    res = client.post("/api/chat/conversation")
    assert res.status_code == 200
    assert "conversationId" in res.json()


def test_eval_dashboard(client) -> None:
    res = client.get("/api/eval/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "layers" in data
    assert "gate" in data
