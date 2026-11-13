"""Notifications (FR-011, FR-022). Built from current data, so they are never out of date."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.core.db import get_db
from app.core.security import current_user
from app.models import DailyTaskLog, LeaveRequest, ProjectTemplate, TimesheetLock, UnlockRequest, User
from app.services import rules

router = APIRouter(prefix="/notifications", tags=["notifications"])

LOOKBACK_DAYS = 14


@router.get("", response_model=list[schemas.NotificationOut], response_model_by_alias=True)
def notifications(db: Session = Depends(get_db), me: User = Depends(current_user)):
    today = date.today()
    start = today - timedelta(days=LOOKBACK_DAYS)
    out: list[schemas.NotificationOut] = []

    def add(type_: str, day: date, message: str, link: str) -> None:
        out.append(schemas.NotificationOut(id=len(out) + 1, user_id=me.user_id, type=type_, date=day, message=message, link=link, read=False))

    # Days under 8 hours; leave counts toward the 8 hours (FR-020).
    logged: dict[date, int] = {}
    for d, m in db.execute(select(DailyTaskLog.log_date, DailyTaskLog.effort_minutes).where(
        DailyTaskLog.user_id == me.user_id, DailyTaskLog.entry_type == "work", DailyTaskLog.log_date >= start, DailyTaskLog.log_date < today
    )):
        logged[d] = logged.get(d, 0) + (m or 0)
    leaves = [(l.start_date, l.end_date, l.day_part) for l in db.scalars(select(LeaveRequest).where(
        LeaveRequest.user_id == me.user_id, LeaveRequest.status == "filed", LeaveRequest.end_date >= start
    ))]
    locks = [(l.start_date, l.end_date) for l in db.scalars(select(TimesheetLock).where(TimesheetLock.end_date >= start))]
    for d in rules.workdays(start, today - timedelta(days=1)):
        short = rules.minutes_short(logged.get(d, 0), rules.leave_minutes_on(d, leaves), d)
        if short:
            is_locked = any(s <= d <= e for s, e in locks)
            add("locked_day" if is_locked else "under_8h", d, f"{short / 60:g}h short", f"/activity?date={d.isoformat()}")

    # Decisions on my unlock requests.
    for r in db.scalars(select(UnlockRequest).where(UnlockRequest.user_id == me.user_id, UnlockRequest.status != "pending", UnlockRequest.request_date >= start)):
        add("unlock_decision", r.request_date, f"Unlock request {r.status}", f"/activity?date={r.request_date.isoformat()}")

    # Manager / Admin: locked days waiting for verification, templates waiting for approval.
    if me.role in rules.MANAGERS:
        names = dict(db.execute(select(User.user_id, User.user_name)).all())
        for r in db.scalars(select(UnlockRequest).where(UnlockRequest.status == "pending")):
            add("lock_verification", r.request_date, f"{names.get(r.user_id, 'Someone')} asks to {r.action_type} time on a locked day", "/locks")
        if me.role == "manager":
            for t in db.scalars(select(ProjectTemplate).where(ProjectTemplate.approval_status == "pending")):
                add("template_approval", today, f'Template "{t.template_name}" waits for approval', "/setup")
    return out
