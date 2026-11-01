import pytest

from app import auth


@pytest.fixture(autouse=True)
def fast_password_hash(monkeypatch):
    """scrypt는 일부러 느리다(무차별 대입 방지). 거의 모든 테스트가 가입하므로 테스트에서만 비용을 낮춘다."""
    monkeypatch.setattr(auth, "SCRYPT", {"n": 2**4, "r": 8, "p": 1})
