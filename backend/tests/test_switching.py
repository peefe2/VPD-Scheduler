from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.switching import (
    MIN_BUCKET_SAMPLES,
    Bucket,
    State,
    Verdict,
    evaluate_horizon,
    make_buckets,
    run_state_machine,
)

B, N, I = Verdict.BETTER, Verdict.NOT_BETTER, Verdict.INSUFFICIENT
T0 = datetime(2026, 10, 1)


def buckets(*verdicts):
    """앞에 학습 중 버킷 2개(항상 BETTER — 판정에 안 들어가야 함)를 붙인다."""
    verdicts = (B, B) + verdicts
    return [
        Bucket(i, T0 + timedelta(days=7 * i), T0 + timedelta(days=7 * (i + 1)), 168,
               None, None, None, v)
        for i, v in enumerate(verdicts)
    ]


@pytest.mark.parametrize(
    "seq, expected",
    [
        ([], State.PERSISTENCE),
        ([B, B], State.PERSISTENCE),  # 2주로는 전환 안 함 (k=3)
        ([B, B, B], State.MODEL),  # 3주 연속이면 전환
        ([B, B, N, B], State.PERSISTENCE),  # 연속이 끊김
        ([B, B, B, N], State.PERSISTENCE),  # 1주만 나빠도 즉시 복귀
        ([B, B, B, N, B, B], State.PERSISTENCE),  # 복귀 후 다시 3주 필요
        ([B, B, B, N, B, B, B], State.MODEL),
        ([B, I, B, B], State.PERSISTENCE),  # 판정 불가는 연속을 끊음
        ([B, B, B, I], State.MODEL),  # 판정 불가 1주는 모델 사용을 유지
        ([B, B, B, I, N], State.PERSISTENCE),
        ([B, B, B, I, I], State.PERSISTENCE),  # 판정 불가 2주 연속이면 강제 복귀 (k와 무관)
        ([B, B, B, I, B, I], State.MODEL),  # 연속이 아니면 복귀 안 함
        ([I, I], State.PERSISTENCE),
        # gh24_4온실 +1h LOSO 리플레이 패턴: k=2면 끝의 2연속에 걸려 전환됐음
        ([B, N, N, N, N, N, N, N, N, N, B, N, N, N, B, B], State.PERSISTENCE),
    ],
)
def test_state_machine(seq, expected):
    assert run_state_machine(buckets(*seq)) == expected


def test_state_after_recorded_per_bucket():
    bs = buckets(B, B, B, N)
    run_state_machine(bs)
    assert [b.state_after for b in bs] == [
        State.LEARNING, State.LEARNING,
        State.PERSISTENCE, State.PERSISTENCE, State.MODEL, State.PERSISTENCE,
    ]


def test_learning_buckets_never_count_even_if_good():
    # 1·2주차가 좋아도 3·4주차 둘만으로는 전환 안 됨
    assert run_state_machine(buckets(B, B)) == State.PERSISTENCE


def test_k_is_a_parameter_for_replay():
    assert run_state_machine(buckets(B, B), switch_streak=2) == State.MODEL


def samples_for(days, model_err, persist_err, start=T0, every_hour=True):
    target = pd.date_range(start, periods=days * 24, freq="h")
    actual = np.ones(len(target))
    return pd.DataFrame({
        "target_at": target,
        "actual": actual,
        "model": actual + model_err,
        "persistence": actual + persist_err,
    })


def test_buckets_are_non_overlapping_and_only_closed_ones():
    s = samples_for(17, 0.05, 0.10)
    end = s["target_at"].max().to_pydatetime()
    bs = make_buckets(s, T0, end)
    assert len(bs) == 2  # 17일째 진행 중인 3번째 버킷은 판정하지 않음
    assert [b.n for b in bs] == [168, 168]
    assert bs[1].start == bs[0].end
    assert bs[0].improvement_pct == pytest.approx(50.0)
    assert bs[0].verdict is Verdict.BETTER


def test_bucket_anchor_is_midnight_of_first_day():
    s = samples_for(15, 0.05, 0.10, start=T0 + timedelta(hours=13))
    bs = make_buckets(s, T0 + timedelta(hours=13), s["target_at"].max().to_pydatetime())
    assert bs[0].start == T0
    assert bs[0].n == 7 * 24 - 13


def test_bucket_with_few_samples_is_insufficient():
    s = samples_for(14, 0.05, 0.10)
    s = s[~((s.target_at >= T0) & (s.target_at < T0 + timedelta(days=7)))
          | (s.index % 3 == 0)]  # 첫 주는 56개만 남김
    bs = make_buckets(s, T0, s["target_at"].max().to_pydatetime())
    assert bs[0].n < MIN_BUCKET_SAMPLES and bs[0].verdict is Verdict.INSUFFICIENT
    assert bs[1].verdict is Verdict.BETTER


def test_tie_counts_as_not_better():
    s = samples_for(7, 0.1, 0.1)
    bs = make_buckets(s, T0, s["target_at"].max().to_pydatetime())
    assert bs[0].verdict is Verdict.NOT_BETTER


def test_evaluate_learning_before_14_days():
    s = samples_for(13, 0.05, 0.10)
    st = evaluate_horizon(1, s, T0, s["target_at"].max().to_pydatetime(), has_co2=True)
    assert st.state is State.LEARNING
    assert st.next_judgment_at == T0 + timedelta(days=14)


@pytest.mark.parametrize("days, expected", [
    (14, State.PERSISTENCE), (28, State.PERSISTENCE), (34, State.PERSISTENCE), (35, State.MODEL),
])
def test_evaluate_first_switch_is_day_35(days, expected):
    s = samples_for(days, 0.05, 0.10)
    st = evaluate_horizon(1, s, T0, s["target_at"].max().to_pydatetime(), has_co2=True)
    assert st.state is expected


def test_evaluate_no_co2_is_permanent():
    s = samples_for(28, 0.05, 0.10)
    st = evaluate_horizon(1, s, T0, s["target_at"].max().to_pydatetime(), has_co2=False)
    assert st.state is State.NO_CO2


def test_evaluate_six_hour_is_reference_only():
    s = samples_for(28, 0.05, 0.10)
    st = evaluate_horizon(6, s, T0, s["target_at"].max().to_pydatetime(), has_co2=True)
    assert st.state is State.REFERENCE
    assert len(st.buckets) == 4  # 결과는 보여준다
