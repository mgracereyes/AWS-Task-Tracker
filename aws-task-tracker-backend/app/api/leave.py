"""Leave: VL and SL, whole or half day (FR-024)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.db import get_db
from app.core.errors import not_found
from app.core.security import current_user
from app.models import LeaveRequest, User
from app.services import access, rules

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("", response_model=list[schemas.LeaveOut], response_model_by_alias=True)
def list_leave(user_id: int | None = Query(None, alias="userId"), db: Session = Depends(get_db), me: User = Depends(current_user)):
    ids = access.visible_user_ids(db, me)
    if user_id is not None:
        if user_id not in ids:
            raise not_found()
        ids = {user_id}
    q = select(LeaveRequest).where(LeaveRequest.user_id.in_(ids)).order_by(LeaveRequest.start_date.desc())
    return [convert.leave(l) for l in db.scalars(q)]


@router.post("", status_code=201)
def file_leave(body: schemas.LeaveIn, db: Session = Depends(get_db), me: User = Depends(current_user)):
    hours = rules.leave_hours(body.start_date, body.end_date, body.day_part)
    for d in rules.workdays(body.start_date, body.end_date):
        access.check_writable_leave(db, me, d)
    row = LeaveRequest(user_id=me.user_id, leave_type=body.type, start_date=body.start_date, end_date=body.end_date, day_part=body.day_part, hours_credited=hours)
    db.add(row)
    db.flush()
    audit(db, me.user_id, "file_leave", "leave_requests", row.leave_id, new={"type": body.type, "hours": hours})
    return {"id": row.leave_id}


@router.post("/{leave_id}/cancel", status_code=204)
def cancel_leave(leave_id: int, db: Session = Depends(get_db), me: User = Depends(current_user)):
    row = db.get(LeaveRequest, leave_id)
    if row is None or row.user_id != me.user_id:
        raise not_found()
    if row.status == "cancelled":
        return
    for d in rules.workdays(row.start_date, row.end_date):
        access.check_writable_leave(db, me, d)  # leave on a locked day needs an unlock first
    row.status = "cancelled"
    audit(db, me.user_id, "cancel_leave", "leave_requests", leave_id)
