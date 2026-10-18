"""수집 API: 센서 게이트웨이가 측정값을 보내면 정시 실측값으로 저장한다.

CSV 가져오기(`app/vpd.py: hourly_first`)와 같은 규칙을 한 건씩 적용한다.
- 각 정시의 값 = 그 정시 구간에서 가장 이른 측정 (평균 아님).
  이미 저장된 값보다 이른 측정이 늦게 도착하면 교체하고, 늦은 측정은 버린다.
- 정시+10분보다 늦은 측정은 그 정시의 실측으로 인정하지 않는다 (CLAUDE.md TODO 임시값).
- 습도 0~100 밖은 클리핑하지 않고 버린다 (CLAUDE.md TODO 임시값).
- CO2가 한 번이라도 들어오면 has_co2 = True.

수집 API(api)와 재생 모드(replay) 온실만 받는다. 재생 모드는 학습 온실 데이터를 흘려보내는
시연용이라 holdout_source가 지정돼 있어야 한다 (in-sample 누수 방지, CLAUDE.md).
인증은 아직 없다 (로컬 시연용).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, NaiveDatetime
from sqlmodel import Session, select

from app.db import get_session
from app.models import ConnectionType, Reading
from app.routers.greenhouses import get_greenhouse
from app.vpd import DEFAULT_MAX_LAG, vpd

router = APIRouter(prefix="/greenhouses/{greenhouse_id}", tags=["ingest"])

MAX_BATCH = 1000


class Measurement(BaseModel):
    measured_at: NaiveDatetime  # 온실 현지 시각, 타임존 없음
    temperature: float
    humidity: float
    co2: float | None = None


class IngestBatch(BaseModel):
    measurements: list[Measurement] = Field(min_length=1, max_length=MAX_BATCH)


@router.post("/ingest")
def ingest(greenhouse_id: int, batch: IngestBatch, session: Session = Depends(get_session)):
    greenhouse = get_greenhouse(greenhouse_id, session)
    if greenhouse.connection_type not in (ConnectionType.API, ConnectionType.REPLAY):
        raise HTTPException(409, "greenhouse is not connected via collection API or replay")
    if greenhouse.connection_type is ConnectionType.REPLAY and greenhouse.holdout_source is None:
        raise HTTPException(409, "replay greenhouse needs holdout_source")

    counts = {"stored": 0, "replaced": 0, "ignored_not_first": 0,
              "rejected_late": 0, "rejected_humidity_out_of_range": 0}
    # 이른 측정부터 처리하면 같은 정시의 뒤 측정은 자연히 "첫 값 아님"이 된다
    for m in sorted(batch.measurements, key=lambda m: m.measured_at):
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
