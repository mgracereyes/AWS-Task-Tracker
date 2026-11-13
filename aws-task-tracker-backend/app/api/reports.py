"""Reports and XLSX / CSV export (FR-012, FR-013, FR-035). Export is Manager and Admin only."""
import csv
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.api.activity import query_entries
from app.core.audit import audit
from app.core.db import get_db
from app.core.security import require
from app.models import ExportFile, User
from app.services import rules

router = APIRouter(prefix="/reports", tags=["reports"])
HEADERS = ["Date", "Employee", "Project", "Task", "Item", "Description", "Hours"]


def _rows(db: Session, me: User, start: date, end: date, project_id, task_id, item_id, user_id) -> list[list]:
    names = dict(db.execute(select(User.user_id, User.user_name)).all())
    entries = [e for e in query_entries(db, me, start, end, project_id, task_id, item_id, user_id) if e.type == "work"]
    return [[e.date.isoformat(), names.get(e.user_id, ""), e.project, e.task, e.item, e.remarks, round(e.minutes / 60, 2)] for e in entries]


@router.get("", response_model=list[schemas.EntryRow], response_model_by_alias=True)
def report(
    start: date = Query(alias="from"), end: date = Query(alias="to"),
    project_id: int | None = Query(None, alias="projectId"), task_id: int | None = Query(None, alias="taskId"),
    item_id: int | None = Query(None, alias="itemId"), user_id: int | None = Query(None, alias="userId"),
    db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP)),
):
    """Team leads get their team only (access rules in query_entries); employees have no Reports."""
    return [e for e in query_entries(db, me, start, end, project_id, task_id, item_id, user_id) if e.type == "work"]


@router.get("/export")
def export(
    fmt: Literal["csv", "xlsx"] = Query("xlsx", alias="format"),
    source: Literal["report", "dashboard", "filter_results"] = "report",
    start: date = Query(alias="from"), end: date = Query(alias="to"),
    project_id: int | None = Query(None, alias="projectId"), task_id: int | None = Query(None, alias="taskId"),
    item_id: int | None = Query(None, alias="itemId"), user_id: int | None = Query(None, alias="userId"),
    db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS)),
):
    rows = _rows(db, me, start, end, project_id, task_id, item_id, user_id)
    filename = f"task_tracker_{source}_{start}_{end}.{fmt}"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(HEADERS)
        w.writerows(rows)
        body, media = ("﻿" + buf.getvalue()).encode("utf-8"), "text/csv; charset=utf-8"
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        ws.append(HEADERS)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append(r)
        for col, width in zip("ABCDEFG", (12, 22, 18, 16, 18, 40, 8)):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"
        buf2 = io.BytesIO()
        wb.save(buf2)
        body, media = buf2.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filters = {"from": str(start), "to": str(end), "projectId": project_id, "taskId": task_id, "itemId": item_id, "userId": user_id}
    db.add(ExportFile(user_id=me.user_id, format=fmt.upper(), source=source, filters=filters, file_path=filename, row_count=len(rows)))
    audit(db, me.user_id, "export", "export_files", None, format=fmt.upper(), rows=len(rows), source=source)
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
