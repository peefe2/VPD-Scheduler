"""한 서버로 배포: API는 /api 아래, 빌드한 프론트는 / 에서. 화면 주소(/g/1/advisor)는 index.html로."""

from fastapi.testclient import TestClient

from app.main import app as api
from app.spa import create_app
from tests.test_api import GREENHOUSE, client, engine  # noqa: F401  fixture 재사용


def make_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def served(tmp_path, client):  # noqa: F811  client fixture가 api의 DB를 테스트 DB로 바꿔 둔다
    started = []
    root = create_app(api, startup=lambda: started.append(True), dist=make_dist(tmp_path))
    return TestClient(root), started


def test_api_under_prefix_and_startup_runs(tmp_path, client):  # noqa: F811
    tc, started = served(tmp_path, client)
    with tc:
        assert tc.get("/api/health").json() == {"status": "ok"}
        assert tc.post("/api/greenhouses", json=GREENHOUSE).status_code == 201
        assert len(tc.get("/api/greenhouses").json()) == 1
    assert started == [True]


def test_frontend_files_and_spa_fallback(tmp_path, client):  # noqa: F811
    tc, _ = served(tmp_path, client)
    assert "id=root" in tc.get("/").text
    assert tc.get("/assets/app.js").text == "console.log(1)"
    deep = tc.get("/g/1/advisor")  # 새로고침해도 화면이 뜬다
    assert deep.status_code == 200 and "id=root" in deep.text


def test_unknown_api_path_is_404_not_index(tmp_path, client):  # noqa: F811
    tc, _ = served(tmp_path, client)
    res = tc.get("/api/no-such-thing")
    assert res.status_code == 404 and "id=root" not in res.text


def test_without_dist_only_api(tmp_path, client):  # noqa: F811
    root = create_app(api, startup=lambda: None, dist=tmp_path / "missing")
    tc = TestClient(root)
    assert tc.get("/api/health").status_code == 200
    assert tc.get("/").status_code == 404
