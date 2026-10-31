from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Literal

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
    # 대역을 바꿀 때만 쓴다. "today": 오늘부터 적용(지난 캘린더 유지),
    # "all": 처음부터 적용(잘못 입력한 값 정정 — 이전 이력을 지운다)
    band_apply: Literal["today", "all"] = "today"


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


class AdviceRecord(SQLModel, table=True):
    """어드바이저 추천 1건 = 온실 × 정시. 그때의 사실 시트와 후보를 그대로 남긴다.

    2시간 뒤 VPD는 저장하지 않고 조회할 때 실측(Reading)에서 붙인다 — 정시 값이
    나중에 교체되면 그 값을 따른다.
    """

    __table_args__ = (UniqueConstraint("greenhouse_id", "hour"),)

    id: int | None = Field(default=None, primary_key=True)
    greenhouse_id: int = Field(foreign_key="greenhouse.id", index=True)
    hour: NaiveDatetime  # 사실 시트 기준 정시 (온실 현지 시각)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str  # "rule" | "llm"
    candidates: list[dict] = Field(sa_column=Column(JSON))
    fact_sheet: dict = Field(sa_column=Column(JSON))
    # 만들 때의 가드레일 결과 {passed, violations, fallback_reason}. 다시 조회할 때도 대체 사유를
    # 보여주려고 저장한다. 이 컬럼이 생기기 전 기록은 None (db.ensure_columns가 컬럼을 더함)
    guardrail: dict | None = Field(default=None, sa_column=Column(JSON))


class AdviceDecision(SQLModel, table=True):
    """후보별 "실행함"/"이번엔 안 함". 같은 후보를 다시 누르면 바꾼다. 설비 명령이 아니다."""

    __table_args__ = (UniqueConstraint("advice_id", "candidate_index"),)

    id: int | None = Field(default=None, primary_key=True)
    advice_id: int = Field(foreign_key="advicerecord.id", index=True)
    candidate_index: int
    decision: str  # "done" | "skipped"
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestToken(SQLModel, table=True):
    """수집 API 토큰 (온실당 1개). 원문은 발급할 때 한 번만 보여주고 SHA-256 해시만 저장한다.

    Greenhouse 컬럼이 아니라 별도 테이블인 이유: DB를 create_all로만 만들어서 기존 테이블에
    컬럼을 더하면 이미 있는 vpd.db에 반영되지 않는다. 새 테이블은 기존 DB에도 생긴다.
    """

    id: int | None = Field(default=None, primary_key=True)
    greenhouse_id: int = Field(foreign_key="greenhouse.id", unique=True, index=True)
    token_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BandVersion(SQLModel, table=True):
    """적정 대역 변경 이력 (결정 2026-10-12, 구현 2026-10-31).

    effective_from부터 다음 버전 전날까지 그 대역으로 캘린더를 판정한다. None은 "처음부터"
    (가장 이른 데이터 날짜부터). 이력이 하나도 없는 온실은 현재 대역을 처음부터로 본다.
    """

    __table_args__ = (UniqueConstraint("greenhouse_id", "effective_from"),)

    id: int | None = Field(default=None, primary_key=True)
    greenhouse_id: int = Field(foreign_key="greenhouse.id", index=True)
    effective_from: date | None = None  # 온실 현지 날짜
    vpd_low: float
    vpd_high: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
