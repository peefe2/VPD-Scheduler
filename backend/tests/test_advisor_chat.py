"""질문하기 대화 내역: 질문·답을 온실별로 저장하고 채팅처럼 다시 불러온다."""

from sqlmodel import Session, select

from app.models import AdviceQuestion
from app.routers import advisor as advisor_router
from tests.test_advisor import API_GH
from tests.test_api import client, engine  # noqa: F401  fixture 재사용
from tests.test_today import m, post


def setup(client, hour="2026-10-01T00:00:00"):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m(hour, t=18, rh=95, co2=450))
    return gh["id"], f"/greenhouses/{gh['id']}/advisor"


def test_ask_is_saved_and_listed_in_order(client):  # noqa: F811
    _, url = setup(client)
    first = client.post(f"{url}/ask", json={"question": "지금 뭐 해야 해?"}).json()
    client.post(f"{url}/ask", json={"question": "환기해도 돼?"})

    assert first["id"] and first["question"] == "지금 뭐 해야 해?"
    history = client.get(f"{url}/questions").json()
    assert [h["question"] for h in history] == ["지금 뭐 해야 해?", "환기해도 돼?"]  # 오래된 것부터
    h = history[0]
    assert h["answer"] == first["answer"] and h["source"] == "rule" and "규칙 기반" in h["note"]
    assert h["observed_at"].startswith("2026-10-01T00:00") and h["vpd"] > 0 and h["asked_at"]


def test_history_limit_keeps_latest(client):  # noqa: F811
    _, url = setup(client)
    for i in range(5):
        client.post(f"{url}/ask", json={"question": f"질문 {i}"})
    history = client.get(f"{url}/questions", params={"limit": 3}).json()
    assert [h["question"] for h in history] == ["질문 2", "질문 3", "질문 4"]


def test_history_is_per_greenhouse(client):  # noqa: F811
    _, url_a = setup(client)
    _, url_b = setup(client)
    client.post(f"{url_a}/ask", json={"question": "A 온실 질문"})
    assert client.get(f"{url_b}/questions").json() == []


def test_follow_up_gets_recent_same_hour_history(client, monkeypatch):  # noqa: F811
    # 앞 대화는 같은 정시(같은 사실 시트)의 최근 3개만 넘긴다 — 다른 정시 답의 숫자는 지금
    # 사실 시트에 없어 가드레일에 막히기 때문
    seen = []
    real = advisor_router.answer_question

    def spy(question, fact, history=None):
        seen.append([h["question"] for h in history or []])
        return real(question, fact, history=history)

    monkeypatch.setattr(advisor_router, "answer_question", spy)
    gh_id, url = setup(client)
    for i in range(5):
        client.post(f"{url}/ask", json={"question": f"질문 {i}"})
    assert seen[0] == [] and seen[1] == ["질문 0"]
    assert seen[4] == ["질문 1", "질문 2", "질문 3"]

    post(client, gh_id, m("2026-10-01T01:00:00", t=18, rh=95, co2=450))  # 다음 정시
    client.post(f"{url}/ask", json={"question": "새 정시 질문"})
    assert seen[5] == []


def test_unanswerable_ask_not_saved(client, engine):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()  # 아직 정시 값 없음 → 409
    assert client.post(f"/greenhouses/{gh['id']}/advisor/ask", json={"question": "뭐 해?"}).status_code == 409
    with Session(engine) as s:
        assert s.exec(select(AdviceQuestion)).all() == []


def test_delete_greenhouse_removes_questions(client, engine):  # noqa: F811
    gh_id, url = setup(client)
    client.post(f"{url}/ask", json={"question": "지금 뭐 해야 해?"})
    assert client.delete(f"/greenhouses/{gh_id}").status_code == 204
    with Session(engine) as s:
        assert s.exec(select(AdviceQuestion)).all() == []
