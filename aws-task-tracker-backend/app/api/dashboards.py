"""Dashboard totals (FR-008 to FR-010, FR-034, FR-035).

The frontend can build every dashboard from GET /api/activity; these endpoints return the
same totals already grouped, for large periods.
"""
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.activity import query_entries
from app.core.db import get_db
from app.core.security import current_user, require
from app.models import Item, Task, User
from app.services import rules

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.get("/me")
def my_summary(start: date = Query(alias="from"), end: date = Query(alias="to"), db: Session = Depends(get_db), me: User = Depends(current_user)):
    rules.check_range(start, end)
    rows = [e for e in query_entries(db, me, start, end, user_id=me.user_id) if e.type == "work"]
    today = date.today()
    expected = len(rules.workdays(start, min(end, today))) * rules.EXPECTED_MINUTES_PER_DAY if start <= today else 0
    by_day: dict[str, int] = defaultdict(int)
    for e in rows:
        by_day[e.date.isoformat()] += e.minutes
    return {"loggedMinutes": sum(by_day.values()), "expectedMinutes": expected, "byDay": by_day}


@router.get("/organization")
def organization(
    start: date = Query(alias="from"), end: date = Query(alias="to"),
    project_id: int | None = Query(None, alias="projectId"), task_id: int | None = Query(None, alias="taskId"),
    item_id: int | None = Query(None, alias="itemId"), user_id: int | None = Query(None, alias="userId"),
    db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS)),
):
    """By project, by team, by day and by item, with planned minutes for progress bars."""
    rules.check_range(start, end)
    rows = [e for e in query_entries(db, me, start, end, project_id, task_id, item_id, user_id) if e.type == "work"]
    leads = {u.user_id: (u.team_lead_id, u.role) for u in db.scalars(select(User))}
    planned_item = {i.item_id: i.planned_minutes for i in db.scalars(select(Item))}
    project_of_task = {t.task_id: t.project_id for t in db.scalars(select(Task))}
    planned_project: dict[int, int] = defaultdict(int)
    for i in db.scalars(select(Item)):
        planned_project[project_of_task[i.task_id]] += i.planned_minutes

    by_project: dict[int, int] = defaultdict(int)
    by_team: dict[int, int] = defaultdict(int)
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_item: dict[int, int] = defaultdict(int)
    by_member: dict[int, int] = defaultdict(int)
    for e in rows:
        by_project[e.project_id] += e.minutes
        lead, role = leads.get(e.user_id, (None, None))
        by_team[e.user_id if role == "team_lead" else (lead or 0)] += e.minutes
        by_day[e.date.isoformat()][f"{e.project_id}:{e.work_type}"] += e.minutes
        by_item[e.item_id or 0] += e.minutes
        by_member[e.user_id] += e.minutes
    return {
        "totalMinutes": sum(by_project.values()),
        "byProject": [{"projectId": p, "minutes": m, "plannedMinutes": planned_project.get(p, 0)} for p, m in by_project.items()],
        "byTeam": [{"leadId": t, "minutes": m} for t, m in by_team.items()],
        "byDay": by_day,
        "byItem": [{"itemId": i, "minutes": m, "plannedMinutes": planned_item.get(i, 0)} for i, m in by_item.items()],
        "byMember": [{"userId": u, "minutes": m} for u, m in by_member.items()],
    }
