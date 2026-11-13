"""Projects, tasks, items and templates (FR-005, FR-006, FR-016, FR-017, FR-029, FR-030)."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.db import get_db
from app.core.errors import forbidden
from app.core.security import current_user, require
from app.models import Item, Project, ProjectMember, ProjectTemplate, Task, TemplateTask, User
from app.services import access, rules

router = APIRouter(prefix="/setup", tags=["setup"])
Kind = Literal["projects", "tasks", "items"]


@router.get("/projects", response_model=list[schemas.ProjectOut], response_model_by_alias=True)
def projects(db: Session = Depends(get_db), me: User = Depends(current_user)):
    ids = access.visible_project_ids(db, me)
    return [convert.project(p) for p in db.scalars(select(Project).where(Project.project_id.in_(ids)).order_by(Project.project_name))]


@router.get("/tasks", response_model=list[schemas.TaskOut], response_model_by_alias=True)
def tasks(db: Session = Depends(get_db), me: User = Depends(current_user)):
    ids = access.visible_project_ids(db, me)
    return [convert.task(t) for t in db.scalars(select(Task).where(Task.project_id.in_(ids)).order_by(Task.task_id))]


@router.get("/items", response_model=list[schemas.ItemOut], response_model_by_alias=True)
def items(db: Session = Depends(get_db), me: User = Depends(current_user)):
    ids = access.visible_project_ids(db, me)
    q = select(Item).join(Task, Task.task_id == Item.task_id).where(Task.project_id.in_(ids)).order_by(Item.item_id)
    return [convert.item(i) for i in db.scalars(q)]


@router.post("/projects", response_model=schemas.ProjectOut, response_model_by_alias=True, status_code=201)
def create_project(body: schemas.ProjectIn, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    if db.scalar(select(Project).where(func.lower(Project.project_name) == body.name.lower())):
        raise rules.RuleError("A project with this name exists")
    p = Project(project_name=body.name, description=body.description, visibility=body.visibility, owner_id=me.user_id, created_by=me.user_id)
    db.add(p)
    db.flush()
    for t in body.tasks:
        task = Task(project_id=p.project_id, task_name=t.name, from_template=True)
        db.add(task)
        db.flush()
        for name in t.items:
            db.add(Item(task_id=task.task_id, item_name=name, from_template=True))
    db.add(ProjectMember(project_id=p.project_id, user_id=me.user_id, role_on_project="Team lead", added_by=me.user_id))
    audit(db, me.user_id, "create_project", "projects", p.project_id, new={"name": p.project_name, "visibility": p.visibility})
    return convert.project(p)


def _option(db: Session, kind: Kind, id_: int):
    model = {"projects": Project, "tasks": Task, "items": Item}[kind]
    return access.get_or_404(db, model, id_)


def _name_attr(kind: Kind) -> str:
    return {"projects": "project_name", "tasks": "task_name", "items": "item_name"}[kind]


@router.put("/{kind}/{id_}", status_code=204)
def rename(kind: Kind, id_: int, body: schemas.RenameIn, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    row = _option(db, kind, id_)
    attr = _name_attr(kind)
    audit(db, me.user_id, "rename", kind, id_, old={"name": getattr(row, attr)}, new={"name": body.name})
    setattr(row, attr, body.name)  # the new name shows everywhere, including past entries


@router.post("/{kind}/{id_}/archive", status_code=204)
def archive(kind: Kind, id_: int, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    row = _option(db, kind, id_)
    row.active_flag = False  # never deleted, so historic entries keep their names (FR-017)
    audit(db, me.user_id, "archive", kind, id_)


# ---------- templates (FR-016, FR-030)

def _template_out(db: Session, t: ProjectTemplate) -> schemas.TemplateOut:
    rows = list(db.scalars(select(TemplateTask).where(TemplateTask.template_id == t.template_id).order_by(TemplateTask.sort_order)))
    tasks_ = [schemas.TaskDraft(name=r.name, items=[c.name for c in rows if c.parent_id == r.template_task_id]) for r in rows if r.parent_id is None]
    return schemas.TemplateOut(id=t.template_id, name=t.template_name, category=t.category or "", sharing=t.sharing, approval=t.approval_status, owner_id=t.owner_id, tasks=tasks_)


def _can_see_template(db: Session, me: User, t: ProjectTemplate) -> bool:
    if t.owner_id is None or t.owner_id == me.user_id or me.role == "manager":
        return True
    if t.sharing == "everyone":
        return t.approval_status == "approved"
    if t.sharing == "my_team":
        my_lead = me.user_id if me.role == "team_lead" else me.team_lead_id
        owner = db.get(User, t.owner_id)
        owner_lead = owner.user_id if owner and owner.role == "team_lead" else (owner.team_lead_id if owner else None)
        return my_lead is not None and my_lead == owner_lead
    return False


@router.get("/templates", response_model=list[schemas.TemplateOut], response_model_by_alias=True)
def templates(db: Session = Depends(get_db), me: User = Depends(current_user)):
    rows = db.scalars(select(ProjectTemplate).where(ProjectTemplate.active_flag.is_(True)).order_by(ProjectTemplate.template_name))
    return [_template_out(db, t) for t in rows if _can_see_template(db, me, t)]


@router.post("/templates", response_model=schemas.TemplateOut, response_model_by_alias=True, status_code=201)
def save_template(body: schemas.TemplateIn, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    needs_approval = body.sharing == "everyone" and me.role != "manager"
    t = ProjectTemplate(
        template_name=body.name, category=body.category, owner_id=me.user_id, sharing=body.sharing,
        approval_status="pending" if needs_approval else ("approved" if body.sharing == "everyone" else "not_needed"),
        approved_by=None if needs_approval or body.sharing != "everyone" else me.user_id,
        approved_date=None if needs_approval or body.sharing != "everyone" else datetime.now(timezone.utc),
        updated_by=me.user_id,
    )
    db.add(t)
    db.flush()
    for order, task in enumerate(body.tasks):
        parent = TemplateTask(template_id=t.template_id, name=task.name, sort_order=order)
        db.add(parent)
        db.flush()
        for k, item in enumerate(task.items):
            db.add(TemplateTask(template_id=t.template_id, parent_id=parent.template_task_id, name=item, sort_order=k))
    audit(db, me.user_id, "save_template", "project_templates", t.template_id, new={"sharing": t.sharing, "approval": t.approval_status})
    db.flush()
    return _template_out(db, t)


@router.post("/templates/{template_id}/approve", status_code=204)
def approve_template(template_id: int, db: Session = Depends(get_db), me: User = Depends(require("manager"))):
    t = access.get_or_404(db, ProjectTemplate, template_id)
    if t.approval_status != "pending":
        raise rules.RuleError(f"This template is {t.approval_status}")
    if t.owner_id == me.user_id:
        raise forbidden("You cannot approve your own template")
    t.approval_status, t.approved_by, t.approved_date = "approved", me.user_id, datetime.now(timezone.utc)
    audit(db, me.user_id, "approve_template", "project_templates", template_id)
