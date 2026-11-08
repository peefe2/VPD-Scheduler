"""데모 온실 자동 준비 (VPD_DEMO=1): 재생 온실을 만들고 지난 이력을 DB에 바로 채운다."""

from datetime import datetime, timedelta

import pandas as pd
from sqlmodel import Session, select

from app import demo, main
from app.models import ConnectionType, Greenhouse, Reading
from tests.test_api import engine  # noqa: F401  fixture 재사용

START = datetime(2021, 9, 27)


def write_csv(tmp_path, days=4):
    hours = pd.date_range(START, periods=days * 24, freq="h")
    rows = pd.DataFrame({"date": hours, "temp": 20.0, "humidity": 90.0, "co2": 450.0,
                         "source": "farm3_2023", "VPD": 0.23})
    other = rows.assign(source="aihub_farm1", temp=30.0)  # 다른 온실 데이터는 쓰지 않는다
    path = tmp_path / "combined.csv"
    pd.concat([rows, other]).to_csv(path, index=False)
    return path


def seed(engine, path, now):  # noqa: F811
    with Session(engine) as s:
        return demo.ensure_demo(s, now=now, data_path=path, backfill_days=2)


def readings(engine):  # noqa: F811
    with Session(engine) as s:
        return s.exec(select(Reading).order_by(Reading.hour)).all()


def test_creates_replay_greenhouse_with_history_up_to_now(engine, tmp_path):  # noqa: F811
    path = write_csv(tmp_path)
    now = datetime(2026, 11, 1, 10, 30)
    seed(engine, path, now)

    with Session(engine) as s:
        (gh,) = s.exec(select(Greenhouse)).all()
    assert gh.name == demo.DEMO_NAME and gh.connection_type is ConnectionType.REPLAY
    assert gh.holdout_source == "farm3_2023" and gh.has_co2 and gh.equipment
    rows = readings(engine)
    # 원본 3일째(앞 2일 이력 뒤)가 오늘이 되고, 시각은 그대로 — 지금(10:30)까지만
    assert rows[0].hour == datetime(2026, 10, 30, 0) and rows[-1].hour == datetime(2026, 11, 1, 10)
    assert len(rows) == 2 * 24 + 11
    assert all(r.temperature == 20.0 for r in rows)  # farm3만


def test_second_run_only_adds_new_hours_with_same_shift(engine, tmp_path):  # noqa: F811
    path = write_csv(tmp_path)
    now = datetime(2026, 11, 1, 10, 30)
    seed(engine, path, now)
    seed(engine, path, now)
    assert len(readings(engine)) == 2 * 24 + 11  # 다시 켜도 그대로

    seed(engine, path, now + timedelta(days=1, hours=2))  # 다음날 다시 켬
    rows = readings(engine)
    assert rows[0].hour == datetime(2026, 10, 30, 0)  # 이동 일수는 처음 그대로
    assert rows[-1].hour == datetime(2026, 11, 2, 12) and len(rows) == 3 * 24 + 13
    with Session(engine) as s:
        assert len(s.exec(select(Greenhouse)).all()) == 1


def test_startup_seeds_demo_only_when_enabled(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(main, "seed_demo", lambda: calls.append("demo"))
    monkeypatch.delenv("VPD_DEMO", raising=False)
    main.startup()
    assert calls == ["init"]
    monkeypatch.setenv("VPD_DEMO", "1")
    main.startup()
    assert calls == ["init", "init", "demo"]


def test_startup_continues_when_demo_seed_fails(monkeypatch, caplog):
    def fail():
        raise RuntimeError("lock timeout")

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "seed_demo", fail)
    monkeypatch.setenv("VPD_DEMO", "1")
    with caplog.at_level("INFO", logger="uvicorn.error"):
        main.startup()  # 예외가 밖으로 나오지 않는다
    text = caplog.text
    assert "DB 테이블 확인 끝" in text and "데모 온실 채우기 실패" in text


def test_demo_seed_logs_how_many_hours(engine, tmp_path, caplog):  # noqa: F811
    with caplog.at_level("INFO", logger="uvicorn.error"):
        seed(engine, write_csv(tmp_path), datetime(2026, 11, 1, 10, 30))
    assert "새로 채울 정시 59건" in caplog.text
