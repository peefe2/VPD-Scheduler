from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, delete, select

from app.db import get_session
from app.forecast import loso_sources
from app.models import (
    Greenhouse,
    GreenhouseCreate,
    GreenhouseRead,
    GreenhouseUpdate,
    Reading,
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
def create_greenhouse(data: GreenhouseCreate, session: Session = Depends(get_session)):
    _check_holdout(data.holdout_source)
    greenhouse = Greenhouse.model_validate(data)
    session.add(greenhouse)
    session.commit()
    session.refresh(greenhouse)
    return greenhouse


@router.get("", response_model=list[GreenhouseRead])
def list_greenhouses(session: Session = Depends(get_session)):
    return session.exec(select(Greenhouse).order_by(Greenhouse.id)).all()


@router.get("/{greenhouse_id}", response_model=GreenhouseRead)
def read_greenhouse(greenhouse_id: int, session: Session = Depends(get_session)):
    return get_greenhouse(greenhouse_id, session)


@router.patch("/{greenhouse_id}", response_model=GreenhouseRead)
def update_greenhouse(
    greenhouse_id: int, data: GreenhouseUpdate, session: Session = Depends(get_session)
):
    greenhouse = get_greenhouse(greenhouse_id, session)
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is None and key != "holdout_source":
            raise HTTPException(422, f"{key} cannot be null")
    _check_holdout(changes.get("holdout_source"))
    low = changes.get("vpd_low", greenhouse.vpd_low)
    high = changes.get("vpd_high", greenhouse.vpd_high)
    if low >= high:
        raise HTTPException(422, "vpd_low must be less than vpd_high")
    for key, value in changes.items():
        setattr(greenhouse, key, value)
    session.add(greenhouse)
    session.commit()
    session.refresh(greenhouse)
    return greenhouse


@router.delete("/{greenhouse_id}", status_code=204)
def delete_greenhouse(greenhouse_id: int, session: Session = Depends(get_session)):
    greenhouse = get_greenhouse(greenhouse_id, session)
    session.exec(delete(Reading).where(Reading.greenhouse_id == greenhouse_id))
    session.delete(greenhouse)
    session.commit()
