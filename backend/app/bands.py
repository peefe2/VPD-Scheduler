"""적정 대역 변경 이력 (CLAUDE.md "대역 변경 이력").

대역을 바꿔도 과거 캘린더가 소리 없이 다시 칠해지지 않게, 날짜마다 그날 유효했던 대역으로
판정한다. 오늘 화면·어드바이저·이탈 판정은 현재 대역(= 마지막 버전 = Greenhouse.vpd_low/high).
"""

from datetime import date

import numpy as np
import pandas as pd
from sqlmodel import Session, delete, select

from app.models import BandVersion, Greenhouse

Version = tuple[date | None, float, float]


def band_versions(session: Session, gh: Greenhouse) -> list[Version]:
    """적용 시작일 순서. 이력이 없으면 현재 대역을 처음부터로 본다."""
    rows = session.exec(select(BandVersion).where(BandVersion.greenhouse_id == gh.id)).all()
    if not rows:
        return [(None, gh.vpd_low, gh.vpd_high)]
    return sorted(((r.effective_from, r.vpd_low, r.vpd_high) for r in rows),
                  key=lambda v: v[0] or date.min)


def record_band_change(session: Session, gh: Greenhouse, low: float, high: float,
                       apply: str, today: date) -> None:
    """대역 변경을 이력에 남긴다 (commit은 호출자가). gh의 현재 대역도 바꾼다.

    apply="today": 오늘부터 적용 (지난 캘린더 유지).
    apply="all": 처음부터 적용 — 잘못 입력한 값 정정용으로 이전 이력을 지운다.
    """
    if apply == "all":
        session.exec(delete(BandVersion).where(BandVersion.greenhouse_id == gh.id))
        session.add(BandVersion(greenhouse_id=gh.id, effective_from=None, vpd_low=low, vpd_high=high))
    else:
        existing = session.exec(select(BandVersion).where(BandVersion.greenhouse_id == gh.id)).all()
        if not existing:  # 첫 변경: 지금까지의 대역을 "처음부터" 버전으로 남긴다
            session.add(BandVersion(greenhouse_id=gh.id, effective_from=None,
                                    vpd_low=gh.vpd_low, vpd_high=gh.vpd_high))
        same_day = next((r for r in existing if r.effective_from == today), None)
        if same_day:  # 같은 날 여러 번 바꾸면 마지막 값만
            same_day.vpd_low, same_day.vpd_high = low, high
            session.add(same_day)
        else:
            session.add(BandVersion(greenhouse_id=gh.id, effective_from=today, vpd_low=low, vpd_high=high))
    gh.vpd_low, gh.vpd_high = low, high


def band_series(index: pd.DatetimeIndex, versions: list[Version]) -> tuple[pd.Series, pd.Series]:
    """정시마다 그 날짜에 유효했던 (하한, 상한)."""
    starts = np.array([np.datetime64(v[0] or date.min, "D") for v in versions])
    days = index.normalize().values.astype("datetime64[D]")
    pos = np.clip(np.searchsorted(starts, days, side="right") - 1, 0, len(versions) - 1)
    lows = np.array([v[1] for v in versions], dtype=float)[pos]
    highs = np.array([v[2] for v in versions], dtype=float)[pos]
    return pd.Series(lows, index=index), pd.Series(highs, index=index)
