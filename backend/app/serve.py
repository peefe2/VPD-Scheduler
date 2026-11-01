"""실행 진입점: `uv run uvicorn app.serve:app --port 8000` (개발·시연·배포 모두).

1. backend/.env를 읽는다 (GEMINI_API_KEY, VPD_ADVISOR_LLM, VPD_DEMO 등 — .env.example 참고).
   이미 있는 환경변수는 덮어쓰지 않는다(배포 서버 설정이 우선). 테스트는 이 파일을 import하지
   않아서 .env의 키로 실제 Gemini를 부르지 않는다.
2. API는 /api 아래, frontend/dist가 있으면 화면은 / 에서 (app.spa).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")

from app.main import app as api, startup  # noqa: E402  .env를 읽은 뒤에 (DB 주소가 import 때 정해진다)
from app.spa import create_app  # noqa: E402

app = create_app(api, startup, Path(os.environ.get("VPD_FRONTEND_DIST", BACKEND.parent / "frontend" / "dist")))
