from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import greenhouse_access
from app.db import get_session
from app.models import Greenhouse, Reading
from app.routers.backtest import evaluate_horizons, load_hourly
from app.routers.greenhouses import get_greenhouse
from app.today import band_status, current_run_hours, displayed_forecasts

router = APIRouter(prefix="/greenhouses/{greenhouse_id}", tags=["today"], dependencies=[Depends(greenhouse_access)])


def today_payload(session: Session, greenhouse: Greenhouse) -> dict:
    """오늘 화면 데이터. 어드바이저의 사실 시트도 이 값에서 만든다."""
    low, high = greenhouse.vpd_low, greenhouse.vpd_high
    base = {
        "greenhouse_id": greenhouse.id,
        "connection_type": greenhouse.connection_type,
        "band": {"low": low, "high": high},
    }
    hourly = load_hourly(session, greenhouse.id)
    if hourly.empty:
        return {**base, "model_set": None, "latest": None, "run_hours": 0, "basis": None, "forecasts": []}

    latest = session.exec(
        select(Reading).where(Reading.greenhouse_id == greenhouse.id).order_by(Reading.hour.desc())
    ).first()
    statuses, predictor, model_set = evaluate_horizons(greenhouse, hourly)
    forecasts = displayed_forecasts(hourly, statuses, predictor, low, high)
    # 유지 시간 안내의 근거: 표시 지평 중 하나라도 모델값이면 "model"
    basis = "model" if any(f.source == "model" for f in forecasts) else "persistence"
    return {
        **base,
        "model_set": model_set,
        "latest": {
            "hour": latest.hour,
            "measured_at": latest.measured_at,
            "temperature": latest.temperature,
            "humidity": latest.humidity,
            "co2": latest.co2,
            "vpd": round(latest.vpd, 4),
            "band_status": band_status(latest.vpd, low, high),
        },
        "run_hours": current_run_hours(hourly["vpd"], low, high),
        "basis": basis,
        "forecasts": [{**asdict(f), "vpd": round(f.vpd, 4)} for f in forecasts],
    }


@router.get("/today")
def get_today(greenhouse_id: int, session: Session = Depends(get_session)):
    """오늘 화면: 최근 정시 값, 지평별 표시 예측, 현재 대역 상태 지속 시간.

    "지금"은 서버 시계가 아니라 마지막으로 저장된 정시다 (측정 시각은 온실 현지 시각,
    타임존 없음). 값이 끊겼는지는 화면에서 latest.hour와 현재 시각을 비교해 알린다.
    """
    return today_payload(session, get_greenhouse(greenhouse_id, session))
