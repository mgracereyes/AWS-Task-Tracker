"""People, roles, business units, project access and the audit log (FR-004, FR-014, FR-015, FR-032)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.api import convert
from app.core.audit import audit
from app.core.db import get_db
from app.core.errors import forbidden, not_found
from app.core.security import current_user, require
from app.models import AuditLog, Project, ProjectMember, User
from app.services import access, rules

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[schemas.UserOut], response_model_by_alias=True)
def list_users(db: Session = Depends(get_db), me: User = Depends(current_user)):
    ids = access.visible_user_ids(db, me)
    users = list(db.scalars(select(User).where(User.user_id.in_(ids)).order_by(User.user_name)))
    last = convert.last_sign_in(db, [u.user_id for u in users])
    return [convert.user(u, last.get(u.user_id, "—")) for u in users]


@router.put("/users/{user_id}", status_code=204)
def update_user(user_id: int, body: schemas.UserPatch, db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS))):
    target = access.get_or_404(db, User, user_id)
    if body.role is not None and body.role != target.role:
        rules.check_role_change(me.role, me.user_id, target.user_id, target.role, body.role)
        audit(db, me.user_id, "role_change", "users", user_id, old={"role": target.role}, new={"role": body.role})
        target.role = body.role
    if body.active is not None and body.active != target.active_flag:
        if me.role != "admin":
            raise forbidden("Only admins can deactivate or activate accounts")
        if target.user_id == me.user_id:
            raise rules.RuleError("You cannot change your own role or access")
        audit(db, me.user_id, "reactivate" if body.active else "deactivate", "users", user_id)
        target.active_flag = body.active  # history is kept; the next request of that user fails (FR-015)
    if body.business_unit is not None and body.business_unit != target.business_unit:
        audit(db, me.user_id, "business_unit", "users", user_id, old={"bu": target.business_unit}, new={"bu": body.business_unit})
        target.business_unit = body.business_unit
    if body.team_lead_id is not None and body.team_lead_id != target.team_lead_id:
        lead = db.get(User, body.team_lead_id)
        if lead is None or lead.role != "team_lead":
            raise rules.RuleError("Team lead must be a user with the Team lead role")
        audit(db, me.user_id, "set_team_lead", "users", user_id, old={"lead": target.team_lead_id}, new={"lead": body.team_lead_id})
        target.team_lead_id = body.team_lead_id


@router.put("/users/{user_id}/projects", status_code=204)
def set_projects(user_id: int, body: schemas.ProjectIdsIn, db: Session = Depends(get_db), me: User = Depends(require(*rules.MANAGERS))):
    if db.get(User, user_id) is None:
        raise not_found()
    wanted = set(body.project_ids)
    if wanted - set(db.scalars(select(Project.project_id))):
        raise rules.RuleError("Unknown project")
    current = {m.project_id: m for m in db.scalars(select(ProjectMember).where(ProjectMember.user_id == user_id))}
    for pid, m in current.items():
        if pid not in wanted:
            db.delete(m)  # past time entries are kept; they reference items, not memberships
    for pid in wanted - current.keys():
        db.add(ProjectMember(project_id=pid, user_id=user_id, role_on_project="Member", added_by=me.user_id))
    audit(db, me.user_id, "set_projects", "users", user_id, old={"projects": sorted(current)}, new={"projects": sorted(wanted)})


@router.get("/audit", response_model=list[schemas.AuditOut], response_model_by_alias=True)
def audit_log(limit: int = 500, db: Session = Depends(get_db), me: User = Depends(require("admin"))):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(min(limit, 5000)))
    return [convert.audit_row(a) for a in rows]
