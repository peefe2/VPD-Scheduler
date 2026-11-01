"""데모 온실 자동 준비 (VPD_DEMO=1). 친구 PC나 시연 서버에서 켜자마자 AI 어드바이저까지 보이게 한다.

재생 모드(research/replay_ingest.py)와 같은 규칙으로 학습 온실 farm3_2023 데이터를 **날짜만**
옮겨 넣는다 — 원본 앞 35일을 지난 이력으로, 그 다음날이 오늘이 되게. 토큰·HTTP 없이 DB에 바로
쓰고, 다시 켜면 지금 시각까지 빈 정시만 채운다(이동 일수는 처음 넣은 값을 따른다).

- holdout_source를 farm3_2023으로 둬서 백테스트·예측이 farm3를 뺀 LOSO 모델을 쓴다 (in-sample 누수 방지).
- 켜져 있는 동안 새 정시는 들어오지 않는다. 시연 직전에 다시 켜면 그 시각까지 채워진다.
- 원본이 84일치라 처음 만든 뒤 약 7주가 지나면 더 채울 값이 없다. 그때는 DB에서 데모 온실을 지우고 다시 켠다.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlmodel import Session, select

from app.models import ConnectionType, Equipment, Greenhouse, Reading
from app.routers.ingest import Measurement, store_measurements

DEMO_NAME = "데모 온실 (farm3 재생)"
DEMO_SOURCE = "farm3_2023"
BACKFILL_DAYS = 35  # 첫 자동 전환이 가능한 최소 이력 (CLAUDE.md)
DATA_PATH = Path(os.environ.get(
    "VPD_DEMO_DATA", Path(__file__).resolve().parents[2] / "research" / "data" / "combined_hourly_pointsample.csv"
))


def ensure_demo(session: Session, now: datetime | None = None, data_path: Path = DATA_PATH,
                backfill_days: int = BACKFILL_DAYS) -> Greenhouse:
    now = now or datetime.now()
    df = pd.read_csv(data_path, parse_dates=["date"])
    df = df[df["source"] == DEMO_SOURCE].sort_values("date")
    first_day = df["date"].iloc[0].normalize()

    gh = session.exec(select(Greenhouse).where(Greenhouse.name == DEMO_NAME)).first()
    if gh is None:
        gh = Greenhouse(name=DEMO_NAME, crop="미상(연구 데이터)", connection_type=ConnectionType.REPLAY,
                        holdout_source=DEMO_SOURCE, equipment=list(Equipment), public=True)
        session.add(gh)
        session.commit()
        session.refresh(gh)
    elif not gh.public:  # 로그인 기능 전에 만든 데모 온실 — 누구나 보게 공개로
        gh.public = True
        session.add(gh)
        session.commit()

    first = session.exec(select(Reading).where(Reading.greenhouse_id == gh.id).order_by(Reading.hour)).first()
    if first is None:  # 처음: 원본 (앞 이력 다음날)이 오늘이 되게
        shift = pd.Timestamp(now).normalize() - (first_day + pd.Timedelta(days=backfill_days))
    else:  # 다시 켬: 처음 넣은 이동 일수를 그대로
        shift = pd.Timestamp(first.hour).normalize() - first_day
    last = session.exec(select(Reading.hour).where(Reading.greenhouse_id == gh.id)
                        .order_by(Reading.hour.desc())).first()

    shown = df["date"] + shift
    todo = df[(shown <= pd.Timestamp(now)) & (shown > pd.Timestamp(last or datetime.min + timedelta(days=1)))]
    store_measurements(session, gh, [
        Measurement(measured_at=(row.date + shift).to_pydatetime(), temperature=row.temp,
                    humidity=row.humidity, co2=None if pd.isna(row.co2) else row.co2)
        for row in todo.itertuples()
    ])
    return gh
