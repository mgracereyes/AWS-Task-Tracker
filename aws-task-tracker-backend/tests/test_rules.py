"""Business rules with no database (run anywhere: pytest tests/test_rules.py)."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.services import rules
from app.services.rules import RuleError

NOW = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)


def test_effort_minutes():  # FR-018
    assert rules.effort_minutes(time(9, 0), time(12, 30)) == 210
    with pytest.raises(RuleError):
        rules.effort_minutes(time(12, 0), time(11, 0))


def test_no_future_dates():
    with pytest.raises(RuleError, match="future"):
        rules.check_entry_date(date(2026, 10, 22), today=date(2026, 10, 21))


def test_day_cannot_exceed_24_hours():
    with pytest.raises(RuleError):
        rules.check_day_total(23 * 60, 2 * 60)


def test_workdays_skip_weekends():  # FR-024
    assert rules.workdays(date(2026, 10, 9), date(2026, 10, 12)) == [date(2026, 10, 9), date(2026, 10, 12)]


def test_range_limits():  # FR-021
    with pytest.raises(RuleError):
        rules.check_range(date(2026, 10, 2), date(2026, 10, 1))
    with pytest.raises(RuleError):
        rules.check_range(date(2026, 1, 1), date(2026, 6, 1))


def test_leave_counts_toward_8_hours():  # FR-020
    half_sl = [(date(2026, 10, 14), date(2026, 10, 14), "half")]
    assert rules.minutes_short(240, rules.leave_minutes_on(date(2026, 10, 14), half_sl), date(2026, 10, 14)) == 0
    assert rules.minutes_short(360, 0, date(2026, 10, 15)) == 120
    assert rules.minutes_short(0, 0, date(2026, 10, 17)) == 0  # Saturday


def test_leave_hours():  # FR-024
    assert rules.leave_hours(date(2026, 10, 9), date(2026, 10, 12), "whole") == 16
    assert rules.leave_hours(date(2026, 10, 14), date(2026, 10, 14), "half") == 4
    with pytest.raises(RuleError):
        rules.leave_hours(date(2026, 10, 14), date(2026, 10, 15), "half")
    with pytest.raises(RuleError):
        rules.leave_hours(date(2026, 10, 17), date(2026, 10, 18), "whole")


def test_locked_day_and_72_hour_window():  # FR-025, FR-026
    locks = [(date(2026, 9, 1), date(2026, 9, 30))]
    day = date(2026, 9, 24)
    assert rules.lock_state(date(2026, 10, 1), locks, [], NOW) == rules.LockState(False, True)
    closed = rules.lock_state(day, locks, [], NOW)
    assert closed.locked and not closed.open_for_user
    with pytest.raises(RuleError) as e:
        rules.check_writable(closed, "employee", None)
    assert e.value.status == 423
    open_ = rules.lock_state(day, locks, [(day, NOW + timedelta(hours=1))], NOW)
    rules.check_writable(open_, "employee", None)
    expired = rules.lock_state(day, locks, [(day, NOW - timedelta(minutes=1))], NOW)
    assert not expired.open_for_user
    assert rules.unlock_expiry(NOW) - NOW == timedelta(hours=72)


def test_manager_override_needs_reason():  # FR-027
    closed = rules.LockState(True, False)
    with pytest.raises(RuleError):
        rules.check_writable(closed, "manager", "  ")
    rules.check_writable(closed, "manager", "Payroll correction")
    with pytest.raises(RuleError):
        rules.check_writable(closed, "team_lead", "reason")


def test_role_changes():  # FR-003, FR-004
    with pytest.raises(RuleError) as e:
        rules.check_role_change("manager", 2, 6, "employee", "admin")
    assert e.value.status == 403
    with pytest.raises(RuleError):
        rules.check_role_change("admin", 1, 1, "admin", "employee")  # own role
    with pytest.raises(RuleError) as e:
        rules.check_role_change("admin", 1, 6, "employee", "owner")
    assert e.value.status == 422
    rules.check_role_change("manager", 2, 6, "employee", "team_lead")


def test_company_email_only():  # FR-001
    assert rules.company_email(" Aisha.Rahman@AWSYS-I.com ", "awsys-i.com") == "aisha.rahman@awsys-i.com"
    with pytest.raises(RuleError) as e:
        rules.company_email("someone@gmail.com", "awsys-i.com")
    assert e.value.status == 403
    with pytest.raises(RuleError):
        rules.company_email("x@awsys-i.com.evil.com", "awsys-i.com")
