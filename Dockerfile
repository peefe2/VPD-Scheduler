# 배포용 한 서버 이미지: 프론트를 빌드하고, 백엔드(app.serve)가 화면(/)과 API(/api)를 함께 준다.
# 켤 때 공개 데모 온실을 만든다. 이메일 가입·로그인한 사람만 자기 온실을 만들고, 로그인 안 한 방문자는
# 데모 온실 보기·질문만 (README "공개 배포").
# GEMINI_API_KEY·VPD_DATABASE_URL은 이미지에 넣지 않고 배포 서비스의 비밀 환경변수로 준다.

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
# LightGBM이 쓰는 OpenMP, 시간대 데이터
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 tzdata && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
# 서버 시각 = 온실 현지 시각으로 본다(데모 온실이 "지금"까지 채운다). 배포 서버 기본은 UTC라 그대로면
# 한국 시각보다 9시간 늦은 값이 "지금"으로 보였다 (Render 첫 배포 2026-11-01 확인)
ENV TZ=Asia/Seoul UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
# 데모 온실이 재생할 연구 데이터 (app/demo.py가 /app/research/data에서 읽는다)
COPY research/data/combined_hourly_pointsample.csv /app/research/data/
COPY --from=web /web/dist /app/frontend/dist

# HTTPS로만 쓰므로 세션 쿠키에 Secure를 붙인다
ENV VPD_DEMO=1 VPD_READONLY=0 VPD_ASK_PER_MINUTE=10 VPD_COOKIE_SECURE=1
EXPOSE 8000
CMD ["sh", "-c", "uv run --frozen --no-dev uvicorn app.serve:app --host 0.0.0.0 --port ${PORT:-8000}"]
