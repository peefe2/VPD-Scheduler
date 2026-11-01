import re

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.auth import (
    COOKIE, cookie_options, end_session, hash_password, require_user, start_session, verify_password,
)
from app.db import get_session
from app.models import Greenhouse, User

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
LOGIN_FAILED = "이메일 또는 비밀번호가 맞지 않습니다."


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL.fullmatch(v):
            raise ValueError("이메일 형식이 아닙니다")
        return v


def _me(user: User) -> dict:
    return {"id": user.id, "email": user.email}


@router.post("/signup", status_code=201)
def signup(body: Credentials, response: Response, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.email == body.email)).first() is not None:
        raise HTTPException(409, "이미 가입된 이메일입니다.")
    first = session.exec(select(User)).first() is None
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    if first:
        # 로그인 기능 전부터 있던 온실(주인 없음, 공개 아님)은 처음 가입한 계정이 가져간다
        for gh in session.exec(select(Greenhouse).where(Greenhouse.owner_id == None,  # noqa: E711
                                                        Greenhouse.public == False)).all():  # noqa: E712
            gh.owner_id = user.id
            session.add(gh)
        session.commit()
    response.set_cookie(value=start_session(session, user), **cookie_options())
    return _me(user)


@router.post("/login")
def login(body: Credentials, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, LOGIN_FAILED)  # 가입 여부를 알려주지 않는다
    response.set_cookie(value=start_session(session, user), **cookie_options())
    return _me(user)


@router.post("/logout", status_code=204)
def logout(response: Response, session: Session = Depends(get_session),
           vpd_session: str | None = Cookie(default=None)):
    end_session(session, vpd_session)
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(user: User = Depends(require_user)):
    return _me(user)
