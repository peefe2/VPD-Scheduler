from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app.switching import Bucket, HorizonStatus, State, Verdict
from app.today import band_status, current_run_hours, displayed_forecasts
from app.vpd import vpd
from tests.test_api import GREENHOUSE, client, engine  # noqa: F401  fixture 재사용


def hourly(n=6, start="2026-10-01 00:00", co2=400.0):
    idx = pd.date_range(start, periods=n, freq="h")
    t = np.full(n, 25.0)
    rh = np.full(n, 70.0)
    return pd.DataFrame({"temperature": t, "humidity": rh, "co2": co2, "vpd": vpd(t, rh)}, index=idx)


def fake_predictor(h, X):
    return np.full(len(X), 1.0 + h / 10)


def buckets(verdicts):
    return [Bucket(i, datetime(2026, 9, 1), datetime(2026, 9, 8), 100, 0.1, 0.2, 10.0, v)
            for i, v in enumerate(verdicts)]


def test_band_status_inclusive():
    assert [band_status(v, 0.5, 1.5) for v in (0.49, 0.5, 1.5, 1.51)] == ["below", "in", "in", "above"]


def test_run_hours_stops_at_gap_and_status_change():
    idx = pd.to_datetime(["2026-10-01 00:00", "2026-10-01 02:00", "2026-10-01 03:00", "2026-10-01 04:00"])
    s = pd.Series([0.3, 0.3, 0.8, 0.9], index=idx)
    assert current_run_hours(s, 0.5, 1.5) == 2
    s = pd.Series([0.3, 0.3, 0.3, 0.3], index=idx)
    assert current_run_hours(s, 0.5, 1.5) == 3  # 01시가 비어 있어 거기서 끊음


def test_model_state_uses_model_value():
    st = [HorizonStatus(1, State.MODEL), HorizonStatus(3, State.PERSISTENCE)]
    f1, f3 = displayed_forecasts(hourly(), st, fake_predictor, 0.5, 1.5)
    assert (f1.source, f1.vpd) == ("model", pytest.approx(1.1))
    assert f1.target_at == pd.Timestamp("2026-10-01 06:00")
    assert f3.source == "persistence" and f3.vpd == pytest.approx(hourly()["vpd"].iloc[-1])


def test_model_state_falls_back_when_lag_missing():
    df = hourly().drop(pd.Timestamp("2026-10-01 04:00"))
    (f,) = displayed_forecasts(df, [HorizonStatus(1, State.MODEL)], fake_predictor, 0.5, 1.5)
    assert f.source == "persistence" and f.note


def test_model_state_falls_back_without_co2():
    df = hourly()
    df.loc[df.index[-1], "co2"] = np.nan
    (f,) = displayed_forecasts(df, [HorizonStatus(1, State.MODEL)], fake_predictor, 0.5, 1.5)
    assert f.source == "persistence"


def test_reference_horizon_not_displayed():
    # +6h는 검증용 — 이 온실 +6h 버킷이 연속 개선이어도 오늘 화면에는 내보내지 않는다 (2026-11-07)
    st = [HorizonStatus(1, State.MODEL), HorizonStatus(6, State.REFERENCE, buckets([Verdict.BETTER] * 5))]
    assert [f.horizon for f in displayed_forecasts(hourly(), st, fake_predictor, 0.5, 1.5)] == [1]


def test_negative_model_value_clipped():
    (f,) = displayed_forecasts(hourly(), [HorizonStatus(1, State.MODEL)],
                               lambda h, X: np.array([-0.02]), 0.5, 1.5)
    assert f.vpd == 0.0 and f.band_status == "below"


# --- API ---

API_GH = {**GREENHOUSE, "connection_type": "api"}


def post(client, gh_id, *ms):
    """토큰을 새로 발급해 보낸다 (CSV 온실은 발급이 409라 토큰 없이 보내서 409를 확인)."""
    issued = client.post(f"/greenhouses/{gh_id}/ingest-token")
    headers = {"Authorization": f"Bearer {issued.json()['token']}"} if issued.status_code == 200 else {}
    return client.post(f"/greenhouses/{gh_id}/ingest", json={"measurements": list(ms)}, headers=headers)


def m(at, t=25.0, rh=70.0, co2=None):
    return {"measured_at": at, "temperature": t, "humidity": rh, "co2": co2}


def test_ingest_requires_api_connection(client):  # noqa: F811
    gh = client.post("/greenhouses", json=GREENHOUSE).json()
    assert post(client, gh["id"], m("2026-10-01T10:00:00")).status_code == 409


def test_ingest_replay_requires_holdout(client):  # noqa: F811
    gh = client.post("/greenhouses", json={**GREENHOUSE, "connection_type": "replay"}).json()
    assert post(client, gh["id"], m("2026-10-01T10:00:00")).status_code == 409
    client.patch(f"/greenhouses/{gh['id']}", json={"holdout_source": "gh24_2온실"})
    assert post(client, gh["id"], m("2026-10-01T10:00:00")).status_code == 200


def test_ingest_keeps_first_measurement_of_hour(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    res = post(client, gh["id"],
               m("2026-10-01T10:05:00", t=21), m("2026-10-01T10:02:00", t=20),
               m("2026-10-01T11:30:00"), m("2026-10-01T12:00:00", rh=101))
    assert res.json() == {"stored": 1, "replaced": 0, "ignored_not_first": 1,
                          "rejected_late": 1, "rejected_humidity_out_of_range": 1}
    # 더 이른 측정이 늦게 도착하면 교체
    res = post(client, gh["id"], m("2026-10-01T10:00:30", t=19))
    assert res.json()["replaced"] == 1
    rows = client.get(f"/greenhouses/{gh['id']}/readings?start=2026-10-01&end=2026-10-01").json()
    assert [(r["hour"], r["temperature"]) for r in rows] == [("2026-10-01T10:00:00", 19.0)]


def test_ingest_sets_has_co2(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    post(client, gh["id"], m("2026-10-01T10:00:00"))
    assert client.get(f"/greenhouses/{gh['id']}").json()["has_co2"] is False
    post(client, gh["id"], m("2026-10-01T11:00:00", co2=450))
    assert client.get(f"/greenhouses/{gh['id']}").json()["has_co2"] is True


def test_today_empty_and_learning(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    body = client.get(f"/greenhouses/{gh['id']}/today").json()
    assert body["latest"] is None and body["forecasts"] == []

    post(client, gh["id"], *[m(f"2026-10-01T{h:02d}:00:00", rh=60 + h, co2=450) for h in range(6)])
    body = client.get(f"/greenhouses/{gh['id']}/today").json()
    assert body["latest"]["hour"] == "2026-10-01T05:00:00"
    assert body["basis"] == "persistence"
    assert [(f["horizon"], f["state"], f["source"]) for f in body["forecasts"]] == [
        (1, "learning", "persistence"), (3, "learning", "persistence")]  # +6h는 검증용이라 없음
    assert body["forecasts"][0]["target_at"] == "2026-10-01T06:00:00"
    assert body["run_hours"] >= 1
