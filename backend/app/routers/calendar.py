from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth import greenhouse_access
from app.bands import band_series, band_versions
from app.calendar import DAYTIME_HOURS, MIN_DAY_HOURS, MIN_NIGHT_HOURS, daily_summary
from app.db import get_session
from app.models import Reading
from app.routers.greenhouses import get_greenhouse

router = APIRouter(prefix="/greenhouses/{greenhouse_id}", tags=["calendar"], dependencies=[Depends(greenhouse_access)])


def _num(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 4)


@router.get("/calendar")
def get_calendar(
    greenhouse_id: int,
    start: date | None = Query(None, description="포함, 기본: 이력 첫날"),
    end: date | None = Query(None, description="포함, 기본: 이력 마지막 날"),
    session: Session = Depends(get_session),
):
    """날짜별 대역 안 시간. 비율은 관측된 정시 기준이고 관측 정시 수를 같이 준다."""
    greenhouse = get_greenhouse(greenhouse_id, session)
    if start and end and start > end:
        raise HTTPException(422, "start must be on or before end")

    query = select(Reading.hour, Reading.vpd).where(Reading.greenhouse_id == greenhouse_id)
    if start:
        query = query.where(Reading.hour >= datetime.combine(start, time.min))
    if end:
        query = query.where(Reading.hour < datetime.combine(end + timedelta(days=1), time.min))
    rows = session.exec(query).all()
    vpd = pd.Series([r.vpd for r in rows], index=pd.DatetimeIndex([r.hour for r in rows]), dtype=float)

    versions = band_versions(session, greenhouse)
    low, high = band_series(vpd.index, versions)
    summary = daily_summary(vpd, low, high)
    days = [
        {
            "date": d.date().isoformat(),
            "band": {"low": float(r.band_low), "high": float(r.band_high)},  # 그날 유효했던 대역
            "hours_observed": int(r.observed),
            "hours_in_band": int(r.in_band),
            "hours_below": int(r.below),
            "hours_above": int(r.above),
            "in_band_ratio": _num(r.in_band_ratio),
            # 캘린더 칸 색: 낮 대역 안 비율 (sufficient=False면 "데이터 부족"으로 칠함)
            "daytime": {
                "hours_observed": int(r.day_observed),
                "hours_in_band": int(r.day_in_band),
                "hours_below": int(r.day_below),
                "hours_above": int(r.day_above),
                "in_band_ratio": _num(r.day_in_band_ratio),
                "sufficient": bool(r.day_sufficient),
            },
            # 별도 배지: 밤 과습(대역 아래) 비율
            "night": {
                "hours_observed": int(r.night_observed),
                "hours_in_band": int(r.night_in_band),
                "hours_below": int(r.night_below),
                "hours_above": int(r.night_above),
                "below_ratio": _num(r.night_below_ratio),
                "sufficient": bool(r.night_sufficient),
            },
            "vpd_min": _num(r.vpd_min),
            "vpd_max": _num(r.vpd_max),
            "vpd_mean": _num(r.vpd_mean),
        }
        for d, r in summary.iterrows()
    ]
    return {
        "greenhouse_id": greenhouse_id,
        # 현재 대역. 날짜별 판정은 각 day.band(그날 유효했던 버전)로 한다
        "band": {"low": greenhouse.vpd_low, "high": greenhouse.vpd_high},
        "bands": [{"effective_from": v[0].isoformat() if v[0] else None, "low": v[1], "high": v[2]}
                  for v in versions],
        "daytime_hours": [DAYTIME_HOURS.start, DAYTIME_HOURS.stop - 1],
        "min_hours": {"daytime": MIN_DAY_HOURS, "night": MIN_NIGHT_HOURS},
        "days": days,
    }
