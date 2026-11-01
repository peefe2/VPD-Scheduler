"""한 서버로 배포: API(app.main)는 /api 아래에 붙이고, 빌드한 프론트(frontend/dist)는 / 에서 준다.

화면 주소(/g/1/advisor 등)는 서버에 파일이 없으므로 index.html을 돌려줘 React 라우터가 처리하게
한다. /api 아래 없는 주소는 그대로 404 (index.html로 감추지 않는다).
마운트한 앱의 시작 이벤트는 실행되지 않아서, DB 준비(startup)는 바깥 앱에서 부른다.
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def create_app(api: FastAPI, startup: Callable[[], None], dist: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        startup()
        yield

    root = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    root.mount("/api", api)
    if dist.is_dir():
        root.mount("/", SPAFiles(directory=dist, html=True), name="frontend")
    return root
