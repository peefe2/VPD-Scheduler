import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.db import init_db
from app.routers import advisor, backtest, calendar, csv_import, greenhouses, ingest, readings, today


def seed_demo() -> None:
    from app.db import engine
    from app.demo import ensure_demo

    with Session(engine) as session:
        ensure_demo(session)


def startup() -> None:
    init_db()
    if os.environ.get("VPD_DEMO") == "1":
        seed_demo()


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
app.include_router(greenhouses.router)
app.include_router(csv_import.router)
app.include_router(backtest.router)
app.include_router(calendar.router)
app.include_router(readings.router)
app.include_router(ingest.router)
app.include_router(today.router)
app.include_router(advisor.router)

# 읽기 전용 공개 데모(VPD_READONLY=1)에서 유일하게 허용하는 쓰기: 질문하기
ASK_PATH = re.compile(r".*/greenhouses/\d+/advisor/ask")
READONLY_MESSAGE = "읽기 전용 데모입니다. 온실 추가·수정·삭제와 기록은 할 수 없고, 질문하기만 쓸 수 있습니다."


def readonly() -> bool:
    return os.environ.get("VPD_READONLY") == "1"


@app.middleware("http")
async def readonly_guard(request: Request, call_next):
    """로그인이 없어서, 공개할 때는 이 모드로 화면을 보기 전용으로 막는다 (CLAUDE.md "알려진 한계")."""
    if readonly() and request.method not in ("GET", "HEAD", "OPTIONS") and not ASK_PATH.fullmatch(request.url.path):
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
