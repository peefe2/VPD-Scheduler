"""수집 API: 센서 게이트웨이가 측정값을 보내면 정시 실측값으로 저장한다.

CSV 가져오기(`app/vpd.py: hourly_first`)와 같은 규칙을 한 건씩 적용한다.
- 각 정시의 값 = 그 정시 구간에서 가장 이른 측정 (평균 아님).
  이미 저장된 값보다 이른 측정이 늦게 도착하면 교체하고, 늦은 측정은 버린다.
- 정시+10분보다 늦은 측정은 그 정시의 실측으로 인정하지 않는다 (CLAUDE.md TODO 임시값).
- 습도 0~100 밖은 클리핑하지 않고 버린다 (CLAUDE.md TODO 임시값).
- CO2가 한 번이라도 들어오면 has_co2 = True.

수집 API(api)와 재생 모드(replay) 온실만 받는다. 재생 모드는 학습 온실 데이터를 흘려보내는
시연용이라 holdout_source가 지정돼 있어야 한다 (in-sample 누수 방지, CLAUDE.md).

인증: 온실별 토큰을 `Authorization: Bearer <토큰>`으로 보내야 한다 (없거나 틀리면 401).
토큰 발급 API를 포함한 웹 화면용 API에는 아직 로그인이 없다 — 센서 쪽 위조만 막는다.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, NaiveDatetime
from sqlmodel import Session, select

from app.db import get_session
from app.models import ConnectionType, Greenhouse, IngestToken, Reading
from app.routers.greenhouses import get_greenhouse
from app.vpd import DEFAULT_MAX_LAG, vpd

router = APIRouter(prefix="/greenhouses/{greenhouse_id}", tags=["ingest"])

MAX_BATCH = 1000
LIVE = (ConnectionType.API, ConnectionType.REPLAY)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _token_row(session: Session, greenhouse_id: int) -> IngestToken | None:
    return session.exec(select(IngestToken).where(IngestToken.greenhouse_id == greenhouse_id)).first()


def _require_token(session: Session, greenhouse: Greenhouse, authorization: str | None) -> None:
    row = _token_row(session, greenhouse.id)
    scheme, _, token = (authorization or "").partition(" ")
    if row is None or scheme.lower() != "bearer" or not hmac.compare_digest(_hash(token), row.token_hash):
        raise HTTPException(401, "invalid or missing ingest token", headers={"WWW-Authenticate": "Bearer"})


@router.post("/ingest-token")
def issue_token(greenhouse_id: int, session: Session = Depends(get_session)):
    """토큰 발급·재발급. 원문은 이 응답에서만 볼 수 있고, 재발급하면 이전 토큰은 바로 무효가 된다."""
    greenhouse = get_greenhouse(greenhouse_id, session)
    if greenhouse.connection_type not in LIVE:
        raise HTTPException(409, "greenhouse is not connected via collection API or replay")
    token = secrets.token_urlsafe(32)
    row = _token_row(session, greenhouse_id) or IngestToken(greenhouse_id=greenhouse_id, token_hash="")
    row.token_hash, row.created_at = _hash(token), datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"token": token, "created_at": row.created_at}


@router.get("/ingest-token")
def token_status(greenhouse_id: int, session: Session = Depends(get_session)):
    """발급 여부만 알려준다. 토큰 값은 돌려주지 않는다."""
    get_greenhouse(greenhouse_id, session)
    row = _token_row(session, greenhouse_id)
    return {"issued": row is not None, "created_at": None if row is None else row.created_at}


class Measurement(BaseModel):
    measured_at: NaiveDatetime  # 온실 현지 시각, 타임존 없음
    temperature: float
    humidity: float
    co2: float | None = None


class IngestBatch(BaseModel):
    measurements: list[Measurement] = Field(min_length=1, max_length=MAX_BATCH)


@router.post("/ingest")
def ingest(
    greenhouse_id: int,
    batch: IngestBatch,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    greenhouse = get_greenhouse(greenhouse_id, session)
    if greenhouse.connection_type not in LIVE:
        raise HTTPException(409, "greenhouse is not connected via collection API or replay")
    _require_token(session, greenhouse, authorization)
    if greenhouse.connection_type is ConnectionType.REPLAY and greenhouse.holdout_source is None:
        raise HTTPException(409, "replay greenhouse needs holdout_source")
    return store_measurements(session, greenhouse, batch.measurements)


def store_measurements(session: Session, greenhouse: Greenhouse, measurements: list[Measurement]) -> dict:
    """정시 첫 측정 규칙으로 저장한다 (수집 API와 데모 온실 준비가 같이 쓴다)."""
    greenhouse_id = greenhouse.id
    counts = {"stored": 0, "replaced": 0, "ignored_not_first": 0,
              "rejected_late": 0, "rejected_humidity_out_of_range": 0}
    # 이른 측정부터 처리하면 같은 정시의 뒤 측정은 자연히 "첫 값 아님"이 된다
    for m in sorted(measurements, key=lambda m: m.measured_at):
        if not 0 <= m.humidity <= 100:
            counts["rejected_humidity_out_of_range"] += 1
            continue
        hour = m.measured_at.replace(minute=0, second=0, microsecond=0)
        if m.measured_at - hour > DEFAULT_MAX_LAG:
            counts["rejected_late"] += 1
            continue
        existing = session.exec(
            select(Reading).where(Reading.greenhouse_id == greenhouse_id, Reading.hour == hour)
        ).first()
        if existing is not None:
            if existing.measured_at <= m.measured_at:
                counts["ignored_not_first"] += 1
                continue
            session.delete(existing)
            session.flush()
            counts["replaced"] += 1
        else:
            counts["stored"] += 1
        session.add(Reading(
            greenhouse_id=greenhouse_id, hour=hour, measured_at=m.measured_at,
            temperature=m.temperature, humidity=m.humidity, co2=m.co2,
            vpd=float(vpd(m.temperature, m.humidity)),
        ))
        if m.co2 is not None and not greenhouse.has_co2:
            greenhouse.has_co2 = True
            session.add(greenhouse)
    session.commit()
    return counts
