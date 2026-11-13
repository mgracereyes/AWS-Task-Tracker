"""Turn database rows into API responses."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.models import AuditLog, Item, LeaveRequest, Project, ProjectMember, Task, TimesheetLock, UnlockRequest, User


def hhmm(t) -> str | None:
    return t.strftime("%H:%M") if t else None


def last_sign_in(db: Session, user_ids: list[int]) -> dict[int, str]:
    rows = db.execute(
        select(AuditLog.actor_id, func.max(AuditLog.timestamp)).where(AuditLog.action == "login", AuditLog.actor_id.in_(user_ids)).group_by(AuditLog.actor_id)
    ).all()
    return {uid: ts.strftime("%d %b %Y %H:%M") for uid, ts in rows}


def user(u: User, last: str = "—") -> schemas.UserOut:
    return schemas.UserOut(
        id=u.user_id, name=u.user_name, email=u.google_account, role=u.role, team_lead_id=u.team_lead_id,
        business_unit=u.business_unit, active=u.active_flag, last_sign_in=last,
    )


def project(p: Project) -> schemas.ProjectOut:
    return schemas.ProjectOut(id=p.project_id, name=p.project_name, description=p.description or "", visibility=p.visibility, active=p.active_flag, lead_id=p.owner_id)


def task(t: Task) -> schemas.TaskOut:
    return schemas.TaskOut(id=t.task_id, project_id=t.project_id, name=t.task_name, active=t.active_flag)


def item(i: Item) -> schemas.ItemOut:
    return schemas.ItemOut(id=i.item_id, task_id=i.task_id, name=i.item_name, work_type=i.work_type, planned_minutes=i.planned_minutes, active=i.active_flag)


def member(m: ProjectMember) -> schemas.MemberOut:
    return schemas.MemberOut(id=m.project_member_id, project_id=m.project_id, user_id=m.user_id, role_on_project=m.role_on_project or "", start_date=m.start_date, end_date=m.end_date)


def leave(l: LeaveRequest) -> schemas.LeaveOut:
    return schemas.LeaveOut(id=l.leave_id, user_id=l.user_id, type=l.leave_type, start_date=l.start_date, end_date=l.end_date, day_part=l.day_part, hours=float(l.hours_credited), status=l.status)


def lock(l: TimesheetLock) -> schemas.LockOut:
    return schemas.LockOut(id=l.lock_id, start_date=l.start_date, end_date=l.end_date, locked_by=l.locked_by, reason=l.lock_reason or "")


def iso(dt: datetime) -> str:
    return dt.isoformat()


def unlock(r: UnlockRequest) -> schemas.UnlockOut:
    return schemas.UnlockOut(
        id=r.request_id, user_id=r.user_id, date=r.request_date, action=r.action_type, reason=r.reason, details=r.details or "",
        status=r.status, created_at=iso(r.created_date), expires_at=iso(r.expires_at),
    )


def audit_row(a: AuditLog) -> schemas.AuditOut:
    target = f"{a.target_table} {a.target_id}" if a.target_table else ""
    if a.details:
        target = (target + " " + ", ".join(f"{k}={v}" for k, v in a.details.items())).strip()
    return schemas.AuditOut(id=a.audit_id, actor_id=a.actor_id, action=a.action, target=target, reason=a.reason or "", at=a.timestamp.strftime("%Y-%m-%d %H:%M"))
