from sqlmodel import Session, select

from app.models import IngestToken
from tests.test_api import GREENHOUSE, client, engine  # noqa: F401  fixture 재사용
from tests.test_today import API_GH, m

URL = "/greenhouses/{}/ingest"
BODY = {"measurements": [m("2026-10-01T10:00:00")]}


def issue(client, gh_id):
    return client.post(f"/greenhouses/{gh_id}/ingest-token")


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_ingest_without_token_is_401(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    issue(client, gh["id"])
    assert client.post(URL.format(gh["id"]), json=BODY).status_code == 401


def test_ingest_before_any_token_issued_is_401(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    assert client.post(URL.format(gh["id"]), json=BODY, headers=bearer("x")).status_code == 401


def test_ingest_with_wrong_token_is_401(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    issue(client, gh["id"])
    assert client.post(URL.format(gh["id"]), json=BODY, headers=bearer("wrong")).status_code == 401


def test_ingest_with_token_of_other_greenhouse_is_401(client):  # noqa: F811
    a = client.post("/greenhouses", json=API_GH).json()
    b = client.post("/greenhouses", json=API_GH).json()
    issue(client, a["id"])
    token_b = issue(client, b["id"]).json()["token"]
    assert client.post(URL.format(a["id"]), json=BODY, headers=bearer(token_b)).status_code == 401


def test_ingest_with_token_stores(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    token = issue(client, gh["id"]).json()["token"]
    res = client.post(URL.format(gh["id"]), json=BODY, headers=bearer(token))
    assert res.status_code == 200 and res.json()["stored"] == 1


def test_reissue_invalidates_old_token(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    old = issue(client, gh["id"]).json()["token"]
    new = issue(client, gh["id"]).json()["token"]
    assert old != new
    assert client.post(URL.format(gh["id"]), json=BODY, headers=bearer(old)).status_code == 401
    assert client.post(URL.format(gh["id"]), json=BODY, headers=bearer(new)).status_code == 200


def test_status_does_not_reveal_token(client):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    assert client.get(f"/greenhouses/{gh['id']}/ingest-token").json() == {"issued": False, "created_at": None}
    token = issue(client, gh["id"]).json()["token"]
    res = client.get(f"/greenhouses/{gh['id']}/ingest-token")
    body = res.json()
    assert body["issued"] is True and body["created_at"]
    assert token not in res.text


def test_only_hash_is_stored(client, engine):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    token = issue(client, gh["id"]).json()["token"]
    with Session(engine) as s:
        row = s.exec(select(IngestToken)).one()
    assert row.token_hash != token and token not in row.token_hash


def test_csv_greenhouse_cannot_issue_token(client):  # noqa: F811
    gh = client.post("/greenhouses", json=GREENHOUSE).json()
    assert issue(client, gh["id"]).status_code == 409


def test_issue_for_missing_greenhouse_is_404(client):  # noqa: F811
    assert issue(client, 999).status_code == 404


def test_delete_greenhouse_removes_token(client, engine):  # noqa: F811
    gh = client.post("/greenhouses", json=API_GH).json()
    issue(client, gh["id"])
    assert client.delete(f"/greenhouses/{gh['id']}").status_code == 204
    with Session(engine) as s:
        assert s.exec(select(IngestToken)).all() == []
