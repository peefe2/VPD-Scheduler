from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import Reading
from app.routers.greenhouses import get_greenhouse

router = APIRouter(prefix="/greenhouses/{greenhouse_id}", tags=["readings"])

MAX_DAYS = 31


@router.get("/readings")
def list_readings(
    greenhouse_id: int,
    start: date = Query(..., description="포함"),
    end: date = Query(..., description="포함"),
    session: Session = Depends(get_session),
):
    """정시 실측값 (캘린더 상세용). 측정이 없는 정시는 응답에 없다 — 보간하지 않는다."""
    get_greenhouse(greenhouse_id, session)
    if start > end:
        raise HTTPException(422, "start must be on or before end")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(422, f"range must be at most {MAX_DAYS} days")
    rows = session.exec(
        select(Reading)
        .where(
            Reading.greenhouse_id == greenhouse_id,
            Reading.hour >= datetime.combine(start, time.min),
            Reading.hour < datetime.combine(end + timedelta(days=1), time.min),
        )
        .order_by(Reading.hour)
    ).all()
    return [
        {
            "hour": r.hour.isoformat(),
            "temperature": r.temperature,
            "humidity": r.humidity,
            "co2": r.co2,
            "vpd": round(r.vpd, 4),
        }
        for r in rows
    ]
