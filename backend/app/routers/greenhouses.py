from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlmodel import Session, delete, select

from app.auth import greenhouse_access, optional_user, require_user
from app.bands import band_versions, record_band_change
from app.db import get_session
from app.forecast import loso_sources
from app.models import (
    AdviceDecision,
    AdviceQuestion,
    AdviceRecord,
    BandVersion,
    Greenhouse,
    GreenhouseCreate,
    GreenhouseRead,
    GreenhouseUpdate,
    IngestToken,
    Reading,
    User,
)

router = APIRouter(prefix="/greenhouses", tags=["greenhouses"])


def _check_holdout(source: str | None) -> None:
    if source is not None and source not in loso_sources():
        raise HTTPException(422, f"unknown training source: {source}")


def get_greenhouse(greenhouse_id: int, session: Session) -> Greenhouse:
    greenhouse = session.get(Greenhouse, greenhouse_id)
    if greenhouse is None:
        raise HTTPException(404, "greenhouse not found")
    return greenhouse


@router.get("/training-sources")
def list_training_sources() -> list[str]:
    """holdout_source로 지정할 수 있는 학습 온실 목록 (데모용)."""
    return sorted(loso_sources())


@router.post("", response_model=GreenhouseRead, status_code=201)
def create_greenhouse(data: GreenhouseCreate, session: Session = Depends(get_session),
                      user: User = Depends(require_user)):
    _check_holdout(data.holdout_source)
    greenhouse = Greenhouse.model_validate(data)
    greenhouse.owner_id = user.id
    session.add(greenhouse)
    session.commit()
    session.refresh(greenhouse)
    return greenhouse


@router.get("", response_model=list[GreenhouseRead])
def list_greenhouses(session: Session = Depends(get_session), user: User | None = Depends(optional_user)):
    """내 온실과 공개(데모) 온실."""
    visible = Greenhouse.public if user is None else or_(Greenhouse.public, Greenhouse.owner_id == user.id)
    return session.exec(select(Greenhouse).where(visible).order_by(Greenhouse.id)).all()


@router.get("/{greenhouse_id}", response_model=GreenhouseRead, dependencies=[Depends(greenhouse_access)])
def read_greenhouse(greenhouse_id: int, session: Session = Depends(get_session)):
    return get_greenhouse(greenhouse_id, session)


@router.patch("/{greenhouse_id}", response_model=GreenhouseRead, dependencies=[Depends(greenhouse_access)])
def update_greenhouse(
    greenhouse_id: int, data: GreenhouseUpdate, session: Session = Depends(get_session)
):
    greenhouse = get_greenhouse(greenhouse_id, session)
    changes = data.model_dump(exclude_unset=True)
    band_apply = changes.pop("band_apply", "today")
    for key, value in changes.items():
        if value is None and key != "holdout_source":
            raise HTTPException(422, f"{key} cannot be null")
    _check_holdout(changes.get("holdout_source"))
    low = changes.get("vpd_low", greenhouse.vpd_low)
    high = changes.get("vpd_high", greenhouse.vpd_high)
    if low >= high:
        raise HTTPException(422, "vpd_low must be less than vpd_high")
    if (low, high) != (greenhouse.vpd_low, greenhouse.vpd_high) or band_apply == "all":
        # 온실 현지 날짜 = 서버 날짜로 본다 (측정 시각도 현지 시각, 타임존 없음)
        record_band_change(session, greenhouse, low, high, band_apply, date.today())
    for key, value in changes.items():
        if key not in ("vpd_low", "vpd_high"):
            setattr(greenhouse, key, value)
    session.add(greenhouse)
    session.commit()
    session.refresh(greenhouse)
    return greenhouse


@router.delete("/{greenhouse_id}", status_code=204, dependencies=[Depends(greenhouse_access)])
def delete_greenhouse(greenhouse_id: int, session: Session = Depends(get_session)):
    greenhouse = get_greenhouse(greenhouse_id, session)
    session.exec(delete(BandVersion).where(BandVersion.greenhouse_id == greenhouse_id))
    session.exec(delete(IngestToken).where(IngestToken.greenhouse_id == greenhouse_id))
    advice_ids = select(AdviceRecord.id).where(AdviceRecord.greenhouse_id == greenhouse_id)
    session.exec(delete(AdviceDecision).where(AdviceDecision.advice_id.in_(advice_ids)))
    session.exec(delete(AdviceRecord).where(AdviceRecord.greenhouse_id == greenhouse_id))
    session.exec(delete(AdviceQuestion).where(AdviceQuestion.greenhouse_id == greenhouse_id))
    session.exec(delete(Reading).where(Reading.greenhouse_id == greenhouse_id))
    session.delete(greenhouse)
    session.commit()


@router.get("/{greenhouse_id}/bands", dependencies=[Depends(greenhouse_access)])
def list_bands(greenhouse_id: int, session: Session = Depends(get_session)):
    """대역 변경 이력. effective_from이 null이면 "처음부터"."""
    gh = get_greenhouse(greenhouse_id, session)
    return [{"effective_from": v[0].isoformat() if v[0] else None, "low": v[1], "high": v[2]}
            for v in band_versions(session, gh)]
