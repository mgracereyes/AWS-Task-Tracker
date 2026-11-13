"""API tests against PostgreSQL. They mirror cases in the Testing workbook (TC numbers in brackets)."""
from fastapi.testclient import TestClient

from app.main import app



def item_id(c: TestClient, project: str, task: str, item: str) -> int:
    """Look up ids by name, so tests do not depend on insert order."""
    ps = {p["name"]: p["id"] for p in c.get("/api/setup/projects").json()}
    ts = {(t["projectId"], t["name"]): t["id"] for t in c.get("/api/setup/tasks").json()}
    return next(i["id"] for i in c.get("/api/setup/items").json() if i["taskId"] == ts[(ps[project], task)] and i["name"] == item)


def user_id(c: TestClient, name: str) -> int:
    return next(u["id"] for u in c.get("/api/admin/users").json() if u["name"] == name)


def project_id(c: TestClient, name: str) -> int:
    return next(p["id"] for p in c.get("/api/setup/projects").json() if p["name"] == name)


def test_non_company_account_rejected(db_ready):  # FR-001
    r = TestClient(app).post("/api/auth/login", json={"email": "someone@gmail.com"})
    assert r.status_code == 403


def test_deactivated_user_rejected(db_ready):  # FR-015
    r = TestClient(app).post("/api/auth/login", json={"email": "kim.bautista@awsys-i.com"})
    assert r.status_code == 403


def test_not_signed_in(db_ready):
    assert TestClient(app).get("/api/activity", params={"from": "2026-10-01", "to": "2026-10-02"}).status_code == 401


def test_employee_blocked_from_locks_and_audit(client_for):  # NFR-002, NFR-005
    c = client_for("aisha.rahman")
    assert c.post("/api/locks", json={"startDate": "2026-10-01", "endDate": "2026-10-02"}).status_code == 403
    assert c.get("/api/admin/audit").status_code == 403


def test_private_project_hidden(client_for):  # FR-029
    names = [p["name"] for p in client_for("aisha.rahman").get("/api/setup/projects").json()]
    assert "Gamma" not in names and "Alpha" in names


def test_only_members_log_time(client_for):  # FR-007
    mgr = client_for("eli.park")
    DELTA_API, ALPHA_API = item_id(mgr, "Delta", "Build", "API"), item_id(mgr, "Alpha", "Build", "API")
    c = client_for("aisha.rahman")
    r = c.post("/api/activity", json={"itemId": DELTA_API, "date": "2026-10-20", "start": "09:00", "end": "10:00"})
    assert r.status_code == 403
    r = c.post("/api/activity", json={"itemId": ALPHA_API, "date": "2026-10-20", "start": "09:00", "end": "10:00"})
    assert r.status_code == 201


def test_invalid_times(client_for):  # FR-018
    c = client_for("aisha.rahman")
    ALPHA_API = item_id(c, "Alpha", "Build", "API")
    r = c.post("/api/activity", json={"itemId": ALPHA_API, "date": "2026-10-20", "start": "12:00", "end": "11:00"})
    assert r.status_code == 400


def test_locked_day_unlock_flow(client_for):  # FR-025, FR-026
    emp, mgr = client_for("aisha.rahman"), client_for("eli.park")
    ALPHA_API = item_id(emp, "Alpha", "Build", "API")
    body = {"itemId": ALPHA_API, "date": "2026-09-24", "start": "13:00", "end": "15:00"}
    assert emp.post("/api/activity", json=body).status_code == 423
    r = emp.post("/api/locks/requests", json={"date": "2026-09-24", "action": "add", "reason": "Forgot the afternoon"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client_for("dana.lopez").post(f"/api/locks/requests/{rid}/allow").status_code == 403  # team lead
    assert mgr.post(f"/api/locks/requests/{rid}/allow").status_code == 204
    assert emp.post("/api/activity", json=body).status_code == 201
    other_day = {**body, "date": "2026-09-25"}
    assert emp.post("/api/activity", json=other_day).status_code == 423


def test_team_lead_assigns_own_team_only(client_for):  # FR-031
    lead, mgr = client_for("dana.lopez"), client_for("eli.park")
    outsider = {"projectId": project_id(mgr, "Alpha"), "userId": user_id(mgr, "Omar Diaz"), "roleOnProject": "Developer", "startDate": "2026-11-01", "endDate": "2026-11-30"}
    assert lead.post("/api/assignments", json=outsider).status_code == 403
    bad_dates = {**outsider, "userId": user_id(mgr, "Aisha Rahman"), "projectId": project_id(mgr, "Delta"), "endDate": "2026-10-01"}
    assert lead.post("/api/assignments", json=bad_dates).status_code == 422


def test_export_manager_only(client_for):  # FR-013
    params = {"from": "2026-10-01", "to": "2026-10-31", "format": "xlsx"}
    assert client_for("dana.lopez").get("/api/reports/export", params=params).status_code == 403
    r = client_for("eli.park").get("/api/reports/export", params=params)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_audit_log_is_append_only(client_for, db_ready):  # NFR-005
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.db import engine

    assert len(client_for("fay.ong").get("/api/admin/audit").json()) > 0
    with engine.connect() as conn, pytest.raises(DBAPIError):
        conn.execute(text("UPDATE audit_logs SET action = 'x'"))
