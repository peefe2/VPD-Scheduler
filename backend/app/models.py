from datetime import datetime, timezone
from enum import StrEnum

from pydantic import NaiveDatetime, model_validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class Equipment(StrEnum):
    """보유 설비. AI 어드바이저 추천 범위를 이 목록으로 제한한다."""

    VENT = "vent"  # 천창·측창 환기
    EXHAUST_FAN = "exhaust_fan"  # 환기팬
    SHADE_SCREEN = "shade_screen"  # 차광막
    HUMIDIFIER = "humidifier"  # 가습
    DEHUMIDIFIER = "dehumidifier"  # 제습기
    HEATER = "heater"  # 난방


class ConnectionType(StrEnum):
    REPLAY = "replay"  # 재생 모드
    CSV = "csv"  # CSV 업로드
    API = "api"  # 수집 API (실시간 알림·AI 어드바이저는 여기서만)


class GreenhouseBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    crop: str = Field(min_length=1, max_length=50)
    # 기본 대역 0.5~1.5 kPa: 문헌(Systemic effects of VPD on protected vegetables)의
    # 주간 범위. 데이터 점유율을 보고 고른 값이 아니다 (결정 2026-10-12, CLAUDE.md).
    vpd_low: float = Field(default=0.5, ge=0, le=5)
    vpd_high: float = Field(default=1.5, ge=0, le=5)
    equipment: list[Equipment] = Field(default_factory=list, sa_column=Column(JSON))
    connection_type: ConnectionType = ConnectionType.CSV
    # 데모용: 이 온실 데이터가 모델 학습에 쓴 온실(예: "gh24_2온실")의 것이면 지정.
    # 백테스트가 그 온실을 뺀 LOSO 모델을 써서 in-sample 누수를 막는다.
    holdout_source: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _band_order(self):
        if self.vpd_low >= self.vpd_high:
            raise ValueError("vpd_low must be less than vpd_high")
        return self


class Greenhouse(GreenhouseBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # CO2 열이 연결된 적 있는지. False면 영구히 "모델 사용"으로 전환하지 않는다.
    has_co2: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GreenhouseCreate(GreenhouseBase):
    pass


class GreenhouseUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    crop: str | None = Field(default=None, min_length=1, max_length=50)
    vpd_low: float | None = Field(default=None, ge=0, le=5)
    vpd_high: float | None = Field(default=None, ge=0, le=5)
    equipment: list[Equipment] | None = None
    connection_type: ConnectionType | None = None
    holdout_source: str | None = Field(default=None, max_length=50)


class GreenhouseRead(GreenhouseBase):
    id: int
    has_co2: bool
    created_at: datetime


class Reading(SQLModel, table=True):
    """정시 실측값 한 건. hour는 정시, measured_at은 실제로 고른 측정 시각.

    둘 다 온실 현지 시각(타임존 없음). 낮·밤 주기가 이 시각 기준이라 UTC로 바꾸지 않는다.
    """

    __table_args__ = (UniqueConstraint("greenhouse_id", "hour"),)

    id: int | None = Field(default=None, primary_key=True)
    greenhouse_id: int = Field(foreign_key="greenhouse.id", index=True)
    hour: NaiveDatetime = Field(index=True)
    measured_at: NaiveDatetime
    temperature: float
    humidity: float
    co2: float | None = None
    vpd: float
