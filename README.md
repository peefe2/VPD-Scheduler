# AI-Smart-Farmer-Scheduler
머신러닝 기반 수증기압차(VPD) 예측 모델 구축 및 스마트팜 의사결정 지원 캘린더 서비스

설계·결정 사항은 [CLAUDE.md](CLAUDE.md)에 있습니다.

## 설치 (처음 한 번)

필요한 것: Git, [uv](https://docs.astral.sh/uv/), Node.js 20 이상

```
git clone https://github.com/peefe2/VPD-Scheduler.git
cd VPD-Scheduler/backend
uv sync
cd ../frontend
npm install
```

## 실행 (터미널 2개)

```
cd backend
uv run uvicorn app.main:app --port 8000
```

```
cd frontend
npm run dev
```

브라우저에서 http://localhost:5173 을 엽니다. Windows에서는 `--reload`를 붙이면 코드 변경 후 재시작이
멈출 때가 있어 시연 때는 빼는 편이 안전합니다.

## 시연: 재생 모드

실제 센서 대신 연구 데이터(farm3)를 날짜만 오늘로 옮겨 정시마다 흘려보냅니다.

1. 화면에서 새 온실 등록 — 학습 온실(데모용) `farm3_2023`
2. 데이터 연결 단계에서 "재생 모드" 선택 → 화면에 나오는 명령을 세 번째 터미널에서 실행

   ```
   cd research
   uv run --project ../backend python replay_ingest.py <온실 id> farm3_2023
   ```

   앞 35일 이력을 먼저 보내고, 이후는 실제 시계에 맞춰 매 정시 1건. `--speed 60`이면 1분에 1시간씩
   (표시 시각이 실제보다 앞서 나감). 멈추려면 Ctrl+C.

## 테스트

```
cd backend
uv run pytest
cd ../frontend
npm run build
npx oxlint src
```
