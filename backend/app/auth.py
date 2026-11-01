"""계정·세션과 온실 접근 규칙.

- 비밀번호: hashlib.scrypt(표준 라이브러리) + 무작위 salt. "scrypt$n$r$p$salt$hash"로 저장.
- 세션: 로그인하면 무작위 토큰을 HttpOnly 쿠키(vpd_session)로 주고, DB에는 SHA-256 해시만 둔다.
  화면과 API가 같은 주소(app.serve)라 쿠키 방식이 가장 단순하다. 배포(HTTPS)에서는
  VPD_COOKIE_SECURE=1로 Secure를 붙인다.
- 온실 접근(greenhouse_access): 보기(GET)·질문하기는 공개 온실이거나 내 온실이면, 나머지(바꾸기)는
  내 온실만. 볼 수 없는 온실은 없는 것처럼 404. 센서 수집(POST /ingest)은 온실 토큰으로 따로 인증한다.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models import Greenhouse, User, UserSession

COOKIE = "vpd_session"
SESSION_DAYS = 30
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(UserSession(token_hash=_token_hash(token), user_id=user.id,
                            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)))
    session.commit()
    return token


def end_session(session: Session, token: str | None) -> None:
    if token:
        row = session.exec(select(UserSession).where(UserSession.token_hash == _token_hash(token))).first()
        if row is not None:
            session.delete(row)
            session.commit()


def cookie_options() -> dict:
    return {"key": COOKIE, "httponly": True, "samesite": "lax", "path": "/",
            "secure": os.environ.get("VPD_COOKIE_SECURE") == "1", "max_age": SESSION_DAYS * 24 * 3600}


def optional_user(session: Session = Depends(get_session),
                  vpd_session: str | None = Cookie(default=None)) -> User | None:
    if not vpd_session:
        return None
    row = session.exec(select(UserSession).where(UserSession.token_hash == _token_hash(vpd_session))).first()
    # SQLite는 시각을 타임존 없이 돌려준다 — 저장할 때 UTC였으니 UTC로 본다
    if row is None or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return session.get(User, row.user_id)


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user


def can_read(gh: Greenhouse, user: User | None) -> bool:
    return gh.public or (user is not None and gh.owner_id == user.id)


def can_write(gh: Greenhouse, user: User | None) -> bool:
    return user is not None and gh.owner_id == user.id


def greenhouse_access(request: Request, greenhouse_id: int, session: Session = Depends(get_session),
                      user: User | None = Depends(optional_user)) -> None:
    """/greenhouses/{greenhouse_id}/... 라우트 공통 검사 (라우터 dependencies로 건다)."""
    path = request.url.path
    if request.method == "POST" and path.endswith("/ingest"):
        return  # 센서는 로그인하지 않는다 — 온실 토큰으로 인증 (routers/ingest.py)
    gh = session.get(Greenhouse, greenhouse_id)
    if gh is None or not can_read(gh, user):
        raise HTTPException(404, "greenhouse not found")
    changing = request.method not in ("GET", "HEAD") and not path.endswith("/advisor/ask")
    if changing and not can_write(gh, user):
        raise HTTPException(401 if user is None else 403,
                            "로그인이 필요합니다." if user is None else "이 온실을 바꿀 권한이 없습니다.")
