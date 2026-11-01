import os
from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get("VPD_DATABASE_URL", "sqlite:///./vpd.db")


def engine_options(url: str) -> tuple[str, dict]:
    """로컬은 SQLite, 배포는 PostgreSQL(Neon 등 — 무료 서버는 디스크가 안 남아서).
    서비스가 주는 postgres(ql):// 주소를 psycopg 드라이버 주소로 바꾼다."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):], {"pool_pre_ping": True}
    if url.startswith("postgresql+"):
        return url, {"pool_pre_ping": True}
    return url, {"connect_args": {"check_same_thread": False}}


_url, _kwargs = engine_options(DATABASE_URL)
engine = create_engine(_url, **_kwargs)


# create_all은 이미 있는 테이블에 새 컬럼을 더하지 않는다. 기존 vpd.db에 나중에 추가한
# nullable 컬럼만 여기서 ALTER TABLE로 채운다 (마이그레이션 도구 대신).
ADDED_COLUMNS = [
    ("advicerecord", "guardrail", "JSON"),
    ("advicequestion", "visitor", "VARCHAR(64)"),
    ("greenhouse", "owner_id", "INTEGER"),
    ("greenhouse", "public", "BOOLEAN NOT NULL DEFAULT FALSE"),
]


def ensure_columns(engine) -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, type_ in ADDED_COLUMNS:
            if insp.has_table(table) and column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {type_}"))


def init_db() -> None:
    from app import models  # noqa: F401  테이블 등록

    SQLModel.metadata.create_all(engine)
    ensure_columns(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
