"""Audit log writer (FR-014). Rows are append-only; the database blocks UPDATE and DELETE."""
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(
    db: Session,
    actor_id: int | None,
    action: str,
    target_table: str | None = None,
    target_id: int | None = None,
    reason: str | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    **details: Any,
) -> None:
    db.add(AuditLog(
        actor_id=actor_id, action=action, target_table=target_table, target_id=target_id,
        reason=reason or None, old_value=old, new_value=new, details=details or None,
    ))
