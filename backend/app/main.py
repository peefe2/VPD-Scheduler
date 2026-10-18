from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import backtest, calendar, csv_import, greenhouses, ingest, readings, today


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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


@app.get("/health")
def health():
    return {"status": "ok"}
