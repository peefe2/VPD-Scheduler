"""이메일 회원가입·로그인(세션 쿠키)과 온실 소유권. 이메일 인증은 하지 않는다 (결정 2026-11-01)."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import Greenhouse, User
from tests.test_api import GREENHOUSE, client, engine  # noqa: F401  fixture 재사용
from tests.test_today import m, post

PW = "password123"


def new_client(email=None):
    """client fixture와 같은 테스트 DB를 쓰는 다른 브라우저. email을 주면 가입해서 로그인한 상태."""
    c = TestClient(app)
    if email:
        assert c.post("/auth/signup", json={"email": email, "password": PW}).status_code == 201
    return c


def make_public(engine, gh_id):  # noqa: F811
    with Session(engine) as s:
        gh = s.get(Greenhouse, gh_id)
        gh.public = True
        s.add(gh)
        s.commit()


# ---------------------------------------------------------------- 가입·로그인

def test_signup_logs_in_and_stores_only_hash(client, engine):  # noqa: F811
    c = new_client()
    res = c.post("/auth/signup", json={"email": " New@Example.com ", "password": PW})
    assert res.status_code == 201 and res.json()["email"] == "new@example.com"
    assert "vpd_session" in res.cookies
    assert c.get("/auth/me").json()["email"] == "new@example.com"
    with Session(engine) as s:
        user = s.exec(select(User).where(User.email == "new@example.com")).one()
    assert PW not in user.password_hash and user.password_hash.startswith("scrypt$")


def test_duplicate_email_rejected(client):  # noqa: F811
    new_client("dup@example.com")
    res = new_client().post("/auth/signup", json={"email": "DUP@example.com", "password": PW})
    assert res.status_code == 409 and "이미" in res.json()["detail"]


def test_bad_email_or_short_password_rejected(client):  # noqa: F811
    c = new_client()
    assert c.post("/auth/signup", json={"email": "not-an-email", "password": PW}).status_code == 422
    assert c.post("/auth/signup", json={"email": "a@b.co", "password": "short"}).status_code == 422


def test_login_logout(client):  # noqa: F811
    new_client("me@example.com")
    c = new_client()
    assert c.get("/auth/me").status_code == 401
    wrong = c.post("/auth/login", json={"email": "me@example.com", "password": "wrong-password"})
    assert wrong.status_code == 401
    unknown = c.post("/auth/login", json={"email": "nobody@example.com", "password": PW})
    assert unknown.json()["detail"] == wrong.json()["detail"]  # 가입 여부를 흘리지 않는다
    assert c.post("/auth/login", json={"email": "ME@example.com", "password": PW}).status_code == 200
    assert c.get("/auth/me").json()["email"] == "me@example.com"
    assert c.post("/auth/logout").status_code == 204
    assert c.get("/auth/me").status_code == 401


# ---------------------------------------------------------------- 온실 소유권

def test_greenhouses_are_private_to_owner(client):  # noqa: F811
    gh = client.post("/greenhouses", json=GREENHOUSE).json()  # client = 가입한 주인
    other = new_client("other@example.com")
    anon = new_client()

    assert [g["id"] for g in client.get("/greenhouses").json()] == [gh["id"]]
    for c in (other, anon):
        assert c.get("/greenhouses").json() == []
        assert c.get(f"/greenhouses/{gh['id']}").status_code == 404
        assert c.get(f"/greenhouses/{gh['id']}/calendar").status_code == 404
        assert c.patch(f"/greenhouses/{gh['id']}", json={"name": "뺏기"}).status_code == 404
        assert c.delete(f"/greenhouses/{gh['id']}").status_code == 404


def test_creating_greenhouse_needs_login(client):  # noqa: F811
    assert new_client().post("/greenhouses", json=GREENHOUSE).status_code == 401
    assert client.post("/greenhouses", json=GREENHOUSE).status_code == 201


def test_public_greenhouse_readable_and_askable_but_not_changeable(client, engine):  # noqa: F811
    gh = client.post("/greenhouses", json={**GREENHOUSE, "connection_type": "api"}).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", t=18, rh=95, co2=450))
    make_public(engine, gh["id"])
    advice_id = client.get(f"/greenhouses/{gh['id']}/advisor").json()["advice_id"]

    anon, other = new_client(), new_client("other@example.com")
    for c in (anon, other):
        assert gh["id"] in [g["id"] for g in c.get("/greenhouses").json()]
        assert c.get(f"/greenhouses/{gh['id']}/today").status_code == 200
    assert anon.post(f"/greenhouses/{gh['id']}/advisor/ask",
                     json={"question": "뭐 해?", "visitor": "browser-1"}).status_code == 200
    assert other.post(f"/greenhouses/{gh['id']}/advisor/ask", json={"question": "뭐 해?"}).status_code == 200

    assert anon.patch(f"/greenhouses/{gh['id']}", json={"name": "x"}).status_code == 401
    assert other.patch(f"/greenhouses/{gh['id']}", json={"name": "x"}).status_code == 403
    assert other.post(f"/greenhouses/{gh['id']}/ingest-token").status_code == 403
    decision = {"candidate_index": 0, "decision": "done"}
    assert other.post(f"/greenhouses/{gh['id']}/advisor/{advice_id}/decisions", json=decision).status_code == 403


def test_public_greenhouse_conversations_split_by_person(client, engine):  # noqa: F811
    gh = client.post("/greenhouses", json={**GREENHOUSE, "connection_type": "api"}).json()
    post(client, gh["id"], m("2026-10-01T00:00:00", t=18, rh=95, co2=450))
    make_public(engine, gh["id"])
    url = f"/greenhouses/{gh['id']}/advisor"
    anon, other = new_client(), new_client("other@example.com")

    assert anon.post(f"{url}/ask", json={"question": "방문자 id 없음"}).status_code == 422
    anon.post(f"{url}/ask", json={"question": "익명 질문", "visitor": "browser-1"})
    other.post(f"{url}/ask", json={"question": "다른 계정 질문"})
    client.post(f"{url}/ask", json={"question": "주인 질문"})

    def asked(c, **params):
        return [h["question"] for h in c.get(f"{url}/questions", params=params).json()]

    assert asked(anon, visitor="browser-1") == ["익명 질문"]
    assert asked(anon) == []
    assert asked(other) == ["다른 계정 질문"]
    assert asked(client) == ["주인 질문"]


def test_ingest_still_uses_token_without_login(client):  # noqa: F811
    gh = client.post("/greenhouses", json={**GREENHOUSE, "connection_type": "api"}).json()
    token = client.post(f"/greenhouses/{gh['id']}/ingest-token").json()["token"]
    sensor = new_client()  # 센서는 로그인하지 않는다
    res = sensor.post(f"/greenhouses/{gh['id']}/ingest", headers={"Authorization": f"Bearer {token}"},
                      json={"measurements": [m("2026-10-01T00:00:00")]})
    assert res.status_code == 200 and res.json()["stored"] == 1


def test_first_signup_claims_existing_greenhouses(engine):  # noqa: F811
    from app.db import get_session

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        with Session(engine) as s:  # 로그인 기능 전부터 있던 온실 + 공개 데모
            s.add(Greenhouse(name="옛 온실", crop="토마토"))
            s.add(Greenhouse(name="데모", crop="미상", public=True))
            s.commit()
        first = new_client("first@example.com")
        second = new_client("second@example.com")
        assert sorted(g["name"] for g in first.get("/greenhouses").json()) == ["데모", "옛 온실"]
        assert [g["name"] for g in second.get("/greenhouses").json()] == ["데모"]
        with Session(engine) as s:
            demo = s.exec(select(Greenhouse).where(Greenhouse.name == "데모")).one()
        assert demo.owner_id is None
    finally:
        app.dependency_overrides.clear()
