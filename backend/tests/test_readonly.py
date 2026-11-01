"""공개 시연용 읽기 전용 모드(VPD_READONLY=1)와 질문 호출 제한(VPD_ASK_PER_MINUTE)."""

import pytest

from app.routers import advisor as advisor_router
from tests.test_advisor import API_GH
from tests.test_api import GREENHOUSE, client, engine  # noqa: F401  fixture 재사용
from tests.test_auth import make_public, new_client
from tests.test_today import m, post


@pytest.fixture(autouse=True)
def fresh_limit():
    advisor_router.ask_limit.clear()
    yield
    advisor_router.ask_limit.clear()


def demo_greenhouse(client, engine=None):  # noqa: F811
    """읽기 전용을 켜기 전에 데모 온실을 만들어 둔다 (실제로는 VPD_DEMO가 켤 때 만든다).
    engine을 주면 공개 온실로 — 로그인 안 한 방문자도 볼 수 있게."""
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", t=18, rh=95, co2=450))
    if engine is not None:
        make_public(engine, gh["id"])
    return gh["id"], f"/greenhouses/{gh['id']}/advisor"


def test_config_reports_modes(client, monkeypatch):  # noqa: F811
    monkeypatch.delenv("VPD_READONLY", raising=False)
    monkeypatch.delenv("VPD_ADVISOR_LLM", raising=False)
    assert client.get("/config").json() == {"readonly": False, "demo": False, "llm": False}
    monkeypatch.setenv("VPD_READONLY", "1")
    monkeypatch.setenv("VPD_DEMO", "1")
    monkeypatch.setenv("VPD_ADVISOR_LLM", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert client.get("/config").json() == {"readonly": True, "demo": True, "llm": True}


def test_readonly_blocks_changes_but_allows_reading(client, monkeypatch):  # noqa: F811
    gh_id, url = demo_greenhouse(client)
    advice_id = client.get(url).json()["advice_id"]
    monkeypatch.setenv("VPD_READONLY", "1")

    blocked = [
        client.post("/greenhouses", json=GREENHOUSE),
        client.patch(f"/greenhouses/{gh_id}", json={"name": "바꿈"}),
        client.delete(f"/greenhouses/{gh_id}"),
        client.post(f"/greenhouses/{gh_id}/ingest-token"),
        client.post(f"/greenhouses/{gh_id}/ingest", json={"measurements": [m("2026-10-01T01:00:00")]}),
        client.post(f"{url}/{advice_id}/decisions", json={"candidate_index": 0, "decision": "done"}),
    ]
    assert [r.status_code for r in blocked] == [403] * len(blocked)
    assert "읽기 전용" in blocked[0].json()["detail"]

    assert client.get(f"/greenhouses/{gh_id}").status_code == 200
    assert client.get(url).status_code == 200
    asked = client.post(f"{url}/ask", json={"question": "지금 뭐 해야 해?", "visitor": "v1"})
    assert asked.status_code == 200


def test_readonly_keeps_each_visitor_conversation_apart(client, engine, monkeypatch):  # noqa: F811
    _, url = demo_greenhouse(client, engine)
    monkeypatch.setenv("VPD_READONLY", "1")
    anon = new_client()  # 로그인 안 한 방문자
    assert anon.post(f"{url}/ask", json={"question": "누구?"}).status_code == 422  # 방문자 id 필요

    anon.post(f"{url}/ask", json={"question": "A의 질문", "visitor": "visitor-a"})
    anon.post(f"{url}/ask", json={"question": "B의 질문", "visitor": "visitor-b"})
    a = anon.get(f"{url}/questions", params={"visitor": "visitor-a"}).json()
    assert [h["question"] for h in a] == ["A의 질문"]
    assert anon.get(f"{url}/questions").json() == []  # 방문자 없이는 남의 대화가 안 보인다


def test_follow_up_history_is_per_visitor(client, engine, monkeypatch):  # noqa: F811
    seen = []
    real = advisor_router.answer_question

    def spy(question, fact, history=None):
        seen.append([h["question"] for h in history or []])
        return real(question, fact, history=history)

    monkeypatch.setattr(advisor_router, "answer_question", spy)
    _, url = demo_greenhouse(client, engine)
    monkeypatch.setenv("VPD_READONLY", "1")
    anon = new_client()
    anon.post(f"{url}/ask", json={"question": "A1", "visitor": "a"})
    anon.post(f"{url}/ask", json={"question": "B1", "visitor": "b"})
    anon.post(f"{url}/ask", json={"question": "A2", "visitor": "a"})
    assert seen == [[], [], ["A1"]]


def test_ask_rate_limit(client, monkeypatch):  # noqa: F811
    _, url = demo_greenhouse(client)
    monkeypatch.setenv("VPD_ASK_PER_MINUTE", "2")
    codes = [client.post(f"{url}/ask", json={"question": f"질문 {i}"}).status_code for i in range(3)]
    assert codes == [200, 200, 429]
    res = client.post(f"{url}/ask", json={"question": "또"})
    assert "1분" in res.json()["detail"]


def test_no_rate_limit_by_default(client, monkeypatch):  # noqa: F811
    _, url = demo_greenhouse(client)
    monkeypatch.delenv("VPD_ASK_PER_MINUTE", raising=False)
    assert all(client.post(f"{url}/ask", json={"question": f"q{i}"}).status_code == 200 for i in range(5))
