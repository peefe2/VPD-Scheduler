"""AI 어드바이저: 사실 시트 → 조치 후보 → 가드레일 (CLAUDE.md "AI 어드바이저 계약").

결정 (2026-10-31):
- 사실 시트에 이탈 예상 시각은 넣지 않는다. 예측값은 "모델 사용" 상태 지평의 값만 넣는다.
- persistence 상태(모델 사용 지평 없음)에서는 규칙 기반 안내만 한다 (LLM 미사용).
- 자유 질문 답변에도 같은 가드레일을 적용한다.
- 조치 기록에는 후보·선택·시각·사실 시트 스냅샷을 남기고, 2시간 뒤 VPD는 실측에서 붙인다.

지금은 LLM이 연결되지 않았다(`generate_with_llm`이 None). 후보는 항상 규칙으로 만들고,
LLM이 붙어도 출력은 `check_text`를 통과해야 하며 실패하면 규칙 후보로 대체한다.
자동 제어는 없다 — 후보는 사람이 판단할 "방안"일 뿐이다.
"""

import re
from dataclasses import dataclass, field

MAX_CANDIDATES = 3

# 설비별 언급 키워드. 등록되지 않은 설비가 텍스트에 나오면 가드레일이 막는다.
EQUIPMENT_KEYWORDS = {
    "vent": ["천창", "측창"],
    "exhaust_fan": ["환기팬"],
    "shade_screen": ["차광"],
    "humidifier": ["가습", "포그", "미스트"],
    "dehumidifier": ["제습"],
    "heater": ["난방", "보일러", "히터"],
}
# "환기"만 쓰면 천창·측창 또는 환기팬 중 하나라도 있어야 한다
GENERIC_VENT = "환기"

# 과장·자동 제어 표현 (CLAUDE.md "하지 말 것")
BANNED_PHRASES = ["자동으로", "자동 제어", "정확히", "정확하게", "예고", "반드시", "보장"]

NUMBER = re.compile(r"\d+(?:\.\d+)?")


# ---------------------------------------------------------------- 사실 시트

def build_fact_sheet(greenhouse, today: dict) -> dict:
    """오늘 화면 데이터(`today_payload`)에서 사실 시트를 만든다. 숫자는 표시 정밀도로 반올림."""
    latest = today["latest"]
    forecasts = [
        {
            "horizon": f["horizon"],
            "vpd": round(f["vpd"], 2),
            "band_status": f["band_status"],
            "reference": f["reference"],
        }
        for f in today["forecasts"]
        if f["source"] == "model"
    ]
    return {
        "greenhouse": {
            "name": greenhouse.name,
            "crop": greenhouse.crop,
            "band": {"low": greenhouse.vpd_low, "high": greenhouse.vpd_high},
            "equipment": list(greenhouse.equipment),
        },
        "observed_at": str(latest["hour"]),
        "current": {
            "vpd": round(latest["vpd"], 2),
            "temperature": round(latest["temperature"], 1),
            "humidity": round(latest["humidity"], 1),
            "co2": None if latest["co2"] is None else round(latest["co2"]),
            "band_status": latest["band_status"],
            "run_hours": today["run_hours"],
        },
        # "모델 사용" 지평만. persistence 값은 현재 값과 같아 근거가 되지 않는다.
        "forecasts": forecasts,
        "mode": "model" if any(not f["reference"] for f in forecasts) else "persistence",
    }


def _fact_numbers(fact: dict) -> list[float]:
    nums: list[float] = []

    def walk(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            nums.append(float(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(fact["greenhouse"]["band"])
    walk(fact["current"])
    walk(fact["forecasts"])
    return nums


# ---------------------------------------------------------------- 가드레일

@dataclass
class Check:
    passed: bool
    violations: list[str] = field(default_factory=list)


def _number_allowed(token: str, allowed: list[float]) -> bool:
    value = float(token)
    decimals = len(token.split(".")[1]) if "." in token else 0
    return any(abs(round(a, decimals) - value) < 1e-9 for a in allowed)


def check_text(text: str, fact: dict) -> Check:
    """텍스트 하나를 사실 시트·등록 설비·금지 표현에 대조한다."""
    violations = []
    allowed = _fact_numbers(fact)
    for token in NUMBER.findall(text):
        if not _number_allowed(token, allowed):
            violations.append(f"사실 시트에 없는 숫자: {token}")

    registered = set(fact["greenhouse"]["equipment"])
    for eq, words in EQUIPMENT_KEYWORDS.items():
        if eq not in registered and any(w in text for w in words):
            violations.append(f"등록되지 않은 설비: {eq}")
    if GENERIC_VENT in text.replace("환기팬", "") and not registered & {"vent", "exhaust_fan"}:
        violations.append("등록되지 않은 설비: 환기")

    for phrase in BANNED_PHRASES:
        if phrase in text:
            violations.append(f"금지 표현: {phrase}")
    return Check(not violations, violations)


def check_candidates(candidates: list[dict], fact: dict) -> Check:
    violations = []
    for c in candidates:
        if c.get("equipment") and c["equipment"] not in fact["greenhouse"]["equipment"]:
            violations.append(f"등록되지 않은 설비: {c['equipment']}")
        for key in ("title", "reason"):
            violations += check_text(c.get(key, ""), fact).violations
    return Check(not violations, violations)


# ---------------------------------------------------------------- 규칙 기반 후보
# 초안 규칙 (CLAUDE.md TODO: 재배 전문가 검토 필요). 방향만 말하고 설정값·시간은 말하지 않는다.

RAISE_VPD = [  # 대역 아래(과습): 공기를 덜 습하게
    ("dehumidifier", "제습기 가동 검토", "습도를 낮춰 VPD를 올리는 방안입니다."),
    ("heater", "난방으로 실내 온도 올리기 검토", "온도가 오르면 같은 습도에서도 VPD가 올라갑니다."),
    ("vent", "천창·측창 열기 검토", "바깥 공기가 더 건조할 때 습한 공기를 내보내는 방안입니다."),
    ("exhaust_fan", "환기팬 가동 검토", "실내 공기를 바꿔 습도를 낮추는 방안입니다."),
]
LOWER_VPD = [  # 대역 위(건조): 공기를 더 습하게, 온도 상승을 늦추기
    ("humidifier", "가습(포그·미스트) 가동 검토", "습도를 올려 VPD를 낮추는 방안입니다."),
    ("shade_screen", "차광막 치기 검토", "일사를 줄여 온도 상승을 늦추는 방안입니다."),
    ("vent", "천창·측창 열기 검토", "바깥이 더 서늘할 때 실내 온도를 낮추는 방안입니다."),
]
STATUS_KO = {"below": "대역 아래", "above": "대역 위", "in": "대역 안"}


def situation(fact: dict) -> str:
    """현재 상황 한 문장. 화면에서 후보들 위에 한 번만 보여준다."""
    cur = fact["current"]
    band = fact["greenhouse"]["band"]
    return (
        f"현재 VPD {cur['vpd']} kPa, 적정 대역 {band['low']}~{band['high']} kPa 기준 "
        f"{STATUS_KO[cur['band_status']]} 상태가 {cur['run_hours']}시간째입니다."
    )


def rule_candidates(fact: dict) -> list[dict]:
    registered = fact["greenhouse"]["equipment"]
    status = fact["current"]["band_status"]
    out: list[dict] = []

    table = RAISE_VPD if status == "below" else LOWER_VPD if status == "above" else []
    for eq, title, why in table:
        if eq in registered and len(out) < MAX_CANDIDATES - 1:
            out.append({"equipment": eq, "title": title, "reason": why})

    if status == "in":
        leaving = [f for f in fact["forecasts"] if not f["reference"] and f["band_status"] != "in"]
        if leaving:
            f = leaving[0]
            out.append({
                "equipment": None,
                "title": f"+{f['horizon']}h 예측값 확인",
                "reason": (f"모델 예측값은 +{f['horizon']}h {f['vpd']} kPa로 "
                           f"{STATUS_KO[f['band_status']]}입니다. 예측은 대역을 벗어나는 시점을 "
                           "맞히지 못할 수 있으니 실측을 보며 판단하세요."),
            })
        out.append({"equipment": None, "title": "지금 상태 유지", "reason": "적정 대역 안이라 당장 바꿀 필요는 없어 보입니다."})

    if status != "in" and not out:
        out.append({
            "equipment": None,
            "title": "쓸 수 있는 설비 확인",
            "reason": "등록된 설비 중 이 상태에 맞는 설비가 없습니다. 온실 설정에서 보유 설비를 확인하세요.",
        })
    out.append({"equipment": None, "title": "다음 정시까지 지켜보기", "reason": "조치하지 않고 다음 정시 값을 확인합니다."})
    return out[:MAX_CANDIDATES]


# ---------------------------------------------------------------- LLM 자리

def generate_with_llm(fact: dict) -> list[dict] | None:
    """LLM 연동 자리 (미연결). 연결되면 사실 시트와 등록 설비만 넘기고, 출력은 반드시
    check_candidates를 통과해야 한다. persistence 모드에서는 호출하지 않는다."""
    return None


def answer_with_llm(question: str, fact: dict) -> str | None:
    """자유 질문 LLM 연동 자리 (미연결)."""
    return None


@dataclass
class Advice:
    summary: str
    candidates: list[dict]
    source: str  # "rule" | "llm"
    check: Check
    fallback_reason: str = ""


def make_advice(fact: dict) -> Advice:
    summary = situation(fact)  # 사실 시트 값만 쓰는 고정 문장
    if fact["mode"] == "model":
        llm = generate_with_llm(fact)
        if llm is not None:
            check = check_candidates(llm, fact)
            if check.passed:
                return Advice(summary, llm[:MAX_CANDIDATES], "llm", check)
            rules = rule_candidates(fact)
            return Advice(summary, rules, "rule", check_candidates(rules, fact),
                          "AI 답변이 가드레일을 통과하지 못해 규칙 기반 안내로 대체했습니다.")
    rules = rule_candidates(fact)
    return Advice(summary, rules, "rule", check_candidates(rules, fact))


def answer_question(question: str, fact: dict) -> dict:
    llm = answer_with_llm(question, fact) if fact["mode"] == "model" else None
    if llm is not None:
        check = check_text(llm, fact)
        if check.passed:
            return {"answer": llm, "source": "llm", "violations": []}
        fallback = "AI 답변이 가드레일을 통과하지 못해 규칙 기반 안내로 대체했습니다."
        violations = check.violations
    else:
        fallback = ("AI 답변은 아직 연결되지 않았습니다." if fact["mode"] == "model"
                    else "모델이 이 온실에서 아직 검증되지 않아 규칙 기반 안내만 드립니다.")
        violations = []
    top = rule_candidates(fact)[0]
    return {"answer": f"{situation(fact)} 가능한 방안: {top['title']}. {top['reason']}", "source": "rule",
            "note": fallback, "violations": violations}
