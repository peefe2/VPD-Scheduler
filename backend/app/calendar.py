"""캘린더: 날짜별 대역 안 시간 회고 (CSV만 연결한 온실·CO2 없는 온실도 사용 가능).

- 정시 실측만 센다. 측정이 없는 정시는 대역 안으로도 밖으로도 세지 않는다 —
  비율은 관측된 정시 기준이고, 관측 정시 수를 같이 돌려준다.
- 대역 경계는 양쪽 포함 (low <= VPD <= high, 이탈 탐지 검증 스크립트와 동일).
- 낮(DAYTIME_HOURS)과 밤(나머지 15시간)을 따로 낸다 (결정 2026-10-12):
  캘린더 칸 색은 낮 대역 안 비율, 밤은 "대역 아래" 비율을 별도 숫자로.
  "관리 가능한 낮 상태"와 "방치되는 밤 과습"을 한 숫자에 섞지 않기 위함.
- 데이터 충분 기준도 낮·밤 따로 (낮 6/9, 밤 10/15). 하루 전체 하나로 두면 낮이 꽉 차고
  밤이 반인 날과 그 반대가 똑같이 통과한다.
- 날짜 경계는 온실 현지 자정.
- 대역은 날짜마다 그날 유효했던 버전을 쓴다 (`app/bands.py`). low/high에 정시별 Series를
  넘길 수 있다.
"""

import pandas as pd

# 이탈 탐지 검증(research/onset_detection.py)의 '주간09-17' 창과 동일: 9시~17시 정시 9개.
# 고정 유지 (결정 2026-10-12): 일출·일몰 기반은 가을·겨울 데이터뿐이라 검증 근거가 없다.
DAYTIME_HOURS = range(9, 18)
MIN_DAY_HOURS = 6  # 낮 9시간 중
MIN_NIGHT_HOURS = 10  # 밤 15시간 중


def _counts(vpd: pd.Series, low, high, prefix: str) -> pd.DataFrame:
    df = pd.DataFrame({
        "observed": vpd.notna(),
        "in_band": vpd.between(low, high),
        "below": vpd < low,
        "above": vpd > high,
    }, index=vpd.index)
    out = df.groupby(vpd.index.normalize()).sum().astype(int)
    out.columns = [f"{prefix}{c}" for c in out.columns]
    return out


def daily_summary(vpd: pd.Series, low, high) -> pd.DataFrame:
    """vpd: 인덱스가 정시(현지 시각)인 VPD 시리즈. low/high: 숫자 또는 정시별 Series.
    반환: 날짜별 집계 (관측 있는 날만)."""
    vpd = vpd.dropna().sort_index()
    if vpd.empty:
        return pd.DataFrame()
    low = low.reindex(vpd.index) if isinstance(low, pd.Series) else pd.Series(float(low), index=vpd.index)
    high = high.reindex(vpd.index) if isinstance(high, pd.Series) else pd.Series(float(high), index=vpd.index)
    is_day = vpd.index.hour.isin(DAYTIME_HOURS)
    out = (
        _counts(vpd, low, high, "")
        .join(_counts(vpd[is_day], low[is_day], high[is_day], "day_"), how="left")
        .join(_counts(vpd[~is_day], low[~is_day], high[~is_day], "night_"), how="left")
        .fillna(0)
        .astype(int)
    )
    stats = vpd.groupby(vpd.index.normalize()).agg(["min", "max", "mean"])
    out["band_low"] = low.groupby(low.index.normalize()).first()
    out["band_high"] = high.groupby(high.index.normalize()).first()
    out["vpd_min"], out["vpd_max"], out["vpd_mean"] = stats["min"], stats["max"], stats["mean"]
    out["in_band_ratio"] = out["in_band"] / out["observed"]
    out["day_in_band_ratio"] = (out["day_in_band"] / out["day_observed"]).where(out["day_observed"] > 0)
    out["night_below_ratio"] = (out["night_below"] / out["night_observed"]).where(out["night_observed"] > 0)
    out["day_sufficient"] = out["day_observed"] >= MIN_DAY_HOURS
    out["night_sufficient"] = out["night_observed"] >= MIN_NIGHT_HOURS
    out.index.name = "date"
    return out
