"""AI 어드바이저: 사실 시트 → 조치 후보 → 가드레일 (CLAUDE.md "AI 어드바이저 계약").

결정 (2026-10-31):
- 사실 시트에 이탈 예상 시각은 넣지 않는다. 예측값은 "모델 사용" 상태 지평의 값만 넣는다.
  +6h는 오늘 화면에서 빠져 사실 시트에도 없다 (결정 2026-11-07).
- persistence 상태(모델 사용 지평 없음)에서는 규칙 기반 안내만 한다 (LLM 미사용).
- 자유 질문 답변에도 같은 가드레일을 적용한다.
- 조치 기록에는 후보·선택·시각·사실 시트 스냅샷을 남기고, 2시간 뒤 VPD는 실측에서 붙인다.

LLM은 Gemini (결정 2026-10-31, 무료 등급). 기본은 꺼져 있고 `VPD_ADVISOR_LLM=1`일 때만 부른다.
LLM 출력은 가드레일을 통과해야 쓰이고, 호출 실패나 위반이면 규칙 후보로 대체한다.
자동 제어는 없다 — 후보는 사람이 판단할 "방안"일 뿐이다.
"""

import json
import os
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

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
EQUIPMENT_KO = {"vent": "천창·측창", "exhaust_fan": "환기팬", "shade_screen": "차광막",
                "humidifier": "가습", "dehumidifier": "제습기", "heater": "난방"}
# "환기"만 쓰면 천창·측창 또는 환기팬 중 하나라도 있어야 한다
GENERIC_VENT = "환기"

# 과장·자동 제어 표현 (CLAUDE.md "하지 말 것")
BANNED_PHRASES = ["자동으로", "자동 제어", "정확히", "정확하게", "예고", "반드시", "보장"]

NUMBER = re.compile(r"\d+(?:\.\d+)?")
# 한자·가나·낱자 자모(ㅇㅈㅈ). 작은 모델이 가끔 이런 깨진 글자를 섞어 낸다 (2026-11-01 실측)
GARBLED = re.compile(r"[\u3131-\u318e\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
# \uc0ac\uc6a9\uc790\uc5d0\uac8c \ubcf4\uc774\uba74 \uc548 \ub418\ub294 \ub0b4\ubd80 \uc6a9\uc5b4: \uc0ac\uc2e4 \uc2dc\ud2b8\u00b7JSON \ud544\ub4dc\uba85\u00b7\uc124\ube44 \ucf54\ub4dc (Gemini \uc2e4\uc81c \ub2f5\ubcc0\uc5d0\uc11c \ub098\uc634)
INTERNAL_FIELDS = ["band_status", "forecasts", "run_hours", "observed_at", "greenhouse", "equipment"]
INTERNAL_TERM = re.compile(
    r"\uc0ac\uc2e4 ?\uc2dc\ud2b8|JSON|(?<![A-Za-z_])(?:" + "|".join(INTERNAL_FIELDS + list(EQUIPMENT_KEYWORDS)) + r")(?![A-Za-z_])"
)


# ---------------------------------------------------------------- 사실 시트

def build_fact_sheet(greenhouse, today: dict) -> dict:
    """오늘 화면 데이터(`today_payload`)에서 사실 시트를 만든다. 숫자는 표시 정밀도로 반올림."""
    latest = today["latest"]
    forecasts = [
        {
            "horizon": f["horizon"],
            "vpd": round(f["vpd"], 2),
            "band_status": f["band_status"],
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
        "mode": "model" if forecasts else "persistence",
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
    if GARBLED.search(text):
        violations.insert(0, "깨진 글자")
    if m := INTERNAL_TERM.search(text):
        violations.append(f"내부 용어: {m.group()}")
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
        leaving = [f for f in fact["forecasts"] if f["band_status"] != "in"]
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


# ---------------------------------------------------------------- LLM (Gemini)
# 비용·키 없이도 서비스가 완결되도록 기본은 꺼져 있다. VPD_ADVISOR_LLM=1이고 GEMINI_API_KEY가
# 있을 때만 부른다. 실패(키·네트워크·타임아웃·형식)는 모두 LLMError → 규칙 기반 안내로 대체.

LLM_ENV = "VPD_ADVISOR_LLM"
MODEL_ENV = "VPD_ADVISOR_MODEL"
# 무료 등급 모델. gemini-3.8-flash는 구조화 출력에서 90초 넘게 걸려 시간 초과 (2026-11-01 실측,
# flash-lite는 약 4초)
DEFAULT_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_SECONDS = 20.0
LLM_FAILED = "AI 응답을 받지 못해 규칙 기반 안내로 대체했습니다."
GUARDRAIL_FAILED = "AI 답변이 가드레일을 통과하지 못해 규칙 기반 안내로 대체했습니다."
UNREGISTERED_NOTE = "등록되지 않은 설비에 대한 질문이라 AI에 묻지 않았습니다."

CONTRACT = """\
너는 스마트팜 온실의 VPD(수증기압차) 관리 도우미다. 입력은 서버가 계산한 "사실 시트" JSON이다.
반드시 지킬 것:
- 숫자는 사실 시트에 있는 값만 쓴다. 습도·온도 목표값, 설정값, 시간, 횟수 같은 새 숫자를 만들지 않는다.
- 설비는 사실 시트 greenhouse.equipment에 등록된 것만 언급한다. 코드값 뜻: vent=천창·측창,
  exhaust_fan=환기팬, shade_screen=차광막, humidifier=가습, dehumidifier=제습기, heater=난방.
  등록되지 않은 설비는 이름도 꺼내지 않는다.
- current.band_status 뜻: below=대역 아래(VPD가 낮음, 과습 쪽), above=대역 위(VPD가 높음, 건조 쪽),
  in=대역 안. in이면 지켜보기를 먼저 권하고, forecasts에서 대역을 벗어나는 지평이 있을 때만
  그 방향의 조치를 검토 방안으로 낸다. 사실 시트에 없는 상태(습도가 높다 등)를 지어내지 않는다.
- VPD가 대역을 벗어나는 시각이나 시점을 예측하거나 단정하지 않는다.
- 다음 표현은 쓰지 않는다: 자동으로, 자동 제어, 정확히, 정확하게, 예고, 반드시, 보장.
- 너는 설비를 제어하지 않는다. 사람이 판단할 "방안"으로만 말한다.
- 읽는 사람은 농가다. "사실 시트", JSON, 필드명, 영문 설비 코드는 쓰지 않는다. 설비는 위의 한글
  이름으로, 근거는 "지금 측정값"처럼 말한다.
- 한국어로, 짧고 쉽게 쓴다."""

CANDIDATES_PROMPT = CONTRACT + """
지금 상황에서 사람이 검토할 조치 후보를 1~3개 고른다. equipment는 등록된 설비 코드 하나 또는
설비가 필요 없는 후보(지켜보기 등)면 null. title은 20자 안팎, reason은 한두 문장."""

ANSWER_PROMPT = CONTRACT + """
사용자 질문에 사실 시트만 근거로 2~4문장으로 답한다.
- 등록된 설비에 대한 질문이면, 지금 대역 상태에서 그 설비가 VPD를 어느 쪽으로 움직이는지 말하고
  검토할 방안으로 답한다. 예: 대역 아래(과습)에서 천창·측창은 바깥 공기가 더 건조할 때 습한 공기를
  내보내 VPD를 올리는 방안이다. 판단에 바깥 날씨처럼 측정값에 없는 정보가 필요하면 그걸 확인해
  보라고 말한다.
- 등록되지 않은 설비를 물으면 그 이름을 다시 쓰지 말고, 등록된 설비 안에서만 안내한다고 말한다.
- 측정값으로 답할 수 없는 질문이면 지금 측정값으로는 판단하기 어렵다고 말한다."""


class LLMCandidate(BaseModel):
    equipment: str | None
    title: str
    reason: str


class LLMCandidates(BaseModel):
    candidates: list[LLMCandidate]


class LLMError(Exception):
    """LLM을 불렀지만 쓸 수 있는 답을 받지 못함."""


def llm_client():
    """켜져 있으면 Gemini 클라이언트, 아니면 None. 키는 GEMINI_API_KEY 환경변수에서 읽는다."""
    if os.environ.get(LLM_ENV) != "1":
        return None
    from google import genai

    try:
        return genai.Client()
    except ValueError as e:  # 키 없음
        raise LLMError(str(e)) from e


def _ask_gemini(client, system: str, user: str, schema: dict | None = None) -> str:
    extra = {"response_format": {"type": "text", "mime_type": "application/json", "schema": schema}} if schema else {}
    try:
        result = client.interactions.create(
            model=os.environ.get(MODEL_ENV, DEFAULT_MODEL),
            system_instruction=system,
            input=user,
            timeout=TIMEOUT_SECONDS,
            **extra,
        )
    # Interactions API는 google.genai.errors가 아니라 비공개 모듈(google.genai._gaos)의 예외를
    # 던진다 (2.34.0). 비공개 경로를 import하면 SDK 업데이트 때 앱이 뜨지 않을 수 있어서, SDK
    # 호출에서 나는 예외는 모두 규칙 기반 대체로 돌린다 — LLM은 없어도 되는 부가 기능이다.
    except Exception as e:
        raise LLMError(str(e)) from e
    if result.status != "completed" or not result.output_text:
        raise LLMError(f"interaction status {result.status}")
    return result.output_text


def generate_with_llm(fact: dict) -> list[dict] | None:
    """사실 시트와 필요한 방향(direction_lines)을 넘겨 후보를 받는다. 꺼져 있으면 None. 출력은
    make_advice에서 check_candidates를 통과해야 쓰인다. persistence 모드에서는 호출하지 않는다."""
    client = llm_client()
    if client is None:
        return None
    text = _ask_gemini(client, CANDIDATES_PROMPT, _llm_input(fact), LLMCandidates.model_json_schema())
    try:
        parsed = LLMCandidates.model_validate_json(text)
    except ValidationError as e:
        raise LLMError(str(e)) from e
    return [c.model_dump() for c in parsed.candidates][:MAX_CANDIDATES]


def direction_lines(fact: dict) -> list[str]:
    """지금 VPD를 어느 쪽으로 움직여야 하는지와, 그 방향에 맞는/맞지 않는 등록 설비 (규칙 후보와 같은 표).
    대역 안이면 모델 예측이 대역을 벗어나는 방향을 따른다. 등록 설비 전체 목록을 주면
    작은 모델이 방향과 상관없이 그대로 나열했다 (평가 2026-11-01: 대역 위로 갈 때 난방 권함)."""
    registered = fact["greenhouse"]["equipment"]
    status = fact["current"]["band_status"]
    if status == "in":
        leaving = [f for f in fact["forecasts"] if f["band_status"] != "in"]
        if not leaving:
            names = ", ".join(EQUIPMENT_KO[e] for e in registered) or "없음"
            return ["지금 필요한 방향: 없음(대역 안이고 예측도 대역 안). 설비 조치보다 지켜보기를 먼저 권한다.",
                    f"등록된 설비: {names}"]
        status = leaving[0]["band_status"]
    word, table = ("올리는", RAISE_VPD) if status == "below" else ("내리는", LOWER_VPD)
    fitting = {eq for eq, _, _ in table}
    fits = [EQUIPMENT_KO[e] for e in registered if e in fitting]
    others = [EQUIPMENT_KO[e] for e in registered if e not in fitting]
    lines = [f"지금 필요한 방향: VPD를 {word} 쪽.", f"지금 권할 수 있는 설비: {', '.join(fits) or '없음'}"]
    if others:
        lines.append(f"방향이 맞지 않아 권하지 않는 설비: {', '.join(others)}")
    return lines


def _llm_input(fact: dict) -> str:
    """조치 후보·자유 질문 공통 입력. 작은 모델은 시스템 프롬프트보다 이 메시지를 더 따른다: 설비를
    한글로, 방향별로 못박고, "사실 시트"라는 말은 넣지 않는다 (답변에 그대로 따라 나왔다).
    후보 입력에 방향이 없을 때는 +6h 참고값을 근거처럼 쓴 사례가 있었다 (2026-11-01)."""
    guide = "\n".join(direction_lines(fact) + ["등록되지 않은 설비는 이름도 쓰지 않는다."])
    return f"지금 측정값:\n{json.dumps(fact, ensure_ascii=False)}\n\n{guide}"


def answer_with_llm(question: str, fact: dict, rejected: tuple[str, list[str]] | None = None,
                    history: list[dict] | None = None) -> str | None:
    """자유 질문 답변. 꺼져 있으면 None. 출력은 check_text를 통과해야 쓰인다.
    rejected = (가드레일에 막힌 이전 답, 위반 목록)이면 그 이유를 알려주고 다시 묻는다.
    history = 같은 정시의 앞 대화 [{question, answer}] (오래된 것부터) — "그럼 난방은?" 같은 후속 질문용."""
    client = llm_client()
    if client is None:
        return None
    user = _llm_input(fact) + "\n\n"
    if history:
        turns = "\n".join(f"사용자: {h['question']}\n도우미: {h['answer']}" for h in history)
        # 앞 답의 상황 설명("VPD는 0.28로 대역 아래…")을 매번 되풀이했다 (실측 2026-11-01)
        user += (f"이전 대화 (오래된 것부터, 후속 질문을 이해하는 데만 쓴다):\n{turns}\n"
                 "앞 답에서 이미 말한 상황 설명은 되풀이하지 말고, 이번에 새로 물은 것에 바로 답한다.\n\n")
    user += f"질문: {question}"
    if rejected:
        answer, violations = rejected
        user += (f"\n\n이전 답변: {answer}\n이 답변은 다음 이유로 쓸 수 없었다: {'; '.join(violations)}.\n"
                 "이 문제를 고쳐서 같은 질문에 다시 답한다.")
    return _ask_gemini(client, ANSWER_PROMPT, user).strip()


@dataclass
class Advice:
    summary: str
    candidates: list[dict]
    source: str  # "rule" | "llm"
    check: Check
    fallback_reason: str = ""
    # 가드레일에 막힌 LLM 후보의 위반 목록 (규칙 후보로 대체했을 때만). check는 대체된 규칙 후보의 결과다
    blocked: list[str] = field(default_factory=list)


def make_advice(fact: dict) -> Advice:
    summary = situation(fact)  # 사실 시트 값만 쓰는 고정 문장
    rules = rule_candidates(fact)
    if fact["mode"] == "model":
        try:
            llm = generate_with_llm(fact)
        except LLMError:
            return Advice(summary, rules, "rule", check_candidates(rules, fact), LLM_FAILED)
        if llm is not None:
            check = check_candidates(llm, fact)
            if check.passed:
                return Advice(summary, llm[:MAX_CANDIDATES], "llm", check)
            return Advice(summary, rules, "rule", check_candidates(rules, fact), GUARDRAIL_FAILED,
                          check.violations)
    return Advice(summary, rules, "rule", check_candidates(rules, fact))


def unregistered_in_question(question: str, fact: dict) -> list[str]:
    """질문이 등록되지 않은 설비만 묻고 있으면 그 설비 이름들. 등록 설비가 하나라도 나오면 [].
    "환기"만 쓰면 천창·측창이나 환기팬 중 하나라도 있어야 등록 설비로 본다 (check_text와 같은 규칙)."""
    registered = set(fact["greenhouse"]["equipment"])
    asked = {eq for eq, words in EQUIPMENT_KEYWORDS.items() if any(w in question for w in words)}
    generic_vent = GENERIC_VENT in question.replace("환기팬", "")
    if asked & registered or (generic_vent and registered & {"vent", "exhaust_fan"}):
        return []
    names = [EQUIPMENT_KO[eq] for eq in EQUIPMENT_KO if eq in asked]
    return names + ["환기 설비"] if generic_vent and not asked else names


def answer_question(question: str, fact: dict, history: list[dict] | None = None) -> dict:
    # 미등록 설비만 묻는 질문은 LLM이 그 이름을 다시 써서 가드레일에 막히므로(실측) 바로 답한다.
    # 설비 이름은 사용자가 쓴 말이라 "등록 설비만 언급" 계약과 부딪히지 않는다.
    if names := unregistered_in_question(question, fact):
        top = rule_candidates(fact)[0]
        return {"answer": f"등록 설비에 없는 설비({', '.join(names)})라 안내하지 않습니다. 갖고 계시면 온실 "
                          f"설정에서 등록해 주세요. 지금 상황에서 먼저 볼 방안: {top['title']}.",
                "source": "rule", "note": UNREGISTERED_NOTE, "violations": []}

    llm, fallback, violations = None, "", []
    if fact["mode"] == "model":
        try:
            llm = answer_with_llm(question, fact, history=history)
            if llm is not None and not (first := check_text(llm, fact)).passed:
                # 막힌 이유를 알려주고 한 번만 다시 묻는다. 재질문이 실패하면 llm은 첫 답 그대로라
                # 아래에서 가드레일 실패로 처리된다.
                llm = answer_with_llm(question, fact, rejected=(llm, first.violations), history=history)
        except LLMError:
            fallback = LLM_FAILED
    if llm is not None:
        check = check_text(llm, fact)
        if check.passed:
            return {"answer": llm, "source": "llm", "violations": []}
        fallback = GUARDRAIL_FAILED
        violations = check.violations
    elif not fallback:
        fallback = ("AI 답변이 꺼져 있어 규칙 기반 안내를 드립니다." if fact["mode"] == "model"
                    else "모델이 이 온실에서 아직 검증되지 않아 규칙 기반 안내만 드립니다.")
    top = rule_candidates(fact)[0]
    return {"answer": f"{situation(fact)} 가능한 방안: {top['title']}. {top['reason']}", "source": "rule",
            "note": fallback, "violations": violations}
