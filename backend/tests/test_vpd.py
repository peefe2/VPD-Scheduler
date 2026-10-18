import math

import pandas as pd
import pytest

from app.vpd import hourly_first, svp, vpd


def test_svp_known_values():
    # Tetens 식 기준값: 20°C ≈ 2.338 kPa, 25°C ≈ 3.168 kPa
    assert svp(20) == pytest.approx(2.338, abs=1e-3)
    assert svp(25) == pytest.approx(3.168, abs=1e-3)


def test_vpd_formula():
    assert vpd(25, 60) == pytest.approx(svp(25) * 0.4)
    assert vpd(25, 100) == pytest.approx(0)
    assert vpd(25, 0) == pytest.approx(svp(25))


def _frame(rows):
    df = pd.DataFrame(rows, columns=["ts", "temperature", "humidity", "co2"])
    return df.set_index(pd.to_datetime(df.pop("ts")))


def test_hourly_first_takes_first_not_mean():
    df = _frame([
        ("2026-10-01 10:00", 20.0, 60.0, 400.0),
        ("2026-10-01 10:30", 30.0, 40.0, 500.0),
    ])
    out = hourly_first(df, ["temperature", "humidity"])
    assert len(out) == 1
    assert out.iloc[0]["temperature"] == 20.0
    assert out.iloc[0]["humidity"] == 60.0


def test_hourly_first_keeps_row_together():
    # 열별 first()였다면 온도 10:00 + 습도 10:05가 섞인다
    df = _frame([
        ("2026-10-01 10:00", 20.0, math.nan, 400.0),
        ("2026-10-01 10:05", 22.0, 55.0, 410.0),
    ])
    out = hourly_first(df, ["temperature", "humidity"])
    row = out.iloc[0]
    assert (row["temperature"], row["humidity"], row["co2"]) == (22.0, 55.0, 410.0)
    assert row["measured_at"] == pd.Timestamp("2026-10-01 10:05")


def test_hourly_first_drops_late_measurement():
    df = _frame([
        ("2026-10-01 10:45", 20.0, 60.0, 400.0),
        ("2026-10-01 11:02", 21.0, 61.0, 400.0),
    ])
    out = hourly_first(df, ["temperature", "humidity"])
    assert list(out.index) == [pd.Timestamp("2026-10-01 11:00")]


def test_hourly_first_unsorted_input():
    df = _frame([
        ("2026-10-01 10:20", 25.0, 50.0, 400.0),
        ("2026-10-01 10:01", 20.0, 60.0, 400.0),
    ])
    out = hourly_first(df, ["temperature", "humidity"], max_lag=pd.Timedelta(minutes=30))
    assert out.iloc[0]["temperature"] == 20.0
