"""Request and response formats. JSON uses camelCase to match the frontend (src/api/types.ts)."""
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

Role = Literal["employee", "team_lead", "manager", "admin"]


class Out(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class In(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, str_strip_whitespace=True, extra="forbid")


# ---------- users

class UserOut(Out):
    id: int
    name: str
    email: str
    role: Role
    team_lead_id: int | None
    business_unit: str
    active: bool
    last_sign_in: str


class LoginIn(In):
    email: str = Field(max_length=255)


class GoogleLoginIn(In):
    credential: str


class UserPatch(In):
    role: Role | None = None
    active: bool | None = None
    business_unit: str | None = Field(default=None, max_length=20)
    team_lead_id: int | None = None


class ProjectIdsIn(In):
    project_ids: list[int]


# ---------- setup

class ProjectOut(Out):
    id: int
    name: str
    description: str
    visibility: Literal["public", "private"]
    active: bool
    lead_id: int | None


class TaskOut(Out):
    id: int
    project_id: int
    name: str
    active: bool


class ItemOut(Out):
    id: int
    task_id: int
    name: str
    work_type: Literal["task", "meeting"]
    planned_minutes: int
    active: bool


class TaskDraft(In):
    name: str = Field(min_length=1, max_length=150)
    items: list[str] = []


class ProjectIn(In):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    visibility: Literal["public", "private"] = "public"
    tasks: list[TaskDraft] = []


class RenameIn(In):
    name: str = Field(min_length=1, max_length=150)


class TemplateOut(Out):
    id: int
    name: str
    category: str
    sharing: Literal["only_me", "my_team", "everyone"]
    approval: Literal["not_needed", "pending", "approved", "rejected"]
    owner_id: int | None
    tasks: list[TaskDraft]


class TemplateIn(In):
    name: str = Field(min_length=1, max_length=150)
    category: str = ""
    sharing: Literal["only_me", "my_team", "everyone"] = "only_me"
    tasks: list[TaskDraft] = []


# ---------- assignments

class MemberOut(Out):
    id: int
    project_id: int
    user_id: int
    role_on_project: str
    start_date: date | None
    end_date: date | None


class MemberIn(In):
    project_id: int
    user_id: int
    role_on_project: str = Field(max_length=50)
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info):
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("End date must be on or after the start date")
        return v


class MemberPatch(In):
    role_on_project: str | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None


# ---------- activity

class EntryRow(Out):
    id: int
    user_id: int
    item_id: int | None
    date: date
    type: Literal["work", "break"]
    start: str
    end: str | None
    minutes: int
    remarks: str
    project_id: int
    project: str
    task: str
    item: str
    work_type: Literal["task", "meeting"]


class EntryIn(In):
    item_id: int
    date: date
    start: time
    end: time
    remarks: str = Field(default="", max_length=500)


class EntryEdit(In):
    start: time
    end: time
    remarks: str = Field(default="", max_length=500)
    reason: str | None = Field(default=None, max_length=500)


class BreakIn(In):
    date: date
    start: time
    end: time


class CorrectIn(In):
    start: time
    end: time
    reason: str = Field(min_length=1, max_length=500)


class ReasonIn(In):
    reason: str | None = Field(default=None, max_length=500)


# ---------- leave

class LeaveOut(Out):
    id: int
    user_id: int
    type: Literal["VL", "SL"]
    start_date: date
    end_date: date
    day_part: Literal["whole", "half"]
    hours: float
    status: Literal["filed", "cancelled"]


class LeaveIn(In):
    type: Literal["VL", "SL"]
    start_date: date
    end_date: date
    day_part: Literal["whole", "half"] = "whole"


# ---------- locks

class LockOut(Out):
    id: int
    start_date: date
    end_date: date
    locked_by: int
    reason: str


class LockIn(In):
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=500)


class UnlockOut(Out):
    id: int
    user_id: int
    date: date
    action: Literal["add", "edit", "delete"]
    reason: str
    details: str
    status: Literal["pending", "allowed", "declined", "expired"]
    created_at: str
    expires_at: str


class UnlockIn(In):
    date: date
    action: Literal["add", "edit", "delete"]
    reason: str = Field(min_length=1, max_length=1000)
    details: str = Field(default="", max_length=1000)


# ---------- notifications and audit

class NotificationOut(Out):
    id: int
    user_id: int
    type: Literal["under_8h", "locked_day", "unlock_decision", "lock_verification", "template_approval"]
    date: date
    message: str
    link: str
    read: bool


class AuditOut(Out):
    id: int
    actor_id: int | None
    action: str
    target: str
    reason: str
    at: str
