from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, delete, select

from app.advisor import answer_question, build_fact_sheet, make_advice, situation
from app.db import get_session
from app.models import AdviceDecision, AdviceRecord, ConnectionType, Greenhouse, Reading
from app.routers.greenhouses import get_greenhouse
from app.routers.today import today_payload
from app.today import band_status

router = APIRouter(prefix="/greenhouses/{greenhouse_id}/advisor", tags=["advisor"])

LIVE = {ConnectionType.API, ConnectionType.REPLAY}


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def _fact_or_reason(session: Session, gh: Greenhouse) -> tuple[dict | None, str]:
    if gh.connection_type not in LIVE:
        return None, "AI 어드바이저는 수집 API·재생 온실에서만 씁니다. CSV 이력은 캘린더에서 돌아볼 수 있습니다."
    today = today_payload(session, gh)
    if today["latest"] is None:
        return None, "아직 들어온 정시 값이 없습니다."
    return build_fact_sheet(gh, today), ""


def _decisions(session: Session, advice_id: int) -> dict[int, str]:
    rows = session.exec(select(AdviceDecision).where(AdviceDecision.advice_id == advice_id)).all()
    return {r.candidate_index: r.decision for r in rows}


@router.get("")
def get_advice(greenhouse_id: int, session: Session = Depends(get_session)):
    """현재 정시 기준 조치 후보. 같은 정시에 다시 부르면 저장된 후보를 그대로 준다
    (기록과 화면이 어긋나지 않게). 아직 아무 선택이 없으면 설비 변경 등을 반영해 새로 만든다."""
    gh = get_greenhouse(greenhouse_id, session)
    fact, reason = _fact_or_reason(session, gh)
    if fact is None:
        return _unavailable(reason)

    hour = datetime.fromisoformat(fact["observed_at"])
    record = session.exec(
        select(AdviceRecord).where(AdviceRecord.greenhouse_id == gh.id, AdviceRecord.hour == hour)
    ).first()
    advice = make_advice(fact)
    if record is None:
        record = AdviceRecord(greenhouse_id=gh.id, hour=hour, source=advice.source,
                              candidates=advice.candidates, fact_sheet=fact)
    elif not _decisions(session, record.id):
        record.source, record.candidates, record.fact_sheet = advice.source, advice.candidates, fact
    session.add(record)
    session.commit()
    session.refresh(record)

    decided = _decisions(session, record.id)
    return {
        "available": True,
        "advice_id": record.id,
        "observed_at": record.hour,
        "mode": record.fact_sheet["mode"],
        "source": record.source,
        "summary": situation(record.fact_sheet),
        "fact_sheet": record.fact_sheet,
        "candidates": [{**c, "index": i, "decision": decided.get(i)} for i, c in enumerate(record.candidates)],
        "guardrail": {"passed": advice.check.passed, "violations": advice.check.violations,
                      "fallback_reason": advice.fallback_reason},
    }


class DecisionIn(BaseModel):
    candidate_index: int = Field(ge=0)
    decision: Literal["done", "skipped"] | None  # None이면 선택 취소


@router.post("/{advice_id}/decisions")
def decide(greenhouse_id: int, advice_id: int, body: DecisionIn, session: Session = Depends(get_session)):
    get_greenhouse(greenhouse_id, session)
    record = session.get(AdviceRecord, advice_id)
    if record is None or record.greenhouse_id != greenhouse_id:
        raise HTTPException(404, "advice not found")
    if body.candidate_index >= len(record.candidates):
        raise HTTPException(422, "candidate_index out of range")
    session.exec(delete(AdviceDecision).where(
        AdviceDecision.advice_id == advice_id, AdviceDecision.candidate_index == body.candidate_index
    ))
    if body.decision is not None:
        session.add(AdviceDecision(advice_id=advice_id, candidate_index=body.candidate_index,
                                   decision=body.decision, decided_at=datetime.now(timezone.utc)))
    session.commit()
    return {"advice_id": advice_id, "decisions": _decisions(session, advice_id)}


@router.get("/logs")
def logs(greenhouse_id: int, limit: int = 50, session: Session = Depends(get_session)):
    """선택한 기록과 2시간 뒤 실측 VPD. 2시간 뒤 정시 값이 아직 없으면 null."""
    gh = get_greenhouse(greenhouse_id, session)
    rows = session.exec(
        select(AdviceDecision, AdviceRecord)
        .join(AdviceRecord, AdviceDecision.advice_id == AdviceRecord.id)
        .where(AdviceRecord.greenhouse_id == greenhouse_id)
        .order_by(AdviceRecord.hour.desc(), AdviceDecision.candidate_index)
        .limit(min(max(limit, 1), 200))
    ).all()
    out = []
    for decision, record in rows:
        after = session.exec(select(Reading).where(
            Reading.greenhouse_id == greenhouse_id, Reading.hour == record.hour + timedelta(hours=2)
        )).first()
        c = record.candidates[decision.candidate_index]
        out.append({
            "advice_id": record.id,
            "observed_at": record.hour,
            "title": c["title"],
            "equipment": c.get("equipment"),
            "decision": decision.decision,
            "decided_at": decision.decided_at,
            "source": record.source,
            "vpd_at": record.fact_sheet["current"]["vpd"],
            "status_at": record.fact_sheet["current"]["band_status"],
            "vpd_after_2h": None if after is None else round(after.vpd, 4),
            "status_after_2h": None if after is None else band_status(after.vpd, gh.vpd_low, gh.vpd_high),
        })
    return out


class QuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.post("/ask")
def ask(greenhouse_id: int, body: QuestionIn, session: Session = Depends(get_session)):
    """자유 질문. 조치 후보와 같은 가드레일을 거친다 (LLM 미연결이면 규칙 안내)."""
    gh = get_greenhouse(greenhouse_id, session)
    fact, reason = _fact_or_reason(session, gh)
    if fact is None:
        raise HTTPException(409, reason)
    return answer_question(body.question, fact)
