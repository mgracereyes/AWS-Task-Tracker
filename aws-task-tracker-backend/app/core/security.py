"""Session cookie, current user and role checks.

The session is a signed JWT in an httpOnly cookie, so the browser never stores a token
in JavaScript (rules/04, rules/06). Every request re-reads the user, so a deactivated user
loses access straight away (FR-015).
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import forbidden, unauthorized
from app.models import User

COOKIE = "tt_session"
ALGO = "HS256"


def set_session(response: Response, user: User) -> None:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)
    token = jwt.encode({"sub": str(user.user_id), "exp": exp}, settings.jwt_secret, algorithm=ALGO)
    response.set_cookie(
        COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="lax",
        max_age=settings.session_hours * 3600, path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise unauthorized()
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
    except jwt.PyJWTError:
        raise unauthorized("Your session has ended. Please sign in again.")
    user = db.get(User, int(data["sub"]))
    if user is None or not user.active_flag:
        raise unauthorized("Your access is disabled. Contact an admin.")
    return user


def require(*roles: str):
    """Dependency: the signed-in user must have one of these roles."""

    def check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise forbidden()
        return user

    return check
