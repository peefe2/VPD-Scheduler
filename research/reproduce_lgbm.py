"""지평별(+1h/+3h/+6h) LightGBM vs persistence, LOSO로 로컬 재현.

h=1은 colab_run_models_v1.ipynb Part B(논문 표2)와 같은 결과가 나와야 한다.
타깃·마스크는 onset_detection.py(원본 daytime_onset_detection.py)의 build(h)와
같다: t-1→t가 1시간 간격이고, 정확히 t+h 시각의 실측이 있는 행만.

입력: data/combined_hourly_pointsample.csv (노트북 Part A의 출력, Drive에서 받음)
실행: uv run --project ../backend python reproduce_lgbm.py [--raw]
  (--raw: 결함 행 포함 원본. 기본은 결함 제외본)
"""

import sys

import numpy as np
import pandas as pd
import lightgbm as lgb

RNG = 42
HORIZONS = (1, 3, 6)
BASE = ["temp", "humidity", "co2", "VPD"]
FEATURES = BASE + [f"{c}_lag1" for c in BASE] + [f"{c}_lag2" for c in BASE]
GH24 = {"gh24_1온실", "gh24_2온실", "gh24_3온실", "gh24_4온실"}
LGBM_PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=RNG, verbose=-1)
DATA = "data/combined_hourly_pointsample.csv"


def load_combined(clean: bool = True) -> pd.DataFrame:
    """통합 데이터를 읽는다. clean=True면 확인된 결함 행을 뺀다 (2026-10-12 결정).

    결함: gh24_1온실 2025-02-01~02-07 168시간은 습도 열에 온도 값이 복사돼 있다
    (temp == humidity). 다른 9곳에는 이런 행이 없다. 습도 99.9(센서 포화 의심)는
    실제 과습일 수 있어 빼지 않는다 — 빼면 가장 습한 조건을 들어내는 생존자 편향.
    """
    df = pd.read_csv(DATA, parse_dates=["date"])
    if clean:
        defect = (df["source"] == "gh24_1온실") & np.isclose(df["temp"], df["humidity"])
        assert defect.sum() == 168, f"예상과 다른 결함 행 수: {defect.sum()}"
        df = df[~defect].reset_index(drop=True)
    return df


def build_samples(df: pd.DataFrame, h: int = 1) -> pd.DataFrame:
    """lag 피처 + target(= 정확히 t+h 시각의 VPD). 보간 없이 이어진 구간만 남김."""
    df = df.sort_values(["source", "date"]).reset_index(drop=True)
    g = df.groupby("source")
    for lag in (1, 2):
        for c in BASE:
            df[f"{c}_lag{lag}"] = g[c].shift(lag)
    df["dt_back"] = g["date"].diff().dt.total_seconds() / 3600
    # 원본 노트북·스크립트와 같게 t-1→t 간격만 본다. t-2→t-1 간격은 확인하지
    # 않으므로 lag2가 1시간보다 먼 과거일 수 있다 (재현을 위해 그대로 둠).
    key = df.set_index(["source", "date"])["VPD"]
    idx = pd.MultiIndex.from_arrays([df["source"], df["date"] + pd.Timedelta(hours=h)])
    df["target_VPD"] = key.reindex(idx).values
    mask = (
        (df["dt_back"] == 1)
        & df[[f"{c}_lag2" for c in BASE]].notna().all(axis=1)
        & df["target_VPD"].notna()
    )
    return df[mask].reset_index(drop=True)


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def loso(s: pd.DataFrame) -> pd.DataFrame:
    X, y, src = s[FEATURES].values, s["target_VPD"].values, s["source"].values
    rows = []
    for held in np.unique(src):
        te = src == held
        if te.sum() < 30:  # 노트북과 동일한 제외 기준
            continue
        model = lgb.LGBMRegressor(**LGBM_PARAMS).fit(X[~te], y[~te])
        r_m = rmse(y[te], model.predict(X[te]))
        r_p = rmse(y[te], s["VPD"].values[te])
        rows.append(dict(source=held, n=int(te.sum()), lgbm=r_m, persist=r_p,
                         improve=(r_p - r_m) / r_p * 100,
                         group="B" if held in GH24 else "A"))
    return pd.DataFrame(rows)


def main():
    df = load_combined(clean="--raw" not in sys.argv)
    for h in HORIZONS:
        s = build_samples(df, h)
        res = loso(s)
        print(f"===== +{h}h (유효 샘플 {len(s)} / {len(df)}) =====")
        print(res.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        for grp, sub in res.groupby("group"):
            print(f"그룹{grp}: n={len(sub)}, 평균 개선율 {sub.improve.mean():+.1f}%, "
                  f"개선 {int((sub.improve > 0).sum())}곳")
        print()


if __name__ == "__main__":
    main()
