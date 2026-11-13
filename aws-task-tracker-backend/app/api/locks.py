"""Locks, unlock requests and the 72-hour window (FR-025, FR-026, FR-027)."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.db import get_db
from app.core.errors import forbidden
from app.core.security import current_user, require
from app.models import LockOverride, TimesheetLock, UnlockRequest, User
from app.services import access, rules

router = APIRouter(prefix="/locks", tags=["locks"])


def expire_old_requests(db: Session) -> int:
    """Pending requests older than 72 hours become 'expired' (FR-011). Also run by the scheduler."""
    res = db.execute(
        update(UnlockRequest).where(UnlockRequest.status == "pending", UnlockRequest.expires_at <= datetime.now(timezone.utc)).values(status="expired")
    )
    return res.rowcount or 0


@router.get("", response_model=list[schemas.LockOut], response_model_by_alias=True)
def list_locks(db: Session = Depends(get_db), me: User = Depends(current_user)):
    return [convert.lock(l) for l in db.scalars(select(TimesheetLock).order_by(TimesheetLock.start_date.desc()))]


@router.post("", status_code=201)
def add_lock(body: schemas.LockIn, db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS))):
    rules.check_range(body.start_date, body.end_date, max_days=366)
    l = TimesheetLock(start_date=body.start_date, end_date=body.end_date, locked_by=me.user_id, lock_reason=body.reason)
    db.add(l)
    db.flush()
    audit(db, me.user_id, "lock", "timesheet_locks", l.lock_id, reason=body.reason, new={"start": str(body.start_date), "end": str(body.end_date)})
    return {"id": l.lock_id}


@router.delete("/{lock_id}", status_code=204)
def remove_lock(lock_id: int, db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS))):
    l = access.get_or_404(db, TimesheetLock, lock_id)
    audit(db, me.user_id, "unlock", "timesheet_locks", lock_id, old={"start": str(l.start_date), "end": str(l.end_date)})
    db.delete(l)  # its unlock requests are removed with it (ON DELETE CASCADE)


@router.get("/open", response_model=bool)
def is_open(user_id: int = Query(alias="userId"), day: date = Query(alias="date"), db: Session = Depends(get_db), me: User = Depends(current_user)):
    access.check_user_visible(db, me, user_id)
    return access.lock_state(db, user_id, day).open_for_user


@router.get("/requests", response_model=list[schemas.UnlockOut], response_model_by_alias=True)
def list_requests(db: Session = Depends(get_db), me: User = Depends(current_user)):
    expire_old_requests(db)
    ids = access.visible_user_ids(db, me)
    q = select(UnlockRequest).where(UnlockRequest.user_id.in_(ids)).order_by(UnlockRequest.created_date.desc())
    return [convert.unlock(r) for r in db.scalars(q)]


@router.post("/requests", status_code=201)
def request_unlock(body: schemas.UnlockIn, db: Session = Depends(get_db), me: User = Depends(current_user)):
    lock = db.scalar(select(TimesheetLock).where(TimesheetLock.start_date <= body.date, TimesheetLock.end_date >= body.date))
    if lock is None:
        raise rules.RuleError("Those dates are not locked")
    if not body.reason.strip():
        raise rules.RuleError("A reason is required", status=422)
    approver = db.scalar(select(User.user_id).where(User.role == "manager", User.active_flag.is_(True)).order_by(User.user_id))
    now = datetime.now(timezone.utc)
    r = UnlockRequest(
        user_id=me.user_id, lock_id=lock.lock_id, request_date=body.date, action_type=body.action, reason=body.reason,
        details=body.details, approver_id=approver, created_date=now, expires_at=rules.unlock_expiry(now),
    )
    db.add(r)
    db.flush()
    audit(db, me.user_id, "unlock_request", "unlock_requests", r.request_id, reason=body.reason, new={"date": str(body.date), "action": body.action})
    return {"id": r.request_id}


def _decide(db: Session, me: User, request_id: int, allow: bool) -> None:
    expire_old_requests(db)
    r = access.get_or_404(db, UnlockRequest, request_id)
    if r.user_id == me.user_id:
        raise forbidden("You cannot decide your own request")
    if r.status != "pending":
        raise rules.RuleError(f"This request is {r.status}")
    now = datetime.now(timezone.utc)
    r.status, r.decided_by, r.decided_date = ("allowed" if allow else "declined"), me.user_id, now
    if allow:
        # Opens that one day for that one person for 72 hours.
        db.add(LockOverride(request_id=r.request_id, user_id=r.user_id, unlocked_date=r.request_date, expiry_date=rules.unlock_expiry(now), approved_by=me.user_id))
    audit(db, me.user_id, "unlock_allowed" if allow else "unlock_declined", "unlock_requests", request_id)


@router.post("/requests/{request_id}/allow", status_code=204)
def allow(request_id: int, db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS))):
    _decide(db, me, request_id, True)


@router.post("/requests/{request_id}/decline", status_code=204)
def decline(request_id: int, db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS))):
    _decide(db, me, request_id, False)
