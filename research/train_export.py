"""서비스용 지평별(+1h/+3h/+6h) LightGBM 모델을 10개 온실 전체로 학습해 backend/models/에 저장.

하이퍼파라미터·피처·전처리는 colab_run_models_v1.ipynb와 동일. 서비스 화면에
쓸 성능 수치는 이 모델이 아니라 LOSO 재현값(reproduce_lgbm.py)을 쓴다 — 이
모델은 학습에 모든 온실을 봤으므로 같은 데이터로 잰 성능은 낙관적이다.

실행: uv run --project ../backend python train_export.py
"""

import hashlib
import json
from datetime import date
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from reproduce_lgbm import FEATURES, HORIZONS, LGBM_PARAMS, build_samples, load_combined

DATA = Path("data/combined_hourly_pointsample.csv")
OUT = Path("../backend/models")


# LOSO 재현값 (reproduce_lgbm.py, 결함 제외본, 2026-10-12). 화면에는 이 값만 쓴다.
LOSO_NOTE = {
    1: "그룹A +9.7%(6곳 중 5곳 개선), 그룹B -10.9%(0곳)",
    3: "그룹A +17.2%(6곳 중 5곳 개선), 그룹B -16.9%(0곳)",
    6: "그룹A +21.3%(6곳 중 6곳 개선), 그룹B -14.5%(0곳). 참고용: 전환 판정 제외",
}
EXCLUDED = "gh24_1온실 2025-02-01~02-07 168행 (습도 열에 온도 복사)"


def export(df: pd.DataFrame, h: int) -> None:
    s = build_samples(df, h)
    X, y = s[FEATURES].values, s["target_VPD"].values
    model = lgb.LGBMRegressor(**LGBM_PARAMS).fit(X, y)

    model_path = OUT / f"vpd_lgbm_h{h}.txt"
    model.booster_.save_model(str(model_path))

    # 서비스는 sklearn 없이 Booster로 읽는다 — 같은 예측이 나오는지 확인
    reloaded = lgb.Booster(model_file=str(model_path))
    assert np.allclose(reloaded.predict(X), model.predict(X))

    meta = {
        "horizon_hours": h,
        "features": FEATURES,
        "params": LGBM_PARAMS,
        "train_rows": int(len(s)),
        "train_sources": sorted(s["source"].unique().tolist()),
        "data_file": DATA.name,
        "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
        "excluded_rows": EXCLUDED,
        "trained_on": date.today().isoformat(),
        "loso_improvement": LOSO_NOTE[h],
    }
    (OUT / f"vpd_lgbm_h{h}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {model_path} ({len(s)} rows)")


def export_loso(df: pd.DataFrame) -> None:
    """데모용: 학습 온실마다 그 온실을 뺀 모델. 학습 온실 데이터를 서비스에 올려
    백테스트할 때 in-sample 누수 없이 보여주기 위함 (CLAUDE.md "하지 말 것")."""
    loso_dir = OUT / "loso"
    loso_dir.mkdir(parents=True, exist_ok=True)
    samples = {h: build_samples(df, h) for h in HORIZONS}
    sources = sorted(df["source"].unique().tolist())
    index = {"sources": {}, "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
             "excluded_rows": EXCLUDED,
             "trained_on": date.today().isoformat()}
    for i, source in enumerate(sources):
        index["sources"][source] = {"key": f"s{i}", "history_start": str(df[df.source == source].date.min()),
                                    "history_end": str(df[df.source == source].date.max())}
        for h in HORIZONS:
            s = samples[h]
            tr = s["source"] != source
            model = lgb.LGBMRegressor(**LGBM_PARAMS).fit(s.loc[tr, FEATURES].values, s.loc[tr, "target_VPD"].values)
            model.booster_.save_model(str(loso_dir / f"h{h}_s{i}.txt"))
        print(f"loso {source} -> s{i}")
    (loso_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    df = load_combined(clean=True)  # 확인된 결함 168행 제외 (서비스 모델은 무조건 제외본)
    OUT.mkdir(parents=True, exist_ok=True)
    for h in HORIZONS:
        export(df, h)
    export_loso(df)


if __name__ == "__main__":
    main()
