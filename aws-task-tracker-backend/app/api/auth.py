"""Sign-in and sign-out (FR-001, FR-002, FR-015)."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.errors import forbidden, not_found
from app.core.security import clear_session, current_user, set_session
from app.models import User
from app.services import rules

router = APIRouter(prefix="/auth", tags=["auth"])


def _sign_in(db: Session, email: str, name: str | None, response: Response) -> schemas.UserOut:
    try:
        email = rules.company_email(email, settings.allowed_domain)
    except rules.RuleError:
        audit(db, None, "login_denied", email=email.strip().lower())
        db.commit()  # keep the audit row even though the request fails
        raise
    user = db.scalar(select(User).where(func.lower(User.google_account) == email))
    if user is None:
        if name is None:
            # Development sign-in only finds existing profiles.
            raise not_found("No profile for this account yet. Ask an admin.")
        # First Google sign-in creates one Employee profile; ADMIN_EMAILS become Admin (FR-002).
        user = User(google_account=email, user_name=name, role="admin" if email in settings.admin_emails else "employee")
        db.add(user)
        db.flush()
        audit(db, user.user_id, "create_user", "users", user.user_id, new={"role": user.role})
    if not user.active_flag:
        raise forbidden("Your access is disabled. Contact an admin.")
    audit(db, user.user_id, "login", "users", user.user_id)
    set_session(response, user)
    return convert.user(user)


@router.post("/google", response_model=schemas.UserOut, response_model_by_alias=True)
def google_login(body: schemas.GoogleLoginIn, response: Response, db: Session = Depends(get_db)):
    """Verify a Google ID token from the sign-in button."""
    if not settings.google_client_id:
        raise forbidden("Google sign-in is not configured yet")
    from google.auth.transport import requests as grequests
    from google.oauth2 import id_token

    try:
        info = id_token.verify_oauth2_token(body.credential, grequests.Request(), settings.google_client_id)
    except ValueError:
        raise forbidden("Google sign-in failed")
    if not info.get("email_verified"):
        raise forbidden("Google account email is not verified")
    return _sign_in(db, info["email"], info.get("name") or info["email"].split("@")[0], response)


@router.post("/login", response_model=schemas.UserOut, response_model_by_alias=True)
def dev_login(body: schemas.LoginIn, response: Response, db: Session = Depends(get_db)):
    """Development sign-in by email while Google SSO is on hold (WBS T07). Off in production."""
    if not settings.dev_login:
        raise forbidden("Email sign-in is turned off")
    return _sign_in(db, body.email, None, response)


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_session(response)


@router.get("/me", response_model=schemas.UserOut, response_model_by_alias=True)
def me(user: User = Depends(current_user)):
    return convert.user(user)
