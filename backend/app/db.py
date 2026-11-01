import os
from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get("VPD_DATABASE_URL", "sqlite:///./vpd.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# create_all은 이미 있는 테이블에 새 컬럼을 더하지 않는다. 기존 vpd.db에 나중에 추가한
# nullable 컬럼만 여기서 ALTER TABLE로 채운다 (마이그레이션 도구 대신).
ADDED_COLUMNS = [("advicerecord", "guardrail", "JSON"), ("advicequestion", "visitor", "VARCHAR(64)")]


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
