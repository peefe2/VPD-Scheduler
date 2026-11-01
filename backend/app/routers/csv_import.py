"""CSV 업로드 → 컬럼 매핑 → 정시 실측값 저장.

1) /csv/preview: 열 이름·앞부분 행·추정 매핑을 돌려준다.
2) /csv/import: 사용자가 확정한 매핑으로 같은 파일을 다시 올리면 정시 값으로
   줄여서 저장한다. 같은 정시가 이미 있으면 새 값으로 교체한다.
"""

import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, delete

from app.auth import greenhouse_access
from app.db import get_session
from app.models import Reading
from app.routers.greenhouses import get_greenhouse
from app.vpd import hourly_first, vpd

router = APIRouter(prefix="/greenhouses/{greenhouse_id}/csv", tags=["csv"], dependencies=[Depends(greenhouse_access)])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PREVIEW_ROWS = 5
MIN_HISTORY_DAYS = 14  # CLAUDE.md N = 14일

# 열 이름 추정용 키워드 (소문자 비교)
GUESS_KEYWORDS = {
    "timestamp": ["timestamp", "datetime", "date", "time", "일시", "날짜", "시간", "측정"],
    "temperature": ["temp", "온도", "기온"],
    "humidity": ["humid", "rh", "습도"],
    "co2": ["co2", "이산화탄소", "탄산"],
}


class ColumnMapping(BaseModel):
    timestamp: str
    temperature: str
    humidity: str
    co2: str | None = None


def _read_csv(raw: bytes) -> pd.DataFrame:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large (max 50MB)")
    # 국내 센서 장비 CSV는 cp949가 흔하다
    for encoding in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(422, "cannot decode file as UTF-8 or CP949")
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        raise HTTPException(422, f"cannot parse CSV: {e}")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def guess_mapping(columns: list[str]) -> dict[str, str | None]:
    guess: dict[str, str | None] = {}
    used: set[str] = set()
    for field, keywords in GUESS_KEYWORDS.items():
        guess[field] = next(
            (
                c
                for c in columns
                if c not in used and any(k in c.lower() for k in keywords)
            ),
            None,
        )
        if guess[field]:
            used.add(guess[field])
    return guess


@router.post("/preview")
async def preview_csv(
    greenhouse_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    get_greenhouse(greenhouse_id, session)
    df = _read_csv(await file.read())
    columns = list(df.columns)
    return {
        "columns": columns,
        "rows": df.head(PREVIEW_ROWS).fillna("").to_dict(orient="records"),
        "total_rows": len(df),
        "guessed_mapping": guess_mapping(columns),
    }


@router.post("/import")
async def import_csv(
    greenhouse_id: int,
    file: UploadFile = File(...),
    mapping: str = Form(..., description="ColumnMapping JSON"),
    session: Session = Depends(get_session),
):
    greenhouse = get_greenhouse(greenhouse_id, session)
    try:
        m = ColumnMapping.model_validate(json.loads(mapping))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(422, f"invalid mapping: {e}")

    df = _read_csv(await file.read())
    wanted = {"timestamp": m.timestamp, "temperature": m.temperature, "humidity": m.humidity}
    if m.co2:
        wanted["co2"] = m.co2
    missing = [col for col in wanted.values() if col not in df.columns]
    if missing:
        raise HTTPException(422, f"columns not in file: {missing}")

    data = pd.DataFrame({field: df[col] for field, col in wanted.items()})
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    for field in ("temperature", "humidity", "co2"):
        if field in data:
            data[field] = pd.to_numeric(data[field], errors="coerce")
    if "co2" not in data:
        data["co2"] = float("nan")

    rows_read = len(data)
    bad_timestamp = int(data["timestamp"].isna().sum())
    data = data.dropna(subset=["timestamp"]).set_index("timestamp")

    # CLAUDE.md TODO: RH 범위 밖 처리 미정. 임시로 클리핑하지 않고 버린다.
    rh_out_of_range = data["humidity"].notna() & ~data["humidity"].between(0, 100)
    data.loc[rh_out_of_range, "humidity"] = float("nan")

    complete = data.dropna(subset=["temperature", "humidity"])
    hours_with_data = complete.index.floor("h").nunique()
    hourly = hourly_first(data, required=["temperature", "humidity"])
    hourly["vpd"] = vpd(hourly["temperature"], hourly["humidity"])

    if not hourly.empty:
        hours = [h.to_pydatetime() for h in hourly.index]
        session.exec(
            delete(Reading).where(
                Reading.greenhouse_id == greenhouse_id, Reading.hour.in_(hours)
            )
        )
        session.add_all(
            Reading(
                greenhouse_id=greenhouse_id,
                hour=hour.to_pydatetime(),
                measured_at=row.measured_at.to_pydatetime(),
                temperature=float(row.temperature),
                humidity=float(row.humidity),
                co2=None if pd.isna(row.co2) else float(row.co2),
                vpd=float(row.vpd),
            )
            for hour, row in hourly.iterrows()
        )

    co2_included = bool(hourly["co2"].notna().any()) if not hourly.empty else False
    if co2_included and not greenhouse.has_co2:
        greenhouse.has_co2 = True
        session.add(greenhouse)
    session.commit()

    return {
        "rows_read": rows_read,
        "rows_bad_timestamp": bad_timestamp,
        "rows_humidity_out_of_range": int(rh_out_of_range.sum()),
        "hours_imported": len(hourly),
        "hours_skipped_late": int(hours_with_data - len(hourly)),
        "start": hourly.index.min().isoformat() if not hourly.empty else None,
        "end": hourly.index.max().isoformat() if not hourly.empty else None,
        "co2_included": co2_included,
        "enough_history": len(hourly) >= MIN_HISTORY_DAYS * 24,
    }
