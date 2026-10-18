import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app
from app.models import Reading


@pytest.fixture
def engine():
    from app import models  # noqa: F401

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(engine):
    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


GREENHOUSE = {
    "name": "1동",
    "crop": "토마토",
    "equipment": ["vent", "humidifier"],
}


def make_greenhouse(client):
    res = client.post("/greenhouses", json=GREENHOUSE)
    assert res.status_code == 201
    return res.json()


def test_create_uses_default_band(client):
    gh = make_greenhouse(client)
    assert (gh["vpd_low"], gh["vpd_high"]) == (0.5, 1.5)
    assert gh["has_co2"] is False
    assert gh["connection_type"] == "csv"


def test_create_rejects_inverted_band(client):
    res = client.post("/greenhouses", json={**GREENHOUSE, "vpd_low": 1.2, "vpd_high": 0.8})
    assert res.status_code == 422


def test_create_rejects_unknown_equipment(client):
    res = client.post("/greenhouses", json={**GREENHOUSE, "equipment": ["sprinkler"]})
    assert res.status_code == 422


def test_update_checks_band_against_stored_value(client):
    gh = make_greenhouse(client)
    res = client.patch(f"/greenhouses/{gh['id']}", json={"vpd_low": 1.5})
    assert res.status_code == 422
    res = client.patch(f"/greenhouses/{gh['id']}", json={"vpd_low": 0.5, "vpd_high": 1.5})
    assert res.status_code == 200
    assert res.json()["vpd_high"] == 1.5


def test_delete_then_404(client):
    gh = make_greenhouse(client)
    assert client.delete(f"/greenhouses/{gh['id']}").status_code == 204
    assert client.get(f"/greenhouses/{gh['id']}").status_code == 404


CSV = (
    "측정일시,내부온도,내부습도,CO2\n"
    "2026-10-01 10:00,20,60,400\n"
    "2026-10-01 10:30,30,40,500\n"
    "2026-10-01 11:50,21,61,410\n"
    "2026-10-01 12:03,22,150,420\n"
    "2026-10-01 12:04,22,62,420\n"
    "not-a-date,1,1,1\n"
)


def upload(text, encoding="utf-8"):
    return {"file": ("data.csv", text.encode(encoding), "text/csv")}


def test_preview_guesses_korean_columns(client):
    gh = make_greenhouse(client)
    res = client.post(f"/greenhouses/{gh['id']}/csv/preview", files=upload(CSV, "cp949"))
    assert res.status_code == 200
    body = res.json()
    assert body["guessed_mapping"] == {
        "timestamp": "측정일시",
        "temperature": "내부온도",
        "humidity": "내부습도",
        "co2": "CO2",
    }
    assert body["total_rows"] == 6


def test_import_hourly_first_and_report(client, engine):
    gh = make_greenhouse(client)
    mapping = {"timestamp": "측정일시", "temperature": "내부온도", "humidity": "내부습도", "co2": "CO2"}
    res = client.post(
        f"/greenhouses/{gh['id']}/csv/import",
        files=upload(CSV),
        data={"mapping": json.dumps(mapping)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["rows_read"] == 6
    assert body["rows_bad_timestamp"] == 1
    assert body["rows_humidity_out_of_range"] == 1
    # 10시(10:00) · 12시(12:04) 저장, 11시는 11:50이라 지연 초과로 제외
    assert body["hours_imported"] == 2
    assert body["hours_skipped_late"] == 1
    assert body["co2_included"] is True
    assert body["enough_history"] is False

    with Session(engine) as session:
        rows = session.exec(select(Reading).order_by(Reading.hour)).all()
    assert [r.temperature for r in rows] == [20.0, 22.0]
    assert rows[1].humidity == 62.0

    assert client.get(f"/greenhouses/{gh['id']}").json()["has_co2"] is True


def test_import_without_co2_keeps_has_co2_false(client):
    gh = make_greenhouse(client)
    mapping = {"timestamp": "측정일시", "temperature": "내부온도", "humidity": "내부습도"}
    res = client.post(
        f"/greenhouses/{gh['id']}/csv/import",
        files=upload(CSV),
        data={"mapping": json.dumps(mapping)},
    )
    assert res.status_code == 200
    assert res.json()["co2_included"] is False
    assert client.get(f"/greenhouses/{gh['id']}").json()["has_co2"] is False


def test_reimport_replaces_same_hour(client, engine):
    gh = make_greenhouse(client)
    mapping = {"timestamp": "t", "temperature": "T", "humidity": "RH"}
    url = f"/greenhouses/{gh['id']}/csv/import"
    client.post(url, files=upload("t,T,RH\n2026-10-01 10:00,20,60\n"), data={"mapping": json.dumps(mapping)})
    client.post(url, files=upload("t,T,RH\n2026-10-01 10:00,25,50\n"), data={"mapping": json.dumps(mapping)})
    with Session(engine) as session:
        rows = session.exec(select(Reading)).all()
    assert len(rows) == 1 and rows[0].temperature == 25.0


def test_import_rejects_missing_column(client):
    gh = make_greenhouse(client)
    mapping = {"timestamp": "측정일시", "temperature": "없는열", "humidity": "내부습도"}
    res = client.post(
        f"/greenhouses/{gh['id']}/csv/import",
        files=upload(CSV),
        data={"mapping": json.dumps(mapping)},
    )
    assert res.status_code == 422


def long_csv(days, with_co2=True):
    import numpy as np
    import pandas as pd

    idx = pd.date_range("2026-09-01", periods=days * 24, freq="h")
    hour = idx.hour.to_numpy()
    t = 18 + 8 * np.sin((hour - 6) / 24 * 2 * np.pi)
    rh = 75 - 15 * np.sin((hour - 6) / 24 * 2 * np.pi)
    df = pd.DataFrame({"t": idx.strftime("%Y-%m-%d %H:%M"), "T": t.round(2), "RH": rh.round(1)})
    if with_co2:
        df["CO2"] = 450
    return df.to_csv(index=False)


@pytest.mark.parametrize("with_co2, expected", [(True, "persistence"), (False, "no_co2")])
def test_backtest_endpoint(client, with_co2, expected):
    gh = make_greenhouse(client)
    mapping = {"timestamp": "t", "temperature": "T", "humidity": "RH"}
    if with_co2:
        mapping["co2"] = "CO2"
    res = client.post(
        f"/greenhouses/{gh['id']}/csv/import",
        files=upload(long_csv(15, with_co2)),
        data={"mapping": json.dumps(mapping)},
    )
    assert res.json()["enough_history"] is True

    body = client.get(f"/greenhouses/{gh['id']}/backtest").json()
    assert body["hours"] == 15 * 24
    states = {h["horizon"]: h for h in body["horizons"]}
    assert set(states) == {1, 3, 6}
    assert states[1]["state"] == expected  # 15일이면 아직 판정 버킷 없음
    assert len(states[1]["buckets"]) == 2
    assert states[6]["state"] == ("reference" if with_co2 else "no_co2")


def test_backtest_learning_when_short(client):
    gh = make_greenhouse(client)
    mapping = {"timestamp": "t", "temperature": "T", "humidity": "RH", "co2": "CO2"}
    client.post(f"/greenhouses/{gh['id']}/csv/import", files=upload(long_csv(5)),
                data={"mapping": json.dumps(mapping)})
    body = client.get(f"/greenhouses/{gh['id']}/backtest").json()
    assert all(h["state"] == "learning" for h in body["horizons"])


def test_training_sources_listed(client):
    sources = client.get("/greenhouses/training-sources").json()
    assert len(sources) == 10 and "gh24_2온실" in sources


def test_holdout_source_validated(client):
    res = client.post("/greenhouses", json={**GREENHOUSE, "holdout_source": "없는온실"})
    assert res.status_code == 422
    gh = make_greenhouse(client)
    res = client.patch(f"/greenhouses/{gh['id']}", json={"holdout_source": "gh24_2온실"})
    assert res.status_code == 200 and res.json()["holdout_source"] == "gh24_2온실"
    res = client.patch(f"/greenhouses/{gh['id']}", json={"holdout_source": None})
    assert res.status_code == 200 and res.json()["holdout_source"] is None


def test_backtest_reports_model_set(client):
    gh = client.post("/greenhouses", json={**GREENHOUSE, "holdout_source": "gh24_2온실"}).json()
    assert client.get(f"/greenhouses/{gh['id']}/backtest").json()["model_set"] == "loso:gh24_2온실"
    gh = make_greenhouse(client)
    assert client.get(f"/greenhouses/{gh['id']}/backtest").json()["model_set"] == "deployed"
