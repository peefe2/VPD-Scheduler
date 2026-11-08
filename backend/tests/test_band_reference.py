from app.band_reference import CROP_NOTES, SOURCES, TABLE
from tests.test_api import client, engine  # noqa: F401  fixture 재사용


def test_every_recommendation_has_source_and_valid_range():
    for crop, stages in TABLE.items():
        for st in stages:
            rec = st["recommend"]
            if rec is None:
                assert st["reason"], (crop, st["stage"])  # 근거 부족이면 이유를 말한다
                continue
            assert 0 <= rec["low"] < rec["high"] <= 5, (crop, st["stage"])
            assert rec["source"] in SOURCES and rec["evidence"], (crop, st["stage"])
            for ref in st.get("references", []):
                assert ref["source"] in SOURCES


def test_conflicting_tomato_sources_keep_default():
    # 출처끼리 다르면 하나를 고르지 않는다 (검토 결정 2026-11-07)
    general = next(s for s in TABLE["토마토"] if s["stage"] == "all")
    assert general["recommend"] is None and len(general["references"]) >= 4


def test_converted_values_show_original_unit():
    fruiting = next(s for s in TABLE["파프리카"] if s["stage"] == "fruiting")
    assert "g/m³" in fruiting["recommend"]["original"]
    for stage in ("seedling", "transplant"):  # 앨버타 지침도 습도부족분을 환산한 값
        rec = next(s for s in TABLE["토마토"] if s["stage"] == stage)["recommend"]
        assert "g/m³" in rec["original"] and "환산" in rec["evidence"]


def test_sources_are_labelled_and_notes_are_sourced():
    for key, src in SOURCES.items():
        assert src["kind"] and src["region"] in {"국내", "해외"}, key
    for crop, notes in CROP_NOTES.items():
        assert crop in TABLE
        for note in notes:
            assert note["source"] in SOURCES and note["kind"] in {"trait", "caution"}, crop


def test_band_references_endpoint_needs_no_login(client):  # noqa: F811
    from fastapi.testclient import TestClient

    from app.main import app

    body = TestClient(app).get("/greenhouses/band-references").json()
    assert body["default"] == {"low": 0.5, "high": 1.5}
    assert set(body["crops"]) == {"토마토", "파프리카", "오이", "딸기"}
