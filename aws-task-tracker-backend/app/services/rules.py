"""Business rules with no database or web code, so they are easy to test.

FR-018 effort, FR-020 8-hour check, FR-021 date ranges, FR-024 leave hours,
FR-026 72-hour unlock window, FR-028 roles.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

EXPECTED_MINUTES_PER_DAY = 480
UNLOCK_HOURS = 72
MAX_RANGE_DAYS = 92
MAX_MINUTES_PER_DAY = 1440

ROLES = ("employee", "team_lead", "manager", "admin")
MANAGERS = ("manager", "admin")
LEADS_AND_UP = ("team_lead", "manager", "admin")


class RuleError(ValueError):
    """A business rule was broken. `status` is the HTTP code the API returns."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------- time and effort (FR-018)

def effort_minutes(start: time, end: time) -> int:
    """Minutes between two times on the same day. End must be after start."""
    minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    if minutes <= 0:
        raise RuleError("End time must be after start time")
    return minutes


def check_entry_date(day: date, today: date) -> None:
    if day > today:
        raise RuleError("Cannot log future dates")


def check_day_total(existing_minutes: int, new_minutes: int) -> None:
    if existing_minutes + new_minutes > MAX_MINUTES_PER_DAY:
        raise RuleError("A day cannot exceed 24 hours")


# ---------- dates (FR-021)

def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def workdays(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if not is_weekend(d):
            days.append(d)
        d += timedelta(days=1)
    return days


def check_range(start: date, end: date, max_days: int = MAX_RANGE_DAYS) -> None:
    if end < start:
        raise RuleError("End date must be on or after the start date")
    if (end - start).days + 1 > max_days:
        raise RuleError(f"Pick {max_days} days or fewer")


# ---------- 8-hour reminder (FR-020)

def minutes_short(logged_minutes: int, leave_minutes: int, day: date) -> int:
    """How many minutes a weekday is short of 8 hours. Leave counts toward the 8 hours."""
    if is_weekend(day):
        return 0
    return max(0, EXPECTED_MINUTES_PER_DAY - logged_minutes - leave_minutes)


# ---------- leave (FR-024)

def leave_hours(start: date, end: date, day_part: str) -> float:
    if end < start:
        raise RuleError("End date must be on or after the start date")
    if day_part == "half":
        if start != end:
            raise RuleError("A half day covers one date only")
        if is_weekend(start):
            raise RuleError("Leave must include at least one weekday")
        return 4.0
    days = len(workdays(start, end))
    if days == 0:
        raise RuleError("Leave must include at least one weekday")
    return days * 8.0


def leave_minutes_on(day: date, leaves: list[tuple[date, date, str]]) -> int:
    """Leave minutes that fall on `day`. Each leave is (start, end, day_part)."""
    if is_weekend(day):
        return 0
    return sum(240 if part == "half" else 480 for s, e, part in leaves if s <= day <= e)


# ---------- locks and unlocks (FR-025 to FR-027)

@dataclass(frozen=True)
class LockState:
    locked: bool
    open_for_user: bool  # an allowed unlock is still within its 72 hours


def lock_state(day: date, lock_ranges: list[tuple[date, date]], overrides: list[tuple[date, datetime]], now: datetime) -> LockState:
    """`overrides` are (unlocked_date, expiry) for this user, not revoked."""
    locked = any(s <= day <= e for s, e in lock_ranges)
    if not locked:
        return LockState(False, True)
    return LockState(True, any(d == day and exp > now for d, exp in overrides))


def check_writable(state: LockState, role: str, reason: str | None) -> None:
    """Locked days refuse changes (423) unless an unlock is open, or a Manager/Admin gives a reason (FR-027)."""
    if state.open_for_user:
        return
    if role in MANAGERS and reason and reason.strip():
        return
    raise RuleError("This day is locked. Request an unlock first.", status=423)


def unlock_expiry(start: datetime) -> datetime:
    return start + timedelta(hours=UNLOCK_HOURS)


# ---------- roles (FR-003, FR-004)

def check_role_change(actor_role: str, actor_id: int, target_id: int, target_role: str, new_role: str) -> None:
    if new_role not in ROLES:
        raise RuleError("Unknown role", status=422)
    if actor_id == target_id:
        raise RuleError("You cannot change your own role or access")
    if actor_role not in MANAGERS:
        raise RuleError("Not allowed for your role", status=403)
    if actor_role == "manager" and (target_role in MANAGERS or new_role in MANAGERS):
        raise RuleError("Only admins can manage manager and admin accounts", status=403)


def company_email(email: str, domain: str) -> str:
    e = email.strip().lower()
    if not e.endswith("@" + domain):
        raise RuleError(f"Only @{domain} accounts can sign in.", status=403)
    return e
