"""오늘 화면: 최근 정시 값, 지평별로 표시할 예측, 현재 대역 상태가 이어진 시간.

- 지평마다 자동 전환 상태(`app/switching.py`)가 "모델 사용"일 때만 모델값을 보여준다.
  그 상태라도 직전 t-2, t-1, t 세 정시가 다 있고 CO2까지 있어야 하며(보간 없음),
  아니면 이번 정시는 persistence(현재 값)를 보여준다.
- +6h는 오늘 화면에 보여주지 않는다 (결정 2026-11-07). 전환 판정에서 빠진 검증용 지평이라
  "검증된 예측만 보여준다"는 원칙과 맞지 않고, 이탈 탐지도 약하다(그룹A 0.37, 그룹B 0.16).
  백테스트·모델 신뢰도 화면에는 검증값으로 남긴다.
- "대역 안 유지 시간"은 예측으로 추정하지 않는다. persistence 예측은 평평해서 "계속
  유지" 아니면 "이미 이탈"만 나오고, 이탈 탐지는 그룹B에서 단순 규칙보다 못하다
  (CLAUDE.md). 대신 현재 상태(대역 안/아래/위)가 몇 시간째 이어졌는지 실측으로 센다.
"""

from dataclasses import dataclass

import pandas as pd

from app.forecast import Predictor, build_features, feature_names
from app.switching import REFERENCE_ONLY_HORIZONS, HorizonStatus, State

ONE_HOUR = pd.Timedelta(hours=1)


def band_status(v: float, low: float, high: float) -> str:
    """경계 양쪽 포함 (캘린더·이탈 탐지 검증과 동일)."""
    if v < low:
        return "below"
    if v > high:
        return "above"
    return "in"


def current_run_hours(vpd: pd.Series, low: float, high: float) -> int:
    """마지막 정시의 대역 상태가 몇 정시째 이어졌는지. 빠진 정시가 있으면 거기서 끊는다."""
    vpd = vpd.dropna().sort_index()
    if vpd.empty:
        return 0
    status = band_status(vpd.iloc[-1], low, high)
    run, prev = 0, None
    for hour, v in zip(reversed(vpd.index), reversed(vpd.to_numpy())):
        if prev is not None and prev - hour != ONE_HOUR:
            break
        if band_status(v, low, high) != status:
            break
        run += 1
        prev = hour
    return run


@dataclass
class Forecast:
    horizon: int
    target_at: pd.Timestamp
    state: State  # 백테스트 자동 전환 상태 (Trust 화면과 같은 값)
    source: str  # "model" | "persistence" — 실제로 보여주는 값의 출처
    vpd: float
    band_status: str
    note: str = ""


def _model_value(hourly: pd.DataFrame, h: int, predictor: Predictor) -> float | None:
    """최신 정시 기준 모델 예측. t-2~t가 다 이어지고 CO2까지 있어야 한다."""
    latest = hourly.index.max()
    X = build_features(hourly.loc[latest - 2 * ONE_HOUR:], feature_names(h))
    if latest not in X.index:
        return None
    return float(predictor(h, X.loc[[latest]].to_numpy())[0])


def displayed_forecasts(
    hourly: pd.DataFrame,
    statuses: list[HorizonStatus],
    predictor: Predictor,
    low: float,
    high: float,
) -> list[Forecast]:
    latest = hourly.index.max()
    current = float(hourly["vpd"].loc[latest])
    out = []
    for st in statuses:
        h = st.horizon
        if h in REFERENCE_ONLY_HORIZONS:
            continue
        wants_model = st.state is State.MODEL
        value = _model_value(hourly, h, predictor) if wants_model else None
        if value is not None:
            source, note = "model", ""
        else:
            source = "persistence"
            if wants_model:
                note = "직전 3시간 중 빠진 정시나 CO2 결측이 있어 이번 정시는 현재 값을 씁니다"
            else:
                note = ""
            value = current
        value = max(value, 0.0)  # 모델이 0 근처에서 음수를 낼 수 있음. VPD는 음수가 없다
        out.append(Forecast(h, latest + h * ONE_HOUR, st.state, source,
                            value, band_status(value, low, high), note))
    return out
