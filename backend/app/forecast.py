"""사전 학습된 지평별 LightGBM으로 VPD 예측, 백테스트 표본 생성.

모델·피처 순서는 research/train_export.py가 만든 models/vpd_lgbm_h{h}.json을 따른다.
학습 코드(원본 노트북)는 t-1→t 간격만 확인했지만, 서비스는 t-2, t-1, t 세 정시가
모두 이어지고 CO2까지 있을 때만 모델을 쓴다 (CLAUDE.md "원본 전처리 주의점").
"""

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
HORIZONS = (1, 3, 6)

# 학습 데이터 열 이름 → Reading 열 이름
_COLUMN = {"temp": "temperature", "humidity": "humidity", "co2": "co2", "VPD": "vpd"}

Predictor = Callable[[int, np.ndarray], np.ndarray]


def _booster(path: Path) -> lgb.Booster:
    # model_file로 경로를 넘기면 Windows에서 LightGBM(C++)이 한글 등 비ASCII 경로를 열지 못한다.
    # 파일은 Python이 읽고 내용만 넘긴다.
    return lgb.Booster(model_str=path.read_text(encoding="utf-8"))


@lru_cache
def _load(h: int) -> tuple[lgb.Booster, list[str]]:
    meta = json.loads((MODELS_DIR / f"vpd_lgbm_h{h}.json").read_text(encoding="utf-8"))
    booster = _booster(MODELS_DIR / f"vpd_lgbm_h{h}.txt")
    return booster, meta["features"]


def feature_names(h: int) -> list[str]:
    return _load(h)[1]


def lgbm_predict(h: int, X: np.ndarray) -> np.ndarray:
    return _load(h)[0].predict(X)


@lru_cache
def loso_sources() -> dict[str, str]:
    """학습 온실 이름 → LOSO 모델 키 (models/loso/index.json)."""
    path = MODELS_DIR / "loso" / "index.json"
    if not path.exists():
        return {}
    index = json.loads(path.read_text(encoding="utf-8"))
    return {name: info["key"] for name, info in index["sources"].items()}


@lru_cache
def _load_loso(h: int, key: str) -> lgb.Booster:
    return _booster(MODELS_DIR / "loso" / f"h{h}_{key}.txt")


def predictor_for(holdout_source: str | None) -> tuple[Predictor, str]:
    """백테스트에 쓸 예측기와 그 이름. holdout_source가 있으면 그 온실을 뺀 모델."""
    if holdout_source is None:
        return lgbm_predict, "deployed"
    key = loso_sources()[holdout_source]
    return (lambda h, X: _load_loso(h, key).predict(X)), f"loso:{holdout_source}"


def build_features(hourly: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """정시 실측(인덱스=hour)에서 피처 행렬을 만든다. 쓸 수 없는 행은 빠진다.

    t, t-1, t-2 세 정시가 모두 있어야 하고(보간 없음), CO2를 포함한 네 변수가
    세 시점 모두 결측이 아니어야 한다.
    """
    hourly = hourly.sort_index()
    out = pd.DataFrame(index=hourly.index)
    for name in features:
        base, _, lag = name.partition("_lag")
        shift = pd.Timedelta(hours=int(lag) if lag else 0)
        col = hourly[_COLUMN[base]]
        out[name] = col.reindex(hourly.index - shift).to_numpy()
    return out.dropna()


def backtest_samples(
    hourly: pd.DataFrame, h: int, predictor: Predictor | None = None,
    features: list[str] | None = None,
) -> pd.DataFrame:
    """그 온실의 실측에 모델과 persistence를 적용한 표본.

    반환 열: issued_at(t), target_at(t+h), actual, model, persistence.
    정확히 t+h 시각의 실측이 있는 행만 남는다.
    """
    predictor = predictor or lgbm_predict
    features = features or feature_names(h)
    X = build_features(hourly, features)
    vpd = hourly["vpd"].sort_index()
    target_at = X.index + pd.Timedelta(hours=h)
    actual = vpd.reindex(target_at).to_numpy()
    keep = ~np.isnan(actual)
    X = X[keep]
    if X.empty:
        return pd.DataFrame(columns=["issued_at", "target_at", "actual", "model", "persistence"])
    return pd.DataFrame({
        "issued_at": X.index,
        "target_at": target_at[keep],
        "actual": actual[keep],
        "model": predictor(h, X.to_numpy()),
        "persistence": vpd.reindex(X.index).to_numpy(),
    }).reset_index(drop=True)
