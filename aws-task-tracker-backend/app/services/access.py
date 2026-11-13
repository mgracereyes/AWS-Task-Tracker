"""Who can see what (FR-005, FR-009, FR-012, FR-029). Used by every endpoint that reads data."""
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import forbidden, locked, not_found
from app.models import DailyTaskLog, Item, LockOverride, Project, ProjectMember, Task, TimesheetLock, User
from app.services import rules


def get_or_404(db: Session, model, pk: int):
    row = db.get(model, pk)
    if row is None:
        raise not_found()
    return row


def team_ids(db: Session, lead_id: int) -> list[int]:
    return list(db.scalars(select(User.user_id).where(User.team_lead_id == lead_id)))


def visible_user_ids(db: Session, user: User) -> set[int]:
    """Own data; a team lead adds the team; Manager and Admin see everyone."""
    if user.role in rules.MANAGERS:
        return set(db.scalars(select(User.user_id)))
    if user.role == "team_lead":
        return {user.user_id, *team_ids(db, user.user_id)}
    return {user.user_id}


def member_project_ids(db: Session, user_id: int) -> set[int]:
    return set(db.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user_id, ProjectMember.active_flag.is_(True))))


def visible_project_ids(db: Session, user: User) -> set[int]:
    """Private projects only for members, their lead and Manager/Admin (FR-029)."""
    if user.role in rules.MANAGERS:
        return set(db.scalars(select(Project.project_id)))
    mine = member_project_ids(db, user.user_id)
    rows = db.execute(select(Project.project_id, Project.visibility, Project.owner_id)).all()
    if user.role == "team_lead":
        return {pid for pid, vis, owner in rows if vis == "public" or pid in mine or owner == user.user_id}
    return {pid for pid, _vis, owner in rows if pid in mine or owner == user.user_id}


def check_user_visible(db: Session, actor: User, user_id: int) -> None:
    if user_id not in visible_user_ids(db, actor):
        raise not_found()


def item_path(db: Session, item_id: int) -> tuple[Item, Task, Project]:
    item = db.get(Item, item_id)
    if item is None:
        raise not_found("Item not found")
    task = db.get(Task, item.task_id)
    project = db.get(Project, task.project_id)
    return item, task, project


def lock_state(db: Session, user_id: int, day: date) -> rules.LockState:
    ranges = db.execute(select(TimesheetLock.start_date, TimesheetLock.end_date).where(TimesheetLock.start_date <= day, TimesheetLock.end_date >= day)).all()
    overrides = db.execute(
        select(LockOverride.unlocked_date, LockOverride.expiry_date).where(
            LockOverride.user_id == user_id, LockOverride.unlocked_date == day, LockOverride.revoked_date.is_(None)
        )
    ).all()
    return rules.lock_state(day, [tuple(r) for r in ranges], [tuple(o) for o in overrides], datetime.now(timezone.utc))


def check_writable(db: Session, user: User, day: date, reason: str | None = None) -> None:
    try:
        rules.check_entry_date(day, date.today())
        rules.check_writable(lock_state(db, user.user_id, day), user.role, reason)
    except rules.RuleError as e:
        if e.status == 423:
            raise locked(str(e))
        raise


def check_writable_leave(db: Session, user: User, day: date) -> None:
    """Leave may be filed ahead of time, but not on a locked day without an open unlock."""
    try:
        rules.check_writable(lock_state(db, user.user_id, day), "employee", None)
    except rules.RuleError as e:
        raise locked(str(e))


def check_can_log(db: Session, user: User, item_id: int) -> tuple[Item, Task, Project]:
    item, task, project = item_path(db, item_id)
    if not (item.active_flag and task.active_flag and project.active_flag):
        raise rules.RuleError("This option is archived")
    if project.project_id not in member_project_ids(db, user.user_id):
        raise forbidden("This project is not assigned to you")
    return item, task, project


def day_minutes(db: Session, user_id: int, day: date, except_id: int | None = None) -> int:
    q = select(DailyTaskLog.effort_minutes).where(DailyTaskLog.user_id == user_id, DailyTaskLog.log_date == day, DailyTaskLog.entry_type == "work")
    if except_id is not None:
        q = q.where(DailyTaskLog.log_id != except_id)
    return sum(m or 0 for m in db.scalars(q))
