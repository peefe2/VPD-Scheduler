# 공개 시연용 한 서버 이미지: 프론트를 빌드하고, 백엔드(app.serve)가 화면(/)과 API(/api)를 함께 준다.
# 기본값은 읽기 전용 데모 — 켤 때 데모 온실을 만들고, 질문하기만 열어 둔다 (README "공개 시연 배포").
# GEMINI_API_KEY는 이미지에 넣지 않고 배포 서비스의 비밀 환경변수로 준다.

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
# LightGBM이 쓰는 OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
# 데모 온실이 재생할 연구 데이터 (app/demo.py가 /app/research/data에서 읽는다)
COPY research/data/combined_hourly_pointsample.csv /app/research/data/
COPY --from=web /web/dist /app/frontend/dist

ENV VPD_DEMO=1 VPD_READONLY=1 VPD_ASK_PER_MINUTE=10
EXPOSE 8000
CMD ["sh", "-c", "uv run --frozen --no-dev uvicorn app.serve:app --host 0.0.0.0 --port ${PORT:-8000}"]
