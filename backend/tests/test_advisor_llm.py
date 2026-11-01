"""Gemini 연동: 실제 API는 부르지 않고 가짜 클라이언트로 확인한다."""

import json
from types import SimpleNamespace

import httpx
from sqlalchemy import inspect, text
from sqlmodel import create_engine

from app import advisor
from app.advisor import Advice, Check, answer_question, generate_with_llm, make_advice
from app.db import ensure_columns
from app.routers import advisor as advisor_router
from tests.test_advisor import API_GH, MODEL_FC, fact
from tests.test_api import client, engine  # noqa: F401  fixture 재사용
from tests.test_today import m, post

GOOD = {"candidates": [{"equipment": "heater", "title": "난방 검토", "reason": "현재 VPD 0.32 kPa입니다."}]}


class FakeInteractions:
    def __init__(self, output_text="", status="completed", error=None):
        self.output_text, self.status, self.error = output_text, status, error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        error = self.error.pop(0) if isinstance(self.error, list) else self.error
        if error:
            raise error
        # 목록이면 부를 때마다 다음 답 (재질문 확인용)
        text = self.output_text.pop(0) if isinstance(self.output_text, list) else self.output_text
        return SimpleNamespace(status=self.status, output_text=text)


def use_fake(monkeypatch, **kw) -> FakeInteractions:
    fake = FakeInteractions(**kw)
    monkeypatch.setattr(advisor, "llm_client", lambda: SimpleNamespace(interactions=fake))
    return fake


# ---------------------------------------------------------------- 켜기·끄기

def test_llm_off_unless_env_set(monkeypatch):
    monkeypatch.delenv("VPD_ADVISOR_LLM", raising=False)
    assert advisor.llm_client() is None
    assert generate_with_llm(fact(forecasts=MODEL_FC)) is None
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "rule" and adv.fallback_reason == ""


# ---------------------------------------------------------------- 조치 후보

def test_candidates_from_gemini_used(monkeypatch):
    fake = use_fake(monkeypatch, output_text=json.dumps(GOOD, ensure_ascii=False))
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "llm" and adv.candidates == GOOD["candidates"]
    (call,) = fake.calls
    assert call["model"] == advisor.DEFAULT_MODEL
    assert "사실 시트" in call["system_instruction"]
    assert json.loads(call["input"])["current"]["vpd"] == 0.32  # 사실 시트만 넘긴다
    assert call["response_format"]["mime_type"] == "application/json"


def test_model_overridable_by_env(monkeypatch):
    monkeypatch.setenv("VPD_ADVISOR_MODEL", "gemini-test")
    fake = use_fake(monkeypatch, output_text=json.dumps(GOOD))
    generate_with_llm(fact(forecasts=MODEL_FC))
    assert fake.calls[0]["model"] == "gemini-test"


def test_candidates_capped_at_three(monkeypatch):
    many = {"candidates": GOOD["candidates"] * 5}
    use_fake(monkeypatch, output_text=json.dumps(many))
    assert len(generate_with_llm(fact(forecasts=MODEL_FC))) == advisor.MAX_CANDIDATES


def test_api_error_falls_back_with_reason(monkeypatch):
    use_fake(monkeypatch, error=httpx.ReadTimeout("timed out"))
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "rule" and "AI 응답을 받지 못해" in adv.fallback_reason


class SdkInternalError(Exception):
    """Interactions API는 google.genai.errors가 아닌 비공개 모듈의 예외를 던진다 (2.34.0 확인)."""


def test_sdk_internal_error_falls_back(monkeypatch):
    use_fake(monkeypatch, error=SdkInternalError("400 API key not valid"))
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "rule" and "AI 응답을 받지 못해" in adv.fallback_reason


def test_bad_json_falls_back(monkeypatch):
    use_fake(monkeypatch, output_text='{"candidates": [{"title": 1}]')
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "rule" and "AI 응답을 받지 못해" in adv.fallback_reason


def test_unfinished_interaction_falls_back(monkeypatch):
    use_fake(monkeypatch, output_text=json.dumps(GOOD), status="failed")
    assert make_advice(fact(forecasts=MODEL_FC)).source == "rule"


def test_gemini_output_failing_guardrail_falls_back(monkeypatch):
    bad = {"candidates": [{"equipment": "heater", "title": "난방 22도로", "reason": "자동으로 맞춥니다"}]}
    use_fake(monkeypatch, output_text=json.dumps(bad, ensure_ascii=False))
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "rule" and "가드레일" in adv.fallback_reason


# ---------------------------------------------------------------- 자유 질문

def test_answer_from_gemini(monkeypatch):
    fake = use_fake(monkeypatch, output_text="현재 VPD 0.32 kPa로 대역 아래입니다. 난방을 검토해 보세요.")
    body = answer_question("지금 뭐 해야 해?", fact(forecasts=MODEL_FC))
    assert body["source"] == "llm" and "난방" in body["answer"]
    assert "지금 뭐 해야 해?" in fake.calls[0]["input"]
    assert "response_format" not in fake.calls[0]


def test_answer_input_names_registered_equipment_in_korean(monkeypatch):
    # 실제 답변이 "사실 시트"를 그대로 쓰고, 등록 안 된 환기팬·차광막을 꺼내 막혔다 (2026-11-01)
    fake = use_fake(monkeypatch, output_text="방안입니다.")
    answer_question("환기해도 돼?", fact(equipment=("vent", "heater"), forecasts=MODEL_FC))
    sent = fake.calls[0]["input"]
    assert "사실 시트" not in sent
    assert "지금 권할 수 있는 설비: 천창·측창, 난방" in sent  # 대역 아래: 둘 다 올리는 쪽
    assert "환기팬" not in sent and "차광막" not in sent


# ---------------------------------------------------------------- 필요한 방향 알려주기
# 평가(2026-11-01)에서 곧 대역 위로 갈 때 "난방"을 권했다 — 난방은 VPD를 더 올린다

UP_FC = [{"horizon": 1, "vpd": 1.62, "band_status": "above", "reference": False}]


def sent_input(monkeypatch, f) -> str:
    fake = use_fake(monkeypatch, output_text="방안입니다.")
    answer_question("뭐 해야 해?", f)
    return fake.calls[0]["input"]


def lines_of(sent: str) -> dict[str, str]:
    return dict(x.split(": ", 1) for x in sent.splitlines() if x.startswith(("지금 필요한 방향", "지금 권할 수 있는 설비",
                                                                          "방향이 맞지 않아 권하지 않는 설비", "등록된 설비")))


def test_answer_input_says_lower_when_forecast_leaves_upward(monkeypatch):
    sent = sent_input(monkeypatch, fact(status="in", vpd=1.35, equipment=("vent", "exhaust_fan", "heater"),
                                        forecasts=UP_FC))
    got = lines_of(sent)
    assert got["지금 필요한 방향"].startswith("VPD를 내리는 쪽")
    assert got["지금 권할 수 있는 설비"] == "천창·측창"
    assert got["방향이 맞지 않아 권하지 않는 설비"] == "환기팬, 난방"
    assert "등록된 설비" not in got  # 전체 목록을 주면 답이 그대로 나열했다


def test_answer_input_says_raise_when_below(monkeypatch):
    sent = sent_input(monkeypatch, fact(status="below", equipment=("vent", "heater", "humidifier"),
                                        forecasts=MODEL_FC))
    got = lines_of(sent)
    assert got["지금 필요한 방향"].startswith("VPD를 올리는 쪽")
    assert got["지금 권할 수 있는 설비"] == "천창·측창, 난방"
    assert got["방향이 맞지 않아 권하지 않는 설비"] == "가습"


def test_answer_input_says_watch_when_in_band_and_staying(monkeypatch):
    stay = [{"horizon": 1, "vpd": 1.2, "band_status": "in", "reference": False}]
    got = lines_of(sent_input(monkeypatch, fact(status="in", vpd=1.1, forecasts=stay)))
    assert "지켜보기" in got["지금 필요한 방향"]
    assert "지금 권할 수 있는 설비" not in got and got["등록된 설비"].startswith("제습기, 난방, 천창·측창")


# ---------------------------------------------------------------- 후속 질문 (앞 대화 전달)

def test_follow_up_sends_previous_turns_in_order(monkeypatch):
    fake = use_fake(monkeypatch, output_text="난방을 검토하는 방안입니다.")
    history = [{"question": "지금 뭐 해야 해?", "answer": "제습기를 검토하는 방안입니다."},
               {"question": "왜?", "answer": "대역 아래라서입니다."}]
    answer_question("그럼 난방은?", fact(forecasts=MODEL_FC), history=history)
    sent = fake.calls[0]["input"]
    order = ["지금 뭐 해야 해?", "제습기를 검토하는 방안입니다.", "왜?", "대역 아래라서입니다.", "질문: 그럼 난방은?"]
    assert [sent.index(x) for x in order] == sorted(sent.index(x) for x in order)


def test_no_history_means_no_previous_section(monkeypatch):
    fake = use_fake(monkeypatch, output_text="방안입니다.")
    answer_question("지금 뭐 해야 해?", fact(forecasts=MODEL_FC))
    assert "이전 대화" not in fake.calls[0]["input"]


# ---------------------------------------------------------------- 미등록 설비 질문

def test_question_about_unregistered_equipment_answered_without_llm(monkeypatch):
    fake = use_fake(monkeypatch, output_text="방안입니다.")
    body = answer_question("차광막 쳐야 해?", fact(equipment=("vent", "heater"), forecasts=MODEL_FC))
    assert not fake.calls
    assert body["source"] == "rule" and body["note"] == advisor.UNREGISTERED_NOTE
    assert "차광막" in body["answer"] and "온실 설정" in body["answer"]


def test_unregistered_shortcut_also_without_llm_or_model():
    body = answer_question("가습기 틀어도 돼?", fact(equipment=("heater",)))  # persistence, LLM 꺼짐
    assert body["note"] == advisor.UNREGISTERED_NOTE and "가습" in body["answer"]


def test_generic_vent_question_needs_some_vent_equipment(monkeypatch):
    fake = use_fake(monkeypatch, output_text="방안입니다.")
    assert answer_question("환기해도 돼?", fact(equipment=("heater",), forecasts=MODEL_FC))["note"] \
        == advisor.UNREGISTERED_NOTE
    assert answer_question("환기팬 켤까?", fact(equipment=("vent",), forecasts=MODEL_FC))["note"] \
        == advisor.UNREGISTERED_NOTE
    assert not fake.calls
    answer_question("환기해도 돼?", fact(equipment=("vent",), forecasts=MODEL_FC))
    assert len(fake.calls) == 1  # 천창·측창이 있으면 Gemini에 묻는다


def test_question_mixing_registered_equipment_goes_to_llm(monkeypatch):
    fake = use_fake(monkeypatch, output_text="난방을 검토하는 방안입니다.")
    body = answer_question("차광막 대신 난방은?", fact(equipment=("heater",), forecasts=MODEL_FC))
    assert len(fake.calls) == 1 and body["source"] == "llm"


# ---------------------------------------------------------------- 가드레일 실패 시 재질문

def test_answer_passing_first_time_asks_once(monkeypatch):
    fake = use_fake(monkeypatch, output_text="난방을 검토하는 방안입니다.")
    answer_question("어떻게 해?", fact(forecasts=MODEL_FC))
    assert len(fake.calls) == 1


def test_answer_retried_once_with_violation_feedback(monkeypatch):
    fake = use_fake(monkeypatch, output_text=["습도를 60%로 낮추세요.", "제습기를 검토하는 방안입니다."])
    body = answer_question("어떻게 해?", fact(forecasts=MODEL_FC))
    assert body["source"] == "llm" and body["answer"] == "제습기를 검토하는 방안입니다."
    assert len(fake.calls) == 2
    retry = fake.calls[1]["input"]
    assert "어떻게 해?" in retry and "60" in retry and "사실 시트에 없는 숫자" in retry


def test_answer_failing_twice_falls_back_with_last_violations(monkeypatch):
    fake = use_fake(monkeypatch, output_text=["습도를 60%로 낮추세요.", "자동으로 맞춥니다."])
    body = answer_question("어떻게 해?", fact(forecasts=MODEL_FC))
    assert len(fake.calls) == 2  # 재질문은 한 번만
    assert body["source"] == "rule" and body["violations"] == ["금지 표현: 자동으로"]


def test_retry_call_failing_falls_back(monkeypatch):
    use_fake(monkeypatch, output_text=["습도를 60%로 낮추세요.", ""], error=[None, httpx.ReadTimeout("t")])
    body = answer_question("어떻게 해?", fact(forecasts=MODEL_FC))
    assert body["source"] == "rule" and "가드레일" in body["note"]


def test_answer_failing_guardrail_falls_back(monkeypatch):
    use_fake(monkeypatch, output_text="습도를 60%로 반드시 낮추세요.")
    body = answer_question("어떻게 해?", fact(forecasts=MODEL_FC))
    assert body["source"] == "rule" and body["violations"]


def test_answer_api_error_falls_back(monkeypatch):
    use_fake(monkeypatch, error=httpx.ConnectError("down"))
    body = answer_question("어떻게 해?", fact(forecasts=MODEL_FC))
    assert body["source"] == "rule" and "AI 응답을 받지 못해" in body["note"]


# ---------------------------------------------------------------- 호출 횟수 · 기록

def counting_make_advice(monkeypatch, fallback_reason=""):
    calls = []

    def fake(f):
        calls.append(f)
        rules = advisor.rule_candidates(f)
        return Advice(advisor.situation(f), rules, "rule", Check(True), fallback_reason)

    monkeypatch.setattr(advisor_router, "make_advice", fake)
    return calls


def test_advice_not_regenerated_within_same_hour(client, monkeypatch):  # noqa: F811
    calls = counting_make_advice(monkeypatch)
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", t=18, rh=95, co2=450))
    url = f"/greenhouses/{gh['id']}/advisor"
    first = client.get(url).json()
    client.get(url)
    assert len(calls) == 1  # 1분마다 새로고침해도 다시 만들지 않는다

    # 선택 전에 설비가 바뀌면 사실 시트가 달라져 다시 만든다
    client.patch(f"/greenhouses/{gh['id']}", json={"equipment": ["heater"]})
    assert client.get(url).json()["advice_id"] == first["advice_id"]
    assert len(calls) == 2

    # 선택한 뒤에는 기록을 고정한다
    client.post(f"{url}/{first['advice_id']}/decisions", json={"candidate_index": 0, "decision": "done"})
    client.patch(f"/greenhouses/{gh['id']}", json={"equipment": ["heater", "vent"]})
    client.get(url)
    assert len(calls) == 2


def test_fallback_reason_survives_reload(client, monkeypatch):  # noqa: F811
    counting_make_advice(monkeypatch, fallback_reason="AI 응답을 받지 못해 규칙 기반 안내로 대체했습니다.")
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", t=18, rh=95, co2=450))
    url = f"/greenhouses/{gh['id']}/advisor"
    client.get(url)
    assert "AI 응답을 받지 못해" in client.get(url).json()["guardrail"]["fallback_reason"]


# ---------------------------------------------------------------- 기존 DB

def test_ensure_columns_adds_guardrail_to_old_db(tmp_path):
    old = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE advicerecord (id INTEGER PRIMARY KEY, greenhouse_id INTEGER, "
                          "hour DATETIME, created_at DATETIME, source VARCHAR, candidates JSON, fact_sheet JSON)"))
    ensure_columns(old)
    ensure_columns(old)  # 두 번 불러도 안전
    assert "guardrail" in {c["name"] for c in inspect(old).get_columns("advicerecord")}
