import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, delete, select

from app.advisor import EQUIPMENT_KO, answer_question, build_fact_sheet, make_advice, situation
from app.auth import greenhouse_access, optional_user
from app.db import get_session
from app.models import AdviceAction, AdviceQuestion, AdviceRecord, ConnectionType, Greenhouse, Reading, User
from app.routers.greenhouses import get_greenhouse
from app.routers.today import today_payload
from app.today import band_status

router = APIRouter(prefix="/greenhouses/{greenhouse_id}/advisor", tags=["advisor"], dependencies=[Depends(greenhouse_access)])

LIVE = {ConnectionType.API, ConnectionType.REPLAY}
HISTORY_TURNS = 3  # 후속 질문에 같이 보내는 앞 대화 수
# "조치 안 함"의 이유 태그. 재배 전문가가 규칙을 검토할 때 쓸 정보라 자유 글 대신 고정 목록
SKIP_REASONS = {"weather": "바깥 날씨", "unavailable": "설비를 쓸 수 없음", "soon": "곧 바뀔 것 같음", "other": "기타"}


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def _fact_or_reason(session: Session, gh: Greenhouse) -> tuple[dict | None, str]:
    if gh.connection_type not in LIVE:
        return None, "AI 어드바이저는 수집 API·재생 온실에서만 씁니다. CSV 이력은 캘린더에서 돌아볼 수 있습니다."
    today = today_payload(session, gh)
    if today["latest"] is None:
        return None, "아직 들어온 정시 값이 없습니다."
    return build_fact_sheet(gh, today), ""


def _has_actions(session: Session, advice_id: int) -> bool:
    return session.exec(select(AdviceAction.id).where(AdviceAction.advice_id == advice_id)).first() is not None


def _action_out(a: AdviceAction | None) -> dict | None:
    if a is None:
        return None
    return {"kind": a.kind, "candidate_index": a.candidate_index, "equipment": a.equipment,
            "reason": a.reason, "decided_at": a.decided_at}


def _action_title(a: AdviceAction, record: AdviceRecord) -> str:
    if a.kind == "candidate":
        return record.candidates[a.candidate_index]["title"]
    if a.kind == "other":
        return f"후보에 없는 조치: {EQUIPMENT_KO.get(a.equipment, a.equipment)}"
    return f"조치 안 함 ({SKIP_REASONS.get(a.reason, '이유 없음')})"


@router.get("")
def get_advice(greenhouse_id: int, visitor: str | None = None, session: Session = Depends(get_session),
               user: User | None = Depends(optional_user)):
    """현재 정시 기준 조치 후보와, 보는 사람이 이 정시에 남긴 조치(action). 같은 정시에 다시 부르면
    저장된 후보를 그대로 준다 (기록과 화면이 어긋나지 않게). 아무도 기록하지 않았고 사실 시트(설비·
    대역 등)가 바뀌었으면 새로 만든다. 화면이 1분마다 다시 부르므로, 같은 사실 시트로는 LLM을 다시
    부르지 않는다."""
    gh = get_greenhouse(greenhouse_id, session)
    fact, reason = _fact_or_reason(session, gh)
    if fact is None:
        return _unavailable(reason)

    hour = datetime.fromisoformat(fact["observed_at"])
    record = session.exec(
        select(AdviceRecord).where(AdviceRecord.greenhouse_id == gh.id, AdviceRecord.hour == hour)
    ).first()
    if record is None or (record.fact_sheet != fact and not _has_actions(session, record.id)):
        advice = make_advice(fact)
        record = record or AdviceRecord(greenhouse_id=gh.id, hour=hour, source="", candidates=[], fact_sheet={})
        record.source, record.candidates, record.fact_sheet = advice.source, advice.candidates, fact
        record.guardrail = {"passed": advice.check.passed, "violations": advice.check.violations,
                            "fallback_reason": advice.fallback_reason, "blocked": advice.blocked}
        session.add(record)
        session.commit()
        session.refresh(record)

    # 로그인도 방문자 id도 없으면 누구의 기록인지 모른다 (questions와 같은 규칙)
    mine = None if user is None and visitor is None else session.exec(select(AdviceAction).where(
        AdviceAction.advice_id == record.id, AdviceAction.visitor == _chat_key(gh, user, visitor))).first()
    return {
        "available": True,
        "advice_id": record.id,
        "observed_at": record.hour,
        "mode": record.fact_sheet["mode"],
        "source": record.source,
        "summary": situation(record.fact_sheet),
        "fact_sheet": record.fact_sheet,
        "candidates": [{**c, "index": i} for i, c in enumerate(record.candidates)],
        "action": _action_out(mine),
        # 이 컬럼이 생기기 전 기록(guardrail None)은 규칙 후보였으므로 통과로 본다. blocked는 나중에
        # 더한 키라 예전 기록에는 없다
        "guardrail": {"passed": True, "violations": [], "fallback_reason": "", "blocked": [],
                      **(record.guardrail or {})},
    }


class ActionIn(BaseModel):
    kind: Literal["candidate", "other", "none"]
    candidate_index: int | None = Field(default=None, ge=0)
    equipment: str | None = None
    reason: Literal["weather", "unavailable", "soon", "other"] | None = None
    # 로그인 안 한 방문자(공개 데모)의 브라우저 id. 질문하기와 같은 열쇠로 사람마다 나눈다
    visitor: str | None = Field(default=None, min_length=1, max_length=64)


def _record_for(session: Session, greenhouse_id: int, advice_id: int) -> AdviceRecord:
    record = session.get(AdviceRecord, advice_id)
    if record is None or record.greenhouse_id != greenhouse_id:
        raise HTTPException(404, "advice not found")
    return record


@router.post("/{advice_id}/action")
def record_action(greenhouse_id: int, advice_id: int, body: ActionIn, session: Session = Depends(get_session),
                  user: User | None = Depends(optional_user)):
    """이번 정시에 한 조치 하나를 남긴다 (다시 보내면 바꾼다). 설비 명령이 아니다."""
    if user is None and body.visitor is None:
        raise HTTPException(422, "visitor is required when not logged in")
    gh = get_greenhouse(greenhouse_id, session)
    record = _record_for(session, greenhouse_id, advice_id)
    action = AdviceAction(advice_id=advice_id, visitor=_chat_key(gh, user, body.visitor), kind=body.kind)
    if body.kind == "candidate":
        if body.candidate_index is None or body.candidate_index >= len(record.candidates):
            raise HTTPException(422, "candidate_index out of range")
        action.candidate_index = body.candidate_index
        action.equipment = record.candidates[body.candidate_index].get("equipment")
    elif body.kind == "other":
        # 그 정시 사실 시트의 등록 설비만 (기록과 근거가 어긋나지 않게)
        if body.equipment not in record.fact_sheet["greenhouse"]["equipment"]:
            raise HTTPException(422, "equipment must be a registered one")
        action.equipment = body.equipment
    else:
        if body.reason is None:
            raise HTTPException(422, "reason is required")
        action.reason = body.reason
    session.exec(delete(AdviceAction).where(AdviceAction.advice_id == advice_id,
                                            AdviceAction.visitor == action.visitor))
    session.add(action)
    session.commit()
    session.refresh(action)
    return _action_out(action)


@router.delete("/{advice_id}/action", status_code=204)
def clear_action(greenhouse_id: int, advice_id: int, visitor: str | None = None,
                 session: Session = Depends(get_session), user: User | None = Depends(optional_user)):
    if user is None and visitor is None:
        raise HTTPException(422, "visitor is required when not logged in")
    gh = get_greenhouse(greenhouse_id, session)
    _record_for(session, greenhouse_id, advice_id)
    session.exec(delete(AdviceAction).where(AdviceAction.advice_id == advice_id,
                                            AdviceAction.visitor == _chat_key(gh, user, visitor)))
    session.commit()


@router.get("/logs")
def logs(greenhouse_id: int, limit: int = 50, visitor: str | None = None, session: Session = Depends(get_session),
         user: User | None = Depends(optional_user)):
    """내가 남긴 조치와 그 정시·2시간 뒤 실측 VPD (최근 것부터). 2시간 뒤 정시 값이 아직 없으면 null.
    효과를 판정하지 않는다 — 날씨 등 다른 요인도 VPD를 바꾼다."""
    gh = get_greenhouse(greenhouse_id, session)
    if user is None and visitor is None:
        return []
    rows = session.exec(
        select(AdviceAction, AdviceRecord)
        .join(AdviceRecord, AdviceAction.advice_id == AdviceRecord.id)
        .where(AdviceRecord.greenhouse_id == greenhouse_id, AdviceAction.visitor == _chat_key(gh, user, visitor))
        .order_by(AdviceRecord.hour.desc())
        .limit(min(max(limit, 1), 200))
    ).all()
    out = []
    for action, record in rows:
        after = session.exec(select(Reading).where(
            Reading.greenhouse_id == greenhouse_id, Reading.hour == record.hour + timedelta(hours=2)
        )).first()
        out.append({
            "advice_id": record.id,
            "observed_at": record.hour,
            **_action_out(action),
            "title": _action_title(action, record),
            "source": record.source,
            "vpd_at": record.fact_sheet["current"]["vpd"],
            "status_at": record.fact_sheet["current"]["band_status"],
            "vpd_after_2h": None if after is None else round(after.vpd, 4),
            "status_after_2h": None if after is None else band_status(after.vpd, gh.vpd_low, gh.vpd_high),
        })
    return out


class QuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    # 읽기 전용 공개 데모에서 브라우저마다 만드는 방문자 id. 평소(온실 주인)에는 비운다.
    visitor: str | None = Field(default=None, min_length=1, max_length=64)


# 최근 1분 안의 질문 시각 (프로세스 하나 기준). VPD_ASK_PER_MINUTE가 있으면 넘는 질문은 429 —
# 공개 데모에서 무료 Gemini 키 한도를 여러 방문자가 함께 쓰기 때문
ask_limit: deque[float] = deque()


def _check_ask_limit() -> None:
    per_minute = os.environ.get("VPD_ASK_PER_MINUTE")
    if not per_minute:
        return
    now = time.monotonic()
    while ask_limit and now - ask_limit[0] > 60:
        ask_limit.popleft()
    if len(ask_limit) >= int(per_minute):
        raise HTTPException(429, "질문이 많아 잠시 쉬고 있습니다. 1분 뒤에 다시 물어봐 주세요.")
    ask_limit.append(now)


def _chat_key(gh: Greenhouse, user: User | None, visitor: str | None) -> str | None:
    """대화를 나누는 열쇠. 내 온실이면 None(주인 대화), 남의 공개(데모) 온실이면 계정별, 로그인
    안 했으면 브라우저 방문자 id — 공개 온실에서 남의 대화가 보이지 않게."""
    if user is not None:
        return None if gh.owner_id == user.id else f"user:{user.id}"
    return visitor


@router.post("/ask")
def ask(greenhouse_id: int, body: QuestionIn, session: Session = Depends(get_session),
        user: User | None = Depends(optional_user)):
    """자유 질문. 조치 후보와 같은 가드레일을 거친다 (LLM 미연결이면 규칙 안내).
    질문과 답은 대화 내역으로 저장한다. 로그인 안 했으면 방문자 id가 있어야 한다."""
    if user is None and body.visitor is None:
        raise HTTPException(422, "visitor is required when not logged in")
    gh = get_greenhouse(greenhouse_id, session)
    key = _chat_key(gh, user, body.visitor)
    fact, reason = _fact_or_reason(session, gh)
    if fact is None:
        raise HTTPException(409, reason)
    _check_ask_limit()
    hour = datetime.fromisoformat(fact["observed_at"])
    # 후속 질문용 앞 대화: 같은 방문자, 같은 정시(같은 사실 시트)의 최근 3개만. 다른 정시 답에 든
    # 숫자는 지금 사실 시트에 없어서, LLM이 따라 쓰면 가드레일에 막힌다.
    recent = session.exec(
        select(AdviceQuestion).where(AdviceQuestion.greenhouse_id == gh.id, AdviceQuestion.observed_at == hour,
                                     AdviceQuestion.visitor == key)
        .order_by(AdviceQuestion.id.desc()).limit(HISTORY_TURNS)
    ).all()
    history = [{"question": r.question, "answer": r.answer} for r in reversed(recent)]
    result = answer_question(body.question, fact, history=history)
    row = AdviceQuestion(
        greenhouse_id=gh.id, observed_at=hour,
        vpd=fact["current"]["vpd"], question=body.question, answer=result["answer"],
        source=result["source"], note=result.get("note", ""), violations=result["violations"],
        visitor=key,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/questions")
def questions(greenhouse_id: int, limit: int = 50, visitor: str | None = None,
              session: Session = Depends(get_session), user: User | None = Depends(optional_user)):
    """대화 내역. 최근 limit개를 오래된 것부터 (채팅 화면 순서). 내 대화만 (_chat_key)."""
    gh = get_greenhouse(greenhouse_id, session)
    if user is None and visitor is None:
        return []
    rows = session.exec(
        select(AdviceQuestion).where(AdviceQuestion.greenhouse_id == greenhouse_id,
                                     AdviceQuestion.visitor == _chat_key(gh, user, visitor))
        .order_by(AdviceQuestion.id.desc()).limit(min(max(limit, 1), 200))
    ).all()
    return list(reversed(rows))
