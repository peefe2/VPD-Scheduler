"""백테스트 · 자동 전환 상태 머신 (CLAUDE.md "백테스트 · 자동 전환 상태 머신").

- 이력 시작일 0시부터 비중첩 7일 버킷. 버킷이 끝나야 한 번 판정한다.
- 표본은 예측 대상 시각(target_at) 기준으로 버킷에 들어간다.
- 학습 중 구간(버킷 1·2 = 처음 14일)은 판정에 넣지 않는다. 결과는 보여주되
  연속 확인은 3주차부터 센다 → 첫 전환은 빨라야 35일째(3·4·5주차). (N=14와 연속
  확인이 같은 14일 데이터로 동시에 만족되면 추가 안전판이 0이 되기 때문.)
- persistence → model: 판정된 버킷 3개 연속 개선율 > 0.
- model → persistence: 버킷 1개라도 개선율 <= 0이면 즉시.
- 판정 불가(표본 부족) 버킷: 1개는 상태 유지, 2개 연속이면 persistence로 강제
  복귀 (검증 없이 모델 사용이 계속되는 것을 막음).
- 이력 14일 미만: 학습 중. CO2 없는 온실: 영구 persistence. +6h: 항상 참고용.
상태는 저장하지 않고 이력 전체에서 매번 다시 계산한다.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import numpy as np
import pandas as pd

BUCKET = pd.Timedelta(days=7)
MIN_HISTORY = pd.Timedelta(days=14)
LEARNING_BUCKETS = MIN_HISTORY // BUCKET  # 판정에서 빼는 앞쪽 버킷 수 (2)
# 전환에 필요한 연속 개선 버킷 수. 2→3 (2026-10-12): 그룹B에서 0 근처 흔들림의 우연한
# 2연속에 걸려 전환되던 것을 막음. 근거: research/simulate_k.py 리플레이.
SWITCH_STREAK = 3
# 판정 불가가 이만큼 연속이면 강제 복귀. SWITCH_STREAK와 일부러 분리 — k를 올려도
# 이 안전장치가 같이 느슨해지면 안 된다.
INSUFFICIENT_LIMIT = 2
# 7일×24의 절반. 표본 40·79건(농가4·5 LOSO)이 노이즈로 판정됐던 것보다 위로 잡은
# 감각적 여유치이지 통계적으로 정한 값은 아니다 (CLAUDE.md TODO).
MIN_BUCKET_SAMPLES = 84
REFERENCE_ONLY_HORIZONS = {6}


class State(StrEnum):
    LEARNING = "learning"  # 이력 14일 미만, persistence만 표시
    PERSISTENCE = "persistence"
    MODEL = "model"
    NO_CO2 = "no_co2"  # CO2 센서 없음, 영구 persistence
    REFERENCE = "reference"  # +6h, 전환 판정 제외


class Verdict(StrEnum):
    BETTER = "better"  # 개선율 > 0
    NOT_BETTER = "not_better"  # 개선율 <= 0
    INSUFFICIENT = "insufficient"  # 표본 부족, 판정 불가


@dataclass
class Bucket:
    index: int
    start: datetime
    end: datetime  # 미포함
    n: int
    rmse_model: float | None
    rmse_persistence: float | None
    improvement_pct: float | None
    verdict: Verdict
    state_after: State | None = None


@dataclass
class HorizonStatus:
    horizon: int
    state: State
    buckets: list[Bucket] = field(default_factory=list)
    next_judgment_at: datetime | None = None
    reason: str = ""


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def make_buckets(samples: pd.DataFrame, history_start: datetime, data_end: datetime) -> list[Bucket]:
    """끝난 버킷만 만든다. data_end: 마지막 실측 정시 (그 정시까지 관측됨)."""
    anchor = pd.Timestamp(history_start).normalize()
    observed_until = pd.Timestamp(data_end) + pd.Timedelta(hours=1)
    buckets = []
    k = 0
    while anchor + (k + 1) * BUCKET <= observed_until:
        start, end = anchor + k * BUCKET, anchor + (k + 1) * BUCKET
        if samples.empty:
            sel = samples
        else:
            sel = samples[(samples["target_at"] >= start) & (samples["target_at"] < end)]
        n = len(sel)
        if n < MIN_BUCKET_SAMPLES:
            buckets.append(Bucket(k, start.to_pydatetime(), end.to_pydatetime(), n,
                                  None, None, None, Verdict.INSUFFICIENT))
        else:
            actual = sel["actual"].to_numpy()
            r_m = _rmse(actual, sel["model"].to_numpy())
            r_p = _rmse(actual, sel["persistence"].to_numpy())
            imp = (r_p - r_m) / r_p * 100 if r_p > 0 else 0.0
            buckets.append(Bucket(k, start.to_pydatetime(), end.to_pydatetime(), n,
                                  r_m, r_p, imp,
                                  Verdict.BETTER if imp > 0 else Verdict.NOT_BETTER))
        k += 1
    return buckets


def run_state_machine(
    buckets: list[Bucket],
    switch_streak: int = SWITCH_STREAK,
    insufficient_limit: int = INSUFFICIENT_LIMIT,
) -> State:
    """버킷 판정을 순서대로 적용. 각 버킷의 state_after를 채우고 최종 상태를 반환."""
    state = State.PERSISTENCE
    streak = 0
    insufficient = 0
    for b in buckets:
        if b.index < LEARNING_BUCKETS:
            b.state_after = State.LEARNING
            continue
        if b.verdict is Verdict.INSUFFICIENT:
            streak = 0
            insufficient += 1
            if insufficient >= insufficient_limit:
                state = State.PERSISTENCE
        else:
            insufficient = 0
            if b.verdict is Verdict.BETTER:
                streak += 1
                if state is State.PERSISTENCE and streak >= switch_streak:
                    state = State.MODEL
            else:
                streak = 0
                state = State.PERSISTENCE
        b.state_after = state
    return state


def evaluate_horizon(
    horizon: int,
    samples: pd.DataFrame,
    history_start: datetime | None,
    data_end: datetime | None,
    has_co2: bool,
) -> HorizonStatus:
    if history_start is None or data_end is None:
        return HorizonStatus(horizon, State.LEARNING, reason="실측 데이터 없음")

    anchor = pd.Timestamp(history_start).normalize()
    observed_until = pd.Timestamp(data_end) + pd.Timedelta(hours=1)
    buckets = make_buckets(samples, history_start, data_end)
    done = len(buckets)
    next_judgment = (anchor + (done + 1) * BUCKET).to_pydatetime()

    if not has_co2:
        return HorizonStatus(horizon, State.NO_CO2, buckets, None,
                             "CO2 센서가 없어 모델을 쓰지 않습니다")
    if observed_until - anchor < MIN_HISTORY:
        return HorizonStatus(horizon, State.LEARNING, buckets, next_judgment,
                             "이력 14일 미만")
    if horizon in REFERENCE_ONLY_HORIZONS:
        return HorizonStatus(horizon, State.REFERENCE, buckets, None,
                             "+6h는 검증 표본이 적어 참고용으로만 표시합니다")
    state = run_state_machine(buckets)
    return HorizonStatus(horizon, state, buckets, next_judgment)
