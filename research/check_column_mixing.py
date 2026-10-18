"""원본 1~5분 CSV에서 열별 resample('1h').first()가 실제로 온도·습도를 다른
시각에서 가져오는지 센다.

정시마다 "온도의 첫 비결측 시각"과 "습도의 첫 비결측 시각"을 비교해, 다르면
섞인 것으로 본다. 섞인 정시는 행 단위 first(둘 다 있는 첫 행)와 VPD 차이도 잰다.

실행: uv run --project ../backend python check_column_mixing.py <csv> <date열> <온도열> <습도열>
"""

import sys

import numpy as np
import pandas as pd


def vpd(t, rh):
    s = 0.6108 * np.exp(17.27 * t / (t + 237.3))
    return s - s * rh / 100


def analyze(path, date_col, temp_col, hum_col):
    df = pd.read_csv(path, low_memory=False, usecols=[date_col, temp_col, hum_col])
    df = df.rename(columns={date_col: "date", temp_col: "temp", hum_col: "humidity"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    for c in ("temp", "humidity"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    n_rows = len(df)
    only_one = df["temp"].notna() ^ df["humidity"].notna()
    print(f"원본 행 {n_rows}, 온도·습도 중 하나만 있는 행 {int(only_one.sum())} "
          f"({only_one.mean() * 100:.3f}%)")

    ts = df.index.to_series()
    t_time = ts.where(df["temp"].notna()).resample("1h").first()
    h_time = ts.where(df["humidity"].notna()).resample("1h").first()

    # 원본 노트북 방식 (열별)
    colwise = df.resample("1h").first().dropna(subset=["temp", "humidity"])
    hours = colwise.index
    mixed = (t_time.reindex(hours) != h_time.reindex(hours))
    print(f"정시 {len(hours)}개 중 온도·습도 시각이 다른 정시 {int(mixed.sum())} "
          f"({mixed.mean() * 100:.2f}%)")

    if mixed.any():
        both = df.dropna(subset=["temp", "humidity"])
        rowwise = both.groupby(both.index.floor("h")).head(1)
        rowwise.index = rowwise.index.floor("h")
        m_hours = hours[mixed.values]
        a = colwise.loc[m_hours]
        b = rowwise.reindex(m_hours)
        diff = (vpd(a.temp, a.humidity) - vpd(b.temp, b.humidity)).abs()
        lag = (t_time.reindex(m_hours) - h_time.reindex(m_hours)).abs()
        print(f"  섞인 정시의 두 측정 시각 차: 중앙 {lag.median()}, 최대 {lag.max()}")
        print(f"  섞인 정시의 VPD 차(열별 vs 행 단위): 중앙 {diff.median():.4f}, "
              f"최대 {diff.max():.4f} kPa")
        print("  예시:")
        print(pd.DataFrame({"temp_at": t_time.reindex(m_hours[:5]),
                            "hum_at": h_time.reindex(m_hours[:5])}).to_string())


if __name__ == "__main__":
    analyze(*sys.argv[1:5])
