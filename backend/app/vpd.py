"""VPD 계산과 정시 리샘플링.

CLAUDE.md "VPD 계산" 절의 계약을 그대로 구현한다. 정시 값은 평균이 아니라
매 정시의 첫 측정값이다 (평균을 쓰면 RMSE 개선율이 부풀려짐).
"""

import numpy as np
import pandas as pd

# CLAUDE.md TODO: 정시로부터 허용 지연은 아직 미정. 임시로 10분.
DEFAULT_MAX_LAG = pd.Timedelta(minutes=10)


def svp(temp_c):
    """포화수증기압(kPa). temp_c: 섭씨."""
    return 0.6108 * np.exp(17.27 * temp_c / (temp_c + 237.3))


def vpd(temp_c, rh_pct):
    """수증기압차(kPa) = SVP - AVP. rh_pct: 0~100(%)."""
    s = svp(temp_c)
    return s - s * rh_pct / 100


def hourly_first(
    df: pd.DataFrame,
    required: list[str],
    max_lag: pd.Timedelta = DEFAULT_MAX_LAG,
) -> pd.DataFrame:
    """분 단위 측정을 정시 실측값으로 줄인다.

    df: DatetimeIndex를 가진 측정값.
    required: 한 행 안에 모두 있어야 하는 열 (온도·습도). 이 열들이 다 있는 행
      중 각 정시 구간의 첫 행을 통째로 고른다. 열마다 따로 first()를 하면
      온도는 10:00, 습도는 10:20 값이 섞일 수 있어서 그렇게 하지 않는다.
    max_lag: 정시로부터 이보다 늦은 첫 측정은 그 정시의 실측으로 인정하지 않는다.

    반환: 인덱스가 정시인 DataFrame. 'measured_at'에 실제 측정 시각이 남는다.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("df must have a DatetimeIndex")

    complete = df.dropna(subset=required).sort_index()
    complete = complete[~complete.index.duplicated(keep="first")]
    if complete.empty:
        return complete.assign(measured_at=pd.Series(dtype="datetime64[ns]"))

    hours = complete.index.floor("h")
    first = complete.groupby(hours).head(1)
    first = first.assign(measured_at=first.index)
    first.index = first.index.floor("h")
    first.index.name = "hour"

    return first[first["measured_at"] - first.index <= max_lag]
