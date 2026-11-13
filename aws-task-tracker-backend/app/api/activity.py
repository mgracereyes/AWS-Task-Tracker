"""Time entries: list, add, edit, delete, breaks, Admin corrections (FR-018, FR-019, FR-020, FR-025, FR-027)."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.db import get_db
from app.core.errors import not_found
from app.core.security import current_user, require
from app.models import DailyTaskLog, Item, Project, Task, User
from app.services import access, rules

router = APIRouter(prefix="/activity", tags=["activity"])


def query_entries(
    db: Session, me: User, start: date, end: date,
    project_id: int | None = None, task_id: int | None = None, item_id: int | None = None, user_id: int | None = None,
) -> list[schemas.EntryRow]:
    """Entries the signed-in user may see, joined with project / task / item names."""
    rules.check_range(start, end, max_days=366)
    ids = access.visible_user_ids(db, me)
    if user_id is not None:
        if user_id not in ids:
            raise not_found()
        ids = {user_id}
    q = (
        select(DailyTaskLog, Item, Task, Project)
        .outerjoin(Item, Item.item_id == DailyTaskLog.item_id)
        .outerjoin(Task, Task.task_id == Item.task_id)
        .outerjoin(Project, Project.project_id == Task.project_id)
        .where(DailyTaskLog.user_id.in_(ids), DailyTaskLog.log_date >= start, DailyTaskLog.log_date <= end)
        .order_by(DailyTaskLog.log_date, DailyTaskLog.start_time)
    )
    filtered = project_id or task_id or item_id
    if project_id:
        q = q.where(Project.project_id == project_id)
    if task_id:
        q = q.where(Task.task_id == task_id)
    if item_id:
        q = q.where(Item.item_id == item_id)
    out = []
    for e, it, t, p in db.execute(q).all():
        if e.entry_type == "break" and filtered:
            continue
        out.append(schemas.EntryRow(
            id=e.log_id, user_id=e.user_id, item_id=e.item_id, date=e.log_date, type=e.entry_type,
            start=convert.hhmm(e.start_time), end=convert.hhmm(e.end_time), minutes=e.effort_minutes or 0, remarks=e.remarks or "",
            project_id=p.project_id if p else 0, project=p.project_name if p else "", task=t.task_name if t else "",
            item=it.item_name if it else "Break", work_type=it.work_type if it else "task",
        ))
    return out


@router.get("", response_model=list[schemas.EntryRow], response_model_by_alias=True)
def list_entries(
    start: date = Query(alias="from"), end: date = Query(alias="to"),
    project_id: int | None = Query(None, alias="projectId"), task_id: int | None = Query(None, alias="taskId"),
    item_id: int | None = Query(None, alias="itemId"), user_id: int | None = Query(None, alias="userId"),
    db: Session = Depends(get_db), me: User = Depends(current_user),
):
    return query_entries(db, me, start, end, project_id, task_id, item_id, user_id)


@router.post("", status_code=201)
def add_entry(body: schemas.EntryIn, db: Session = Depends(get_db), me: User = Depends(current_user)):
    item, _task, project = access.check_can_log(db, me, body.item_id)
    access.check_writable(db, me, body.date)
    minutes = rules.effort_minutes(body.start, body.end)
    rules.check_day_total(access.day_minutes(db, me.user_id, body.date), minutes)
    e = DailyTaskLog(
        user_id=me.user_id, item_id=item.item_id, log_date=body.date, entry_type="work", start_time=body.start, end_time=body.end,
        effort_minutes=minutes, remarks=body.remarks, start_date=body.date, end_date=body.date,
    )
    db.add(e)
    db.flush()
    audit(db, me.user_id, "add_entry", "daily_task_logs", e.log_id, new={"project": project.project_name, "start": str(body.start), "end": str(body.end)})
    return {"id": e.log_id}


def _own_entry(db: Session, me: User, log_id: int) -> DailyTaskLog:
    e = db.get(DailyTaskLog, log_id)
    if e is None or e.user_id != me.user_id:
        raise not_found()  # never reveal other people's entries
    return e


@router.put("/{log_id}", status_code=204)
def edit_entry(log_id: int, body: schemas.EntryEdit, db: Session = Depends(get_db), me: User = Depends(current_user)):
    e = _own_entry(db, me, log_id)
    access.check_writable(db, me, e.log_date, body.reason)
    minutes = rules.effort_minutes(body.start, body.end)
    rules.check_day_total(access.day_minutes(db, me.user_id, e.log_date, except_id=log_id), minutes)
    old = {"start": convert.hhmm(e.start_time), "end": convert.hhmm(e.end_time), "remarks": e.remarks}
    e.start_time, e.end_time, e.effort_minutes, e.remarks = body.start, body.end, minutes, body.remarks
    e.updated_by, e.updated_date = me.user_id, datetime.now(timezone.utc)
    audit(db, me.user_id, "edit_entry", "daily_task_logs", log_id, reason=body.reason, old=old,
          new={"start": convert.hhmm(body.start), "end": convert.hhmm(body.end), "remarks": body.remarks})


@router.delete("/{log_id}", status_code=204)
def delete_entry(log_id: int, body: schemas.ReasonIn | None = Body(default=None), db: Session = Depends(get_db), me: User = Depends(current_user)):
    e = _own_entry(db, me, log_id)
    reason = body.reason if body else None
    access.check_writable(db, me, e.log_date, reason)
    audit(db, me.user_id, "delete_entry", "daily_task_logs", log_id, reason=reason,
          old={"date": str(e.log_date), "start": convert.hhmm(e.start_time), "end": convert.hhmm(e.end_time), "item": e.item_id})
    db.delete(e)


@router.post("/breaks", status_code=201)
def add_break(body: schemas.BreakIn, db: Session = Depends(get_db), me: User = Depends(current_user)):
    access.check_writable(db, me, body.date)
    e = DailyTaskLog(
        user_id=me.user_id, item_id=None, log_date=body.date, entry_type="break", start_time=body.start, end_time=body.end,
        effort_minutes=rules.effort_minutes(body.start, body.end), start_date=body.date, end_date=body.date,
    )
    db.add(e)
    db.flush()
    return {"id": e.log_id}


@router.post("/{log_id}/correct", status_code=204)
def correct_entry(log_id: int, body: schemas.CorrectIn, db: Session = Depends(get_db), me: User = Depends(require("admin"))):
    """Admin correction of another person's entry; reason required (FR-019)."""
    e = access.get_or_404(db, DailyTaskLog, log_id)
    minutes = rules.effort_minutes(body.start, body.end)
    rules.check_day_total(access.day_minutes(db, e.user_id, e.log_date, except_id=log_id), minutes)
    old = {"start": convert.hhmm(e.start_time), "end": convert.hhmm(e.end_time)}
    e.start_time, e.end_time, e.effort_minutes = body.start, body.end, minutes
    e.updated_by, e.updated_date = me.user_id, datetime.now(timezone.utc)
    audit(db, me.user_id, "correct_entry", "daily_task_logs", log_id, reason=body.reason, old=old,
          new={"start": convert.hhmm(body.start), "end": convert.hhmm(body.end)})
