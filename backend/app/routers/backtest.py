from dataclasses import asdict

import pandas as pd
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import greenhouse_access
from app.db import get_session
from app.forecast import HORIZONS, backtest_samples, predictor_for
from app.models import Greenhouse, Reading
from app.routers.greenhouses import get_greenhouse
from app.switching import evaluate_horizon

router = APIRouter(prefix="/greenhouses/{greenhouse_id}", tags=["backtest"], dependencies=[Depends(greenhouse_access)])


def load_hourly(session: Session, greenhouse_id: int) -> pd.DataFrame:
    rows = session.exec(
        select(Reading).where(Reading.greenhouse_id == greenhouse_id).order_by(Reading.hour)
    ).all()
    df = pd.DataFrame(
        [(r.hour, r.temperature, r.humidity, r.co2, r.vpd) for r in rows],
        columns=["hour", "temperature", "humidity", "co2", "vpd"],
    )
    return df.set_index("hour").astype(float)


def evaluate_horizons(greenhouse: Greenhouse, hourly: pd.DataFrame):
    """지평별 자동 전환 상태. 반환: (HorizonStatus 목록, 예측기, model_set 이름)."""
    start = hourly.index.min() if not hourly.empty else None
    end = hourly.index.max() if not hourly.empty else None
    predictor, model_set = predictor_for(greenhouse.holdout_source)
    statuses = []
    for h in HORIZONS:
        samples = backtest_samples(hourly, h, predictor) if greenhouse.has_co2 and not hourly.empty else pd.DataFrame()
        statuses.append(evaluate_horizon(h, samples, start, end, greenhouse.has_co2))
    return statuses, predictor, model_set


@router.get("/backtest")
def get_backtest(greenhouse_id: int, session: Session = Depends(get_session)):
    """지평별 주간 버킷 백테스트와 자동 전환 상태 (Trust 화면용)."""
    greenhouse = get_greenhouse(greenhouse_id, session)
    hourly = load_hourly(session, greenhouse_id)
    statuses, _, model_set = evaluate_horizons(greenhouse, hourly)
    return {
        "greenhouse_id": greenhouse_id,
        "history_start": hourly.index.min() if not hourly.empty else None,
        "history_end": hourly.index.max() if not hourly.empty else None,
        "hours": len(hourly),
        # "deployed" = 서비스 모델, "loso:<온실>" = 그 학습 온실을 뺀 데모용 모델
        "model_set": model_set,
        "horizons": [asdict(s) for s in statuses],
    }
