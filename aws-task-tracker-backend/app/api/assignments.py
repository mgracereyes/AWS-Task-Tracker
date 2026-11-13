"""Project membership and assignments (FR-007, FR-031, FR-033)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.db import get_db
from app.core.errors import forbidden
from app.core.security import current_user, require
from app.models import Project, ProjectMember, User
from app.services import access, rules

router = APIRouter(prefix="/assignments", tags=["assignments"])


def _check_can_manage(db: Session, me: User, user_id: int) -> None:
    """Team leads manage their own team only; Manager and Admin manage everyone."""
    if me.role == "team_lead" and user_id not in access.team_ids(db, me.user_id):
        raise forbidden("You can only assign your own team")


@router.get("", response_model=list[schemas.MemberOut], response_model_by_alias=True)
def list_members(db: Session = Depends(get_db), me: User = Depends(current_user)):
    ids = access.visible_user_ids(db, me)
    return [convert.member(m) for m in db.scalars(select(ProjectMember).where(ProjectMember.user_id.in_(ids)).order_by(ProjectMember.end_date))]


@router.post("", status_code=201)
def assign(body: schemas.MemberIn, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    _check_can_manage(db, me, body.user_id)
    person = access.get_or_404(db, User, body.user_id)
    if not person.active_flag:
        raise rules.RuleError("This person is deactivated")
    project = access.get_or_404(db, Project, body.project_id)
    if not project.active_flag:
        raise rules.RuleError("This project is archived")
    if db.scalar(select(ProjectMember).where(ProjectMember.user_id == body.user_id, ProjectMember.project_id == body.project_id)):
        raise rules.RuleError("This person is already on the project")
    m = ProjectMember(project_id=body.project_id, user_id=body.user_id, role_on_project=body.role_on_project, start_date=body.start_date, end_date=body.end_date, added_by=me.user_id)
    db.add(m)
    db.flush()
    audit(db, me.user_id, "assign", "project_members", m.project_member_id, new={"user": body.user_id, "project": body.project_id, "role": body.role_on_project})
    return {"id": m.project_member_id}


@router.put("/{member_id}", status_code=204)
def update(member_id: int, body: schemas.MemberPatch, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    m = access.get_or_404(db, ProjectMember, member_id)
    _check_can_manage(db, me, m.user_id)
    old = {"role": m.role_on_project, "start": str(m.start_date), "end": str(m.end_date)}
    start = body.start_date or m.start_date
    end = body.end_date or m.end_date
    if start and end and end < start:
        raise rules.RuleError("End date must be on or after the start date")
    m.start_date, m.end_date = start, end
    if body.role_on_project is not None:
        m.role_on_project = body.role_on_project
    audit(db, me.user_id, "change_assignment", "project_members", member_id, old=old, new={"role": m.role_on_project, "start": str(start), "end": str(end)})


@router.delete("/{member_id}", status_code=204)
def remove(member_id: int, db: Session = Depends(get_db), me: User = Depends(require(*rules.LEADS_AND_UP))):
    m = access.get_or_404(db, ProjectMember, member_id)
    _check_can_manage(db, me, m.user_id)
    audit(db, me.user_id, "remove_member", "project_members", member_id, old={"user": m.user_id, "project": m.project_id})
    db.delete(m)  # past entries stay; the person can no longer log new time on the project
