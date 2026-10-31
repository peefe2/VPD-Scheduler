import pytest

from app import advisor
from app.advisor import check_candidates, check_text, make_advice, rule_candidates
from tests.test_api import GREENHOUSE, client, engine  # noqa: F401  fixture 재사용
from tests.test_today import m, post


def fact(status="below", vpd=0.32, run=5, equipment=("dehumidifier", "heater", "vent"), forecasts=(), mode=None):
    fc = [dict(f) for f in forecasts]
    return {
        "greenhouse": {"name": "1동", "crop": "토마토", "band": {"low": 0.5, "high": 1.5}, "equipment": list(equipment)},
        "observed_at": "2026-10-01 10:00:00",
        "current": {"vpd": vpd, "temperature": 18.2, "humidity": 91.5, "co2": 450,
                    "band_status": status, "run_hours": run},
        "forecasts": fc,
        "mode": mode or ("model" if any(not f["reference"] for f in fc) else "persistence"),
    }


# ---------------------------------------------------------------- 가드레일

def test_numbers_must_come_from_fact_sheet():
    f = fact()
    assert check_text("현재 VPD 0.32 kPa, 5시간째", f).passed
    assert check_text("VPD 0.3 근처", f).passed  # 사실 값을 반올림한 표현은 허용
    bad = check_text("습도를 80%로 낮추세요", f)
    assert not bad.passed and "사실 시트에 없는 숫자: 80" in bad.violations


def test_unregistered_equipment_blocked():
    f = fact(equipment=["heater"])
    assert not check_text("제습기를 켜는 방안", f).passed
    assert not check_text("환기를 검토하세요", f).passed  # 천창·측창도 환기팬도 없음
    assert check_text("난방으로 온도를 올리는 방안", f).passed
    f2 = fact(equipment=["exhaust_fan"])
    assert check_text("환기팬 가동 검토", f2).passed


def test_banned_phrases_blocked():
    f = fact()
    for text in ("자동으로 제어합니다", "이탈을 정확히 예측합니다", "AI가 이탈을 예고합니다"):
        assert not check_text(text, f).passed


def test_garbled_text_blocked():
    # gemini-3.5-flash-lite가 실제로 낸 깨진 출력 (2026-11-01)
    f = fact(status="in", vpd=0.9)
    for text in ("怄木 ㅇㅈㅈ", "怨案 ㅇㅈㅈ 怨案 ㅇㅈㅈ.", "怄數 지켜보기", "ㅇㅈㅈ 지켜보기", "現在 상태 유지"):
        res = check_text(text, f)
        assert not res.passed and "깨진 글자" in res.violations[0], text
    assert check_text("천창·측창 열기 검토 → 지켜보기", f).passed


def test_candidate_equipment_field_checked():
    f = fact(equipment=["heater"])
    res = check_candidates([{"equipment": "humidifier", "title": "검토", "reason": "방안"}], f)
    assert not res.passed


# ---------------------------------------------------------------- 규칙 후보

def test_below_uses_registered_raising_equipment_only():
    cands = rule_candidates(fact("below", equipment=["humidifier", "heater", "vent"]))
    assert len(cands) == 3
    assert [c["equipment"] for c in cands] == ["heater", "vent", None]
    assert all(c["equipment"] != "humidifier" for c in cands)  # 과습인데 가습은 권하지 않음
    assert cands[-1]["title"] == "다음 정시까지 지켜보기"


def test_above_uses_lowering_equipment():
    cands = rule_candidates(fact("above", vpd=1.8, equipment=["humidifier", "shade_screen", "dehumidifier"]))
    assert [c["equipment"] for c in cands] == ["humidifier", "shade_screen", None]


def test_no_matching_equipment_points_to_settings():
    cands = rule_candidates(fact("below", equipment=["humidifier"]))
    assert cands[0]["title"] == "쓸 수 있는 설비 확인"


def test_in_band_mentions_model_forecast_only_when_leaving():
    leaving = [{"horizon": 3, "vpd": 0.41, "band_status": "below", "reference": False}]
    cands = rule_candidates(fact("in", vpd=0.8, forecasts=leaving))
    assert cands[0]["title"] == "+3h 예측값 확인"
    assert "맞히지 못할 수 있" in cands[0]["reason"]
    assert rule_candidates(fact("in", vpd=0.8))[0]["title"] == "지금 상태 유지"


@pytest.mark.parametrize("status,vpd", [("below", 0.32), ("above", 1.8), ("in", 0.8)])
def test_rule_candidates_always_pass_guardrail(status, vpd):
    f = fact(status, vpd=vpd, equipment=[e for e in advisor.EQUIPMENT_KEYWORDS])
    assert check_candidates(rule_candidates(f), f).passed
    assert check_text(advisor.situation(f), f).passed


# ---------------------------------------------------------------- LLM 자리

MODEL_FC = [{"horizon": 1, "vpd": 0.35, "band_status": "below", "reference": False}]


def test_llm_output_failing_guardrail_falls_back(monkeypatch):
    monkeypatch.setattr(advisor, "generate_with_llm",
                        lambda f: [{"equipment": "heater", "title": "난방 22도로", "reason": "자동으로 맞춥니다"}])
    adv = make_advice(fact(forecasts=MODEL_FC))
    assert adv.source == "rule" and adv.fallback_reason and adv.check.passed


def test_llm_not_called_in_persistence_mode(monkeypatch):
    def boom(f):
        raise AssertionError("persistence 모드에서 LLM 호출")
    monkeypatch.setattr(advisor, "generate_with_llm", boom)
    assert make_advice(fact()).source == "rule"


def test_llm_output_passing_guardrail_used(monkeypatch):
    good = [{"equipment": "heater", "title": "난방 검토", "reason": "현재 VPD 0.32 kPa입니다."}]
    monkeypatch.setattr(advisor, "generate_with_llm", lambda f: good)
    assert make_advice(fact(forecasts=MODEL_FC)).source == "llm"


# ---------------------------------------------------------------- API

API_GH = {**GREENHOUSE, "connection_type": "api", "equipment": ["heater", "vent", "humidifier"]}


def test_advisor_unavailable_for_csv_and_empty(client):  # noqa: F811
    csv_gh = client.post("/greenhouses", json=GREENHOUSE).json()
    assert client.get(f"/greenhouses/{csv_gh['id']}/advisor").json()["available"] is False
    api_gh = client.post("/greenhouses", json=API_GH).json()
    body = client.get(f"/greenhouses/{api_gh['id']}/advisor").json()
    assert body["available"] is False and "정시 값" in body["reason"]
    assert client.post(f"/greenhouses/{csv_gh['id']}/advisor/ask", json={"question": "어때?"}).status_code == 409


def test_advice_saved_per_hour_and_decisions_logged(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    # 습도 95%: 대역 아래(과습)
    post(client, gh["id"], *[m(f"2026-10-01T{h:02d}:00:00", t=18, rh=95, co2=450) for h in range(4)])
    url = f"/greenhouses/{gh['id']}/advisor"
    body = client.get(url).json()
    assert body["available"] and body["mode"] == "persistence" and body["source"] == "rule"
    assert "대역 아래" in body["summary"] and "4시간째" in body["summary"]
    assert body["fact_sheet"]["forecasts"] == []  # 모델 사용 지평이 없으면 예측을 넣지 않음
    assert "onset" not in str(body["fact_sheet"]) and body["guardrail"]["passed"]
    assert [c["equipment"] for c in body["candidates"]] == ["heater", "vent", None]
    advice_id = body["advice_id"]

    res = client.post(f"{url}/{advice_id}/decisions", json={"candidate_index": 0, "decision": "done"})
    assert res.json()["decisions"] == {"0": "done"}
    client.post(f"{url}/{advice_id}/decisions", json={"candidate_index": 2, "decision": "skipped"})
    assert client.get(url).json()["advice_id"] == advice_id  # 같은 정시면 같은 기록

    logs = client.get(f"{url}/logs").json()
    assert [(r["title"], r["decision"]) for r in logs][0] == (body["candidates"][0]["title"], "done")
    assert logs[0]["vpd_after_2h"] is None  # 05시 값이 아직 없음

    post(client, gh["id"], m("2026-10-01T04:00:00", t=18, rh=95, co2=450),
         m("2026-10-01T05:00:00", t=24, rh=70, co2=450))
    logs = client.get(f"{url}/logs").json()
    assert logs[0]["vpd_after_2h"] is not None and logs[0]["status_after_2h"] == "in"

    # 다음 정시엔 새 추천 기록
    assert client.get(url).json()["advice_id"] != advice_id

    # 취소
    client.post(f"{url}/{advice_id}/decisions", json={"candidate_index": 0, "decision": None})
    assert all(r["decision"] != "done" or r["advice_id"] != advice_id for r in client.get(f"{url}/logs").json())


def test_decision_validation(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", co2=450))
    advice_id = client.get(f"/greenhouses/{gh['id']}/advisor").json()["advice_id"]
    url = f"/greenhouses/{gh['id']}/advisor/{advice_id}/decisions"
    assert client.post(url, json={"candidate_index": 9, "decision": "done"}).status_code == 422
    assert client.post(url, json={"candidate_index": 0, "decision": "launch"}).status_code == 422
    other = client.post("/greenhouses", json=API_GH).json()
    assert client.post(f"/greenhouses/{other['id']}/advisor/{advice_id}/decisions",
                       json={"candidate_index": 0, "decision": "done"}).status_code == 404


def test_ask_returns_rule_answer_without_llm(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", t=18, rh=95, co2=450))
    body = client.post(f"/greenhouses/{gh['id']}/advisor/ask", json={"question": "지금 뭐 해야 해?"}).json()
    assert body["source"] == "rule" and "규칙 기반" in body["note"]


def test_delete_greenhouse_removes_advice(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", co2=450))
    advice_id = client.get(f"/greenhouses/{gh['id']}/advisor").json()["advice_id"]
    client.post(f"/greenhouses/{gh['id']}/advisor/{advice_id}/decisions", json={"candidate_index": 0, "decision": "done"})
    assert client.delete(f"/greenhouses/{gh['id']}").status_code == 204
