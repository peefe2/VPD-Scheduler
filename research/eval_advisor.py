"""AI 어드바이저 자유 질문을 실제 Gemini로 돌려 통과율·대체 사유·응답 시간을 잰다 (품질 평가).

실행: cd research; uv run --project ../backend python eval_advisor.py [옵션]
  (VPD_ADVISOR_LLM=1, GEMINI_API_KEY 필요. 키는 환경변수로만)
  --repeat N   상황 × 질문 조합을 N번 반복 (기본 2 — 같은 질문도 답이 매번 다르다)
  --delay S    호출 사이 쉬는 초 (기본 4 — 무료 등급 분당 호출 한도)
  --out DIR    결과 저장 폴더 (기본 eval_out/, git에 안 올림)

- 상황 3종(대역 아래·위·안이지만 곧 벗어남) × 질문 10개. 질문에는 등록·미등록 설비, 시간,
  숫자, 측정값과 무관한 질문을 섞었다.
- "통과"는 가드레일을 넘어 LLM 답이 그대로 쓰인 비율일 뿐, 답이 좋다는 뜻은 아니다.
  답변 전문을 .md로 남기니 사람이 읽고 판단한다.
- Gemini 무료 등급은 보낸 내용이 Google 제품 개선에 쓰일 수 있다. 여기 사실 시트는 가상 값이다.
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import advisor  # noqa: E402
from app.advisor import answer_question  # noqa: E402


def fact(status, vpd, run, temperature, humidity, equipment, forecasts):
    return {
        "greenhouse": {"name": "1동", "crop": "토마토", "band": {"low": 0.5, "high": 1.5},
                       "equipment": equipment},
        "observed_at": "2026-11-01 10:00:00",
        "current": {"vpd": vpd, "temperature": temperature, "humidity": humidity, "co2": 420,
                    "band_status": status, "run_hours": run},
        "forecasts": [{"horizon": h, "vpd": v, "band_status": s, "reference": h == 6} for h, v, s in forecasts],
        "mode": "model",
    }


SITUATIONS = {
    "below": fact("below", 0.28, 17, 20.0, 88.2, ["vent", "dehumidifier", "heater"],
                  [(1, 0.40, "below"), (3, 0.44, "below"), (6, 0.44, "below")]),
    "above": fact("above", 1.82, 4, 29.5, 56.0, ["vent", "humidifier", "shade_screen"],
                  [(1, 1.90, "above"), (3, 1.71, "above"), (6, 1.20, "in")]),
    "in_leaving": fact("in", 1.35, 6, 26.1, 61.3, ["vent", "exhaust_fan", "heater"],
                       [(1, 1.62, "above"), (3, 1.70, "above"), (6, 1.10, "in")]),
}

WRONG_DIRECTION = {"below": ["가습"], "above": ["난방", "제습"], "in_leaving": ["난방", "제습"]}

QUESTIONS = [
    "지금 뭐 해야 해?",
    "지금 환기를 해도 될까요?",
    "난방 켜는 게 나아 제습기 켜는 게 나아?",
    "차광막 쳐야 해?",
    "가습기 틀어도 돼?",
    "제습기 몇 시간 돌려야 해?",
    "습도 몇 %로 맞추면 돼?",
    "오늘 오후에는 어떻게 될까?",
    "왜 VPD가 이렇게 나와?",
    "토마토 잎이 시들어 보이는데 왜 그래?",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repeat", type=int, default=2)
    p.add_argument("--delay", type=float, default=4.0)
    p.add_argument("--out", default=str(Path(__file__).parent / "eval_out"))
    args = p.parse_args()
    if os.environ.get(advisor.LLM_ENV) != "1" or not os.environ.get("GEMINI_API_KEY"):
        sys.exit("VPD_ADVISOR_LLM=1과 GEMINI_API_KEY 환경변수가 필요합니다.")

    calls = Counter()
    ask = advisor._ask_gemini

    def counting_ask(*a, **kw):  # 질문 하나에 Gemini를 몇 번 불렀는지 (재질문 포함)
        calls["n"] += 1
        return ask(*a, **kw)

    advisor._ask_gemini = counting_ask

    rows = []
    for rep in range(args.repeat):
        for sit, f in SITUATIONS.items():
            for q in QUESTIONS:
                before, t = calls["n"], time.time()
                r = answer_question(q, f)
                rows.append({"repeat": rep, "situation": sit, "question": q, "source": r["source"],
                             "note": r.get("note", ""), "violations": r["violations"], "answer": r["answer"],
                             "seconds": round(time.time() - t, 1), "gemini_calls": calls["n"] - before})
                print(f"[{rep}] {sit:10} {r['source']:4} {rows[-1]['seconds']:5}s {q}", flush=True)
                time.sleep(args.delay)

    n = len(rows)
    passed = sum(r["source"] != "rule" for r in rows)
    # 미등록 설비 질문에 LLM 없이 바로 답한 것 (실패가 아니라 의도한 안내)
    guided = sum(r["note"] == getattr(advisor, "UNREGISTERED_NOTE", None) for r in rows)
    # 반대 방향 설비를 꺼낸 LLM 답 (가드레일이 못 잡는 오류): 대역 위로 가는데 VPD를 더 올리는
    # 난방·제습, 대역 아래인데 VPD를 더 내리는 가습. 질문에 그 설비가 나온 경우는 뺀다.
    wrong = [r for r in rows if r["source"] == "llm"
             and any(w in r["answer"] and w not in r["question"] for w in WRONG_DIRECTION[r["situation"]])]
    reasons = Counter(v.split(":")[0] for r in rows for v in r["violations"])
    reasons.update("호출 실패" for r in rows if r["note"] == advisor.LLM_FAILED)
    secs = sorted(r["seconds"] for r in rows)
    summary = {
        "model": os.environ.get(advisor.MODEL_ENV, advisor.DEFAULT_MODEL),
        "answers": n, "llm_used": passed, "pass_rate": round(passed / n, 3),
        "unregistered_guided": guided, "fallback_rate": round((n - passed - guided) / n, 3),
        "wrong_direction": len(wrong),
        "by_situation": {s: sum(r["source"] != "rule" for r in rows if r["situation"] == s) for s in SITUATIONS},
        "fallback_reasons": dict(reasons),
        "seconds_median": secs[n // 2], "seconds_max": secs[-1],
        "gemini_calls": calls["n"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out / f"advisor_{stamp}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 어드바이저 질문 평가 {stamp}", "", f"```json\n{json.dumps(summary, ensure_ascii=False, indent=1)}\n```", ""]
    for r in rows:
        mark = "LLM" if r["source"] != "rule" else f"규칙 대체 ({', '.join(r['violations']) or r['note']})"
        lines += [f"## [{r['repeat']}] {r['situation']} · {r['question']}", f"*{mark}, {r['seconds']}초*", "",
                  r["answer"], ""]
    (out / f"advisor_{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"저장: {out / f'advisor_{stamp}.md'}")


if __name__ == "__main__":
    main()
