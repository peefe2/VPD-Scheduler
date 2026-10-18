import numpy as np
import pandas as pd
import pytest

from app.forecast import HORIZONS, backtest_samples, build_features, feature_names, lgbm_predict
from app.vpd import vpd

FEATS = ["temp", "humidity", "co2", "VPD",
         "temp_lag1", "humidity_lag1", "co2_lag1", "VPD_lag1",
         "temp_lag2", "humidity_lag2", "co2_lag2", "VPD_lag2"]


def hourly(n=10, start="2026-10-01 00:00"):
    idx = pd.date_range(start, periods=n, freq="h")
    t = 20 + np.arange(n, dtype=float)
    rh = np.full(n, 60.0)
    return pd.DataFrame({"temperature": t, "humidity": rh, "co2": 400.0, "vpd": vpd(t, rh)}, index=idx)


def test_feature_order_matches_trained_models():
    for h in HORIZONS:
        assert feature_names(h) == FEATS


def test_build_features_uses_exact_lags():
    X = build_features(hourly(5), FEATS)
    assert len(X) == 3  # 처음 두 정시는 lag2가 없음
    row = X.iloc[0]
    assert (row.temp, row.temp_lag1, row.temp_lag2) == (22.0, 21.0, 20.0)


def test_build_features_requires_t_minus_2_contiguous():
    # 원본 학습 마스크와 달리 t-2→t-1 간격도 확인한다
    df = hourly(6).drop(pd.Timestamp("2026-10-01 01:00"))
    X = build_features(df, FEATS)
    assert pd.Timestamp("2026-10-01 02:00") not in X.index
    assert pd.Timestamp("2026-10-01 03:00") not in X.index
    assert pd.Timestamp("2026-10-01 04:00") in X.index


def test_build_features_requires_co2():
    df = hourly(5)
    df.loc[pd.Timestamp("2026-10-01 03:00"), "co2"] = np.nan
    X = build_features(df, FEATS)
    assert list(X.index) == [pd.Timestamp("2026-10-01 02:00")]


def test_backtest_samples_target_exactly_h_later():
    calls = {}

    def fake(h, X):
        calls["shape"] = X.shape
        return np.zeros(len(X))

    s = backtest_samples(hourly(10), 3, predictor=fake, features=FEATS)
    # t=2..9 피처 가능, t+3 <= 9 → t=2..6
    assert list(s.issued_at.dt.hour) == [2, 3, 4, 5, 6]
    assert (s.target_at - s.issued_at == pd.Timedelta(hours=3)).all()
    assert s.persistence.iloc[0] == pytest.approx(vpd(22.0, 60.0))
    assert s.actual.iloc[0] == pytest.approx(vpd(25.0, 60.0))
    assert calls["shape"] == (5, 12)


def test_real_models_predict_plausible_vpd():
    X = build_features(hourly(5), FEATS).to_numpy()
    for h in HORIZONS:
        p = lgbm_predict(h, X)
        assert p.shape == (3,)
        assert np.all((p > -0.5) & (p < 5))


def test_loso_models_differ_from_deployed():
    from app.forecast import predictor_for

    X = build_features(hourly(5), FEATS).to_numpy()
    deployed, name = predictor_for(None)
    loso, loso_name = predictor_for("gh24_2온실")
    assert (name, loso_name) == ("deployed", "loso:gh24_2온실")
    for h in HORIZONS:
        assert not np.allclose(deployed(h, X), loso(h, X))
