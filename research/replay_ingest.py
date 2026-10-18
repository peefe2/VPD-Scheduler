"""학습 온실 데이터를 현재 시각에 맞춰 수집 API로 흘려보내는 시연용 스크립트 (재생 모드).

실행: cd research; uv run --project ../backend python replay_ingest.py GH_ID SOURCE [옵션]
  --backfill-days D  원본 앞쪽 D일을 "지난 이력"으로 먼저 보낸다 (기본 35 = 첫 전환이
                     가능한 최소 이력, CLAUDE.md). 원본 D일째가 오늘 날짜가 된다.
  --speed X          그 뒤 정시를 보내는 속도. 1(기본)이면 실제 시계에 맞춰 매 정시에 1건.
                     X>1이면 3600/X초마다 1건 — 표시 시각이 실제 시계보다 앞서 나간다.
  --base-url URL     백엔드 주소 (기본 http://localhost:8000)

- 시각은 **날짜만** 통째로 옮긴다(일 단위). 시 단위로 옮기면 낮(09~17시)·밤 주기가
  실제 측정과 어긋나 캘린더와 모델 입력이 틀어진다.
- load_combined()로 읽으므로 결함 168행은 빠진다 (CLAUDE.md "데이터 결함").
- 학습 온실 데이터를 서비스 모델로 데모하면 in-sample 누수가 생긴다. 대상 온실은
  재생 모드(connection_type = replay)이고 holdout_source가 SOURCE여야 하며, 비어 있어야
  한다(다른 이동량으로 두 번 보내면 섞이므로).
- 이 스크립트의 PC 시계 = 온실 현지 시각이라고 가정한다.
"""

import argparse
import sys
import time
from datetime import datetime

import httpx
import pandas as pd

from reproduce_lgbm import load_combined

BATCH = 1000  # 백엔드 MAX_BATCH


def measurements(df: pd.DataFrame) -> list[dict]:
    return [
        {
            "measured_at": row.shown.isoformat(),
            "temperature": float(row.temp),
            "humidity": float(row.humidity),
            "co2": None if pd.isna(row.co2) else float(row.co2),
        }
        for row in df.itertuples()
    ]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("greenhouse_id", type=int)
    p.add_argument("source")
    p.add_argument("--backfill-days", type=int, default=35)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--base-url", default="http://localhost:8000")
    args = p.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # 오래 도는 스크립트라 로그를 바로 보이게

    client = httpx.Client(base_url=args.base_url, timeout=60)
    gh_id = args.greenhouse_id
    gh = client.get(f"/greenhouses/{gh_id}").raise_for_status().json()
    if gh["connection_type"] != "replay":
        sys.exit("온실 연결 방식이 재생 모드가 아닙니다.")
    if gh["holdout_source"] != args.source:
        sys.exit(f"온실 holdout_source가 {gh['holdout_source']!r}입니다. 학습 온실 데이터는 "
                 f"holdout_source={args.source!r}로 지정한 온실에만 보낼 수 있습니다 (in-sample 누수 방지).")
    if client.get(f"/greenhouses/{gh_id}/today").raise_for_status().json()["latest"] is not None:
        sys.exit("이미 값이 있는 온실입니다. 새 재생 온실을 만들어 주세요.")

    df = load_combined()
    df = df[df["source"] == args.source].sort_values("date")
    if df.empty:
        sys.exit(f"소스 {args.source!r} 데이터가 없습니다.")

    now = datetime.now()
    first_day = df["date"].iloc[0].normalize()
    shift = pd.Timestamp(now).normalize() - (first_day + pd.Timedelta(days=args.backfill_days))
    df = df.assign(shown=df["date"] + shift)
    print(f"원본 {first_day.date()} ~ {df['date'].iloc[-1].date()} → 표시 {df['shown'].iloc[0].date()} ~ "
          f"{df['shown'].iloc[-1].date()} (날짜만 {shift.days}일 이동, 시각은 그대로)")

    url = f"/greenhouses/{gh_id}/ingest"
    past, future = df[df["shown"] <= now], df[df["shown"] > now]
    rows = measurements(past)
    for i in range(0, len(rows), BATCH):
        res = client.post(url, json={"measurements": rows[i:i + BATCH]}).raise_for_status().json()
        print(f"지난 이력 {len(rows[i:i + BATCH])}건: {res}")

    print(f"남은 {len(future)}건을 {'실제 시계에 맞춰' if args.speed == 1 else f'{args.speed:g}배속으로'} 보냅니다. Ctrl+C로 멈춤.")
    for m, shown in zip(measurements(future), future["shown"]):
        if args.speed == 1:
            time.sleep(max(0.0, (shown - pd.Timestamp(datetime.now())).total_seconds()))
        else:
            time.sleep(3600 / args.speed)
        res = client.post(url, json={"measurements": [m]}).raise_for_status().json()
        print(f"{m['measured_at']}: {res}")


if __name__ == "__main__":
    main()
