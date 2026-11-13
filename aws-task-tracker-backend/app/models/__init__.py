"""ORM models. Table and column names match database/schema.sql (v1.3) + migrations."""
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_account: Mapped[str] = mapped_column(String(255))
    user_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20), default="employee")
    team_lead_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    business_unit: Mapped[str] = mapped_column(String(20), default="Dev C")  # migration 001
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectTemplate(Base):
    __tablename__ = "project_templates"
    template_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    sharing: Mapped[str] = mapped_column(String(10), default="only_me")
    approval_status: Mapped[str] = mapped_column(String(10), default="not_needed")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    approved_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"))
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    updated_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateTask(Base):
    __tablename__ = "template_tasks"
    template_task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("project_templates.template_id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("template_tasks.template_task_id"))  # NULL = task
    name: Mapped[str] = mapped_column(String(150))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Project(Base):
    __tablename__ = "projects"
    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("project_templates.template_id"))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    visibility: Mapped[str] = mapped_column(String(10), default="public")
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    role_on_project: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)


class Task(Base):
    __tablename__ = "tasks"
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"))
    task_name: Mapped[str] = mapped_column(String(150))
    planned_minutes: Mapped[int] = mapped_column(Integer, default=0)
    from_template: Mapped[bool] = mapped_column(Boolean, default=False)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Item(Base):
    __tablename__ = "items"
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.task_id"))
    item_name: Mapped[str] = mapped_column(String(150))
    work_type: Mapped[str] = mapped_column(String(10), default="task")
    planned_minutes: Mapped[int] = mapped_column(Integer, default=0)
    from_template: Mapped[bool] = mapped_column(Boolean, default=False)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyTaskLog(Base):
    __tablename__ = "daily_task_logs"
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.item_id"))  # NULL = break
    log_date: Mapped[date] = mapped_column(Date)
    entry_type: Mapped[str] = mapped_column(String(5), default="work")
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    effort_minutes: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    updated_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    leave_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    leave_type: Mapped[str] = mapped_column(String(2))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    day_part: Mapped[str] = mapped_column(String(5), default="whole")
    hours_credited: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(10), default="filed")
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimesheetLock(Base):
    __tablename__ = "timesheet_locks"
    lock_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    locked_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    lock_reason: Mapped[str | None] = mapped_column(Text)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UnlockRequest(Base):
    __tablename__ = "unlock_requests"
    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    lock_id: Mapped[int] = mapped_column(ForeignKey("timesheet_locks.lock_id"))
    request_date: Mapped[date] = mapped_column(Date)
    action_type: Mapped[str] = mapped_column(String(6))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    decided_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LockOverride(Base):
    __tablename__ = "lock_overrides"
    override_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("unlock_requests.request_id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    unlocked_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    revoked_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"
    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    type: Mapped[str] = mapped_column(String(20))
    link: Mapped[str | None] = mapped_column(String(255))
    related_date: Mapped[date | None] = mapped_column(Date)
    message: Mapped[str] = mapped_column(Text)
    read_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportFile(Base):
    __tablename__ = "export_files"
    export_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    format: Mapped[str] = mapped_column(String(4))
    source: Mapped[str] = mapped_column(String(20), default="report")
    filters: Mapped[dict | None] = mapped_column(JSONB)
    file_path: Mapped[str | None] = mapped_column(String(500))
    row_count: Mapped[int | None] = mapped_column(Integer)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    action: Mapped[str] = mapped_column(String(50))
    target_table: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    old_value: Mapped[dict | None] = mapped_column(JSONB)
    new_value: Mapped[dict | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[dict | None] = mapped_column(JSONB)
