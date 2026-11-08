import logging
import os
import re
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import event
from sqlmodel import Session

from app.auth import VISITOR_WRITE
from app.db import init_db
from app.routers import advisor, auth, backtest, calendar, csv_import, greenhouses, ingest, readings, today

log = logging.getLogger("uvicorn.error")  # uvicorn이 INFO로 출력하는 로거 (배포 로그에 보임)


def seed_demo() -> None:
    from app.db import engine, limit_lock_wait
    from app.demo import ensure_demo

    with Session(engine) as session:
        event.listen(session, "after_begin", lambda _s, _t, conn: limit_lock_wait(conn))
        ensure_demo(session)


@contextmanager
def step(name: str) -> Iterator[None]:
    # 시작 단계마다 시작·끝·걸린 시간을 남긴다 — 배포 서버가 어디서 멈췄는지 로그로 보이게
    log.info("시작 준비: %s ...", name)
    t = time.monotonic()
    yield
    log.info("시작 준비: %s 끝 (%.1f초)", name, time.monotonic() - t)


def startup() -> None:
    with step("DB 테이블 확인"):
        init_db()
    if os.environ.get("VPD_DEMO") == "1":
        # 데모 정시를 못 채워도 서버는 켠다 (이미 채운 이력으로 화면은 동작한다)
        try:
            with step("데모 온실 채우기"):
                seed_demo()
        except Exception:
            log.exception("시작 준비: 데모 온실 채우기 실패 — 채우지 않고 서버를 켭니다")


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield


app = FastAPI(title="VPD Smartfarm API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(greenhouses.router)
app.include_router(csv_import.router)
app.include_router(backtest.router)
app.include_router(calendar.router)
app.include_router(readings.router)
app.include_router(ingest.router)
app.include_router(today.router)
app.include_router(advisor.router)

# 읽기 전용 공개 데모(VPD_READONLY=1)에서도 허용하는 쓰기: 질문하기, 조치 기록 (방문자별로 따로 저장)
READONLY_MESSAGE = "읽기 전용 데모입니다. 온실 추가·수정·삭제는 할 수 없고, 질문하기와 조치 기록 체험만 쓸 수 있습니다."


def readonly() -> bool:
    return os.environ.get("VPD_READONLY") == "1"


@app.middleware("http")
async def readonly_guard(request: Request, call_next):
    """로그인이 없어서, 공개할 때는 이 모드로 화면을 보기 전용으로 막는다 (CLAUDE.md "알려진 한계")."""
    if readonly() and request.method not in ("GET", "HEAD", "OPTIONS") and not VISITOR_WRITE.fullmatch(request.url.path):
        return JSONResponse({"detail": READONLY_MESSAGE}, status_code=403)
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    """화면이 모드에 맞춰 버튼을 숨기고 안내를 띄우는 데 쓴다. 키 값은 알려주지 않는다."""
    return {
        "readonly": readonly(),
        "demo": os.environ.get("VPD_DEMO") == "1",
        "llm": os.environ.get("VPD_ADVISOR_LLM") == "1" and bool(os.environ.get("GEMINI_API_KEY")),
    }
