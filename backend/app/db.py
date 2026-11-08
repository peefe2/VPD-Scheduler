import os
from collections.abc import Iterator

from sqlalchemy import Connection, Engine, inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get("VPD_DATABASE_URL", "sqlite:///./vpd.db")

# 배포 서버 시작이 DB를 기다리며 오류 없이 15분 멈춘 적이 있다 (Render, 2026-11-08) — 연결과 잠금 대기에
# 시간 제한을 둬서 멈추는 대신 무엇에 막혔는지 오류로 보이게 한다.
CONNECT_TIMEOUT = 10  # 초
LOCK_TIMEOUT = "30s"


def engine_options(url: str) -> tuple[str, dict]:
    """로컬은 SQLite, 배포는 PostgreSQL(Neon 등 — 무료 서버는 디스크가 안 남아서).
    서비스가 주는 postgres(ql):// 주소를 psycopg 드라이버 주소로 바꾼다."""
    pg = {"pool_pre_ping": True, "connect_args": {"connect_timeout": CONNECT_TIMEOUT}}
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):], pg
    if url.startswith("postgresql+"):
        return url, pg
    return url, {"connect_args": {"check_same_thread": False}}


_url, _kwargs = engine_options(DATABASE_URL)
engine = create_engine(_url, **_kwargs)


def limit_lock_wait(conn: Connection) -> None:
    """이 트랜잭션에서 잠금을 LOCK_TIMEOUT까지만 기다린다 (PostgreSQL만).

    배포 중에는 이전 서버와 새 서버가 같은 DB를 쓴다. SET LOCAL이라 트랜잭션이 끝나면 풀리고,
    Neon 연결 풀러(트랜잭션 단위)에서도 다른 연결로 새지 않는다."""
    if conn.dialect.name == "postgresql":
        conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))


# create_all은 이미 있는 테이블에 새 컬럼을 더하지 않는다. 기존 vpd.db에 나중에 추가한
# nullable 컬럼만 여기서 ALTER TABLE로 채운다 (마이그레이션 도구 대신).
ADDED_COLUMNS = [
    ("advicerecord", "guardrail", "JSON"),
    ("advicequestion", "visitor", "VARCHAR(64)"),
    ("greenhouse", "owner_id", "INTEGER"),
    ("greenhouse", "public", "BOOLEAN NOT NULL DEFAULT FALSE"),
]


def ensure_columns(bind: Engine | Connection) -> None:
    if isinstance(bind, Engine):
        with bind.begin() as conn:
            ensure_columns(conn)
        return
    insp = inspect(bind)
    for table, column, type_ in ADDED_COLUMNS:
        if insp.has_table(table) and column not in {c["name"] for c in insp.get_columns(table)}:
            bind.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {type_}"))


def init_db() -> None:
    from app import models  # noqa: F401  테이블 등록

    with engine.begin() as conn:
        limit_lock_wait(conn)
        SQLModel.metadata.create_all(conn)
        ensure_columns(conn)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
