"""전환 기준 k(연속 개선 주 수)를 바꿔 학습 온실 10곳을 LOSO 모델로 리플레이.

각 온실은 그 온실을 뺀 모델(backend/models/loso)로 백테스트하므로 in-sample 누수 없음.
주 w의 판정으로 정해진 상태는 다음 주 w+1에 적용된다고 보고:
  - 피해 주: 모델 사용 상태였는데 그 주 실제로 모델이 persistence보다 못했던 주
  - 놓친 주: persistence 상태였는데 그 주 실제로 모델이 더 나았던 주
실행: uv run --project ../backend python simulate_k.py
"""

import sys

import pandas as pd

sys.path.insert(0, "../backend")
from app.forecast import backtest_samples, predictor_for  # noqa: E402
from app.switching import LEARNING_BUCKETS, State, Verdict, make_buckets, run_state_machine  # noqa: E402
from app.vpd import vpd  # noqa: E402
from reproduce_lgbm import load_combined  # noqa: E402

GH24 = {"gh24_1온실", "gh24_2온실", "gh24_3온실", "gh24_4온실"}
KS = (2, 3)


def replay(buckets, k):
    for b in buckets:
        b.state_after = None
    final = run_state_machine(buckets, switch_streak=k, insufficient_limit=2)
    judged = [b for b in buckets if b.index >= LEARNING_BUCKETS]
    switches = sum(1 for prev, cur in zip(judged, judged[1:])
                   if prev.state_after is not State.MODEL and cur.state_after is State.MODEL)
    if judged and judged[0].state_after is State.MODEL:
        switches += 1
    first = next((b.index + 1 for b in judged if b.state_after is State.MODEL), None)  # 몇 주차 끝에 전환
    harm = missed = model_weeks = 0
    for prev, cur in zip(judged, judged[1:]):
        if prev.state_after is State.MODEL:
            model_weeks += 1
            harm += cur.verdict is Verdict.NOT_BETTER
        elif cur.verdict is Verdict.BETTER:
            missed += 1
    return dict(final=final.value, switches=switches, first_switch_week=first,
                model_weeks=model_weeks, harm=harm, missed=missed)


def main():
    comb = load_combined(clean=True)
    rows = []
    for src, d in comb.groupby("source"):
        hourly = d.set_index("date").rename(columns={"temp": "temperature", "VPD": "vpd"})
        hourly = hourly[["temperature", "humidity", "co2"]].assign(
            vpd=lambda x: vpd(x.temperature, x.humidity))
        predictor, _ = predictor_for(src)
        for h in (1, 3):
            s = backtest_samples(hourly, h, predictor)
            buckets = make_buckets(s, hourly.index.min(), hourly.index.max())
            pattern = "".join({"better": "+", "not_better": "-", "insufficient": "?"}[b.verdict]
                              for b in buckets[LEARNING_BUCKETS:])
            for k in KS:
                rows.append(dict(source=src, group="B" if src in GH24 else "A", h=h, k=k,
                                 judged=pattern or "(없음)", **replay(buckets, k)))
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(res.to_string(index=False))
    print()
    print(res.groupby(["group", "h", "k"])[["switches", "model_weeks", "harm", "missed"]].sum().to_string())


if __name__ == "__main__":
    main()
