"""배포 DB 주소: Neon·Render가 주는 postgres(ql):// 주소를 SQLAlchemy psycopg 드라이버 주소로 바꾼다."""

from app.db import engine_options


def test_postgres_urls_use_psycopg_driver():
    for given in ("postgres://u:p@host/db?sslmode=require", "postgresql://u:p@host/db?sslmode=require"):
        url, kwargs = engine_options(given)
        assert url == "postgresql+psycopg://u:p@host/db?sslmode=require"
        assert kwargs == {"pool_pre_ping": True}  # 무료 DB는 쉬다가 연결을 끊는다


def test_sqlite_keeps_thread_option():
    url, kwargs = engine_options("sqlite:///./vpd.db")
    assert url == "sqlite:///./vpd.db" and kwargs == {"connect_args": {"check_same_thread": False}}


def test_explicit_driver_untouched():
    assert engine_options("postgresql+psycopg://u@h/d")[0] == "postgresql+psycopg://u@h/d"
