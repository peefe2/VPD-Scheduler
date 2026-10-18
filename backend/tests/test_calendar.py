import json

import numpy as np
import pandas as pd
import pytest

from app.calendar import daily_summary
from tests.test_api import client, engine, make_greenhouse, upload  # noqa: F401


def series(values, start="2026-10-01 00:00"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="h"), dtype=float)


def test_boundaries_inclusive_and_split():
    s = series([0.79, 0.8, 1.0, 1.2, 1.21, np.nan])
    r = daily_summary(s, 0.8, 1.2).iloc[0]
    assert (r.observed, r.in_band, r.below, r.above) == (5, 3, 1, 1)
    assert r.in_band_ratio == pytest.approx(3 / 5)  # 결측 정시는 분모에서 빠짐


def test_daytime_window_9_to_17():
    v = [0.5] * 24
    for h in range(9, 18):
        v[h] = 1.0
    r = daily_summary(series(v), 0.8, 1.2).iloc[0]
    assert (r.observed, r.in_band) == (24, 9)
    assert (r.day_observed, r.day_in_band, r.day_in_band_ratio) == (9, 9, 1.0)


def test_days_split_at_local_midnight():
    out = daily_summary(series([1.0] * 30, start="2026-10-01 00:00"), 0.8, 1.2)
    assert list(out.observed) == [24, 6]


def test_night_only_day_has_no_daytime_ratio():
    out = daily_summary(series([1.0] * 5, start="2026-10-01 00:00"), 0.8, 1.2)
    assert out.iloc[0].day_observed == 0 and pd.isna(out.iloc[0].day_in_band_ratio)


def test_calendar_endpoint_uses_greenhouse_band_and_range(client):  # noqa: F811
    gh = client.post("/greenhouses", json={"name": "1동", "crop": "토마토",
                                           "vpd_low": 0.8, "vpd_high": 1.2}).json()
    rows = ["t,T,RH"]
    for d in (1, 2, 3):
        for h in range(24):
            rows.append(f"2026-10-0{d} {h:02d}:00,25,60")  # VPD ≈ 1.27 kPa
    mapping = {"timestamp": "t", "temperature": "T", "humidity": "RH"}
    client.post(f"/greenhouses/{gh['id']}/csv/import", files=upload("\n".join(rows)),
                data={"mapping": json.dumps(mapping)})

    body = client.get(f"/greenhouses/{gh['id']}/calendar").json()
    assert [d["date"] for d in body["days"]] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert body["days"][0]["hours_above"] == 24 and body["days"][0]["hours_in_band"] == 0
    assert body["daytime_hours"] == [9, 17]
    assert body["min_hours"] == {"daytime": 6, "night": 10}
    assert body["days"][0]["night"]["hours_observed"] == 15
    assert body["days"][0]["daytime"]["sufficient"] is True

    client.patch(f"/greenhouses/{gh['id']}", json={"vpd_high": 1.5})
    body = client.get(f"/greenhouses/{gh['id']}/calendar", params={"start": "2026-10-02", "end": "2026-10-02"}).json()
    assert [d["date"] for d in body["days"]] == ["2026-10-02"]
    assert body["days"][0]["hours_in_band"] == 24 and body["days"][0]["daytime"]["in_band_ratio"] == 1.0

    assert client.get(f"/greenhouses/{gh['id']}/calendar", params={"start": "2026-10-03", "end": "2026-10-01"}).status_code == 422


def test_night_badge_and_separate_sufficiency():
    v = [0.3] * 24  # 밤 15시간 전부 대역 아래
    for h in range(9, 18):
        v[h] = 1.0
    r = daily_summary(series(v), 0.8, 1.2).iloc[0]
    assert (r.night_observed, r.night_below, r.night_below_ratio) == (15, 15, 1.0)
    assert r.day_sufficient and r.night_sufficient


def test_sufficiency_not_shared_between_day_and_night():
    # 낮은 꽉 차고 밤은 7시간뿐인 날 vs 낮 5시간 + 밤 꽉 찬 날: 전체로는 둘 다 16~20시간
    full_day_half_night = series([1.0] * 24).drop(series([1.0] * 24).index[[0, 1, 2, 3, 4, 5, 6, 18]])
    r = daily_summary(full_day_half_night, 0.8, 1.2).iloc[0]
    assert r.observed == 16 and r.day_sufficient and not r.night_sufficient

    s = series([1.0] * 24)
    half_day = s.drop(s.index[[9, 10, 11, 12]])
    r = daily_summary(half_day, 0.8, 1.2).iloc[0]
    assert r.observed == 20 and not r.day_sufficient and r.night_sufficient


def test_readings_endpoint_range_and_gaps(client):  # noqa: F811
    gh = make_greenhouse(client)
    rows = ["t,T,RH", "2026-10-01 00:00,20,60", "2026-10-01 02:00,21,60", "2026-10-02 00:00,22,60"]
    mapping = {"timestamp": "t", "temperature": "T", "humidity": "RH"}
    client.post(f"/greenhouses/{gh['id']}/csv/import", files=upload("\n".join(rows)),
                data={"mapping": json.dumps(mapping)})
    body = client.get(f"/greenhouses/{gh['id']}/readings", params={"start": "2026-10-01", "end": "2026-10-01"}).json()
    assert [r["hour"] for r in body] == ["2026-10-01T00:00:00", "2026-10-01T02:00:00"]  # 01시는 비어 있음
    assert body[0]["co2"] is None
    too_long = client.get(f"/greenhouses/{gh['id']}/readings", params={"start": "2026-01-01", "end": "2026-03-01"})
    assert too_long.status_code == 422
