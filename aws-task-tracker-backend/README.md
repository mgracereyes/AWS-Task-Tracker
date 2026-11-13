# AWS Task Tracker – Backend

API for the AWS Task Tracker timesheet app (Requirements v1.2, FR-001 to FR-035; Process Flow v1.3). It handles sign-in, roles, projects and templates, assignments, time logging, leave, dashboards, locks and unlock requests, notifications, reports and export, and the audit log.

Every request checks the user's role **and** project membership. The frontend only hides buttons; this API is the real security check.

## Tech Stack

- Python 3.12, FastAPI, SQLAlchemy 2, psycopg 3
- PostgreSQL 16 (Database Schema v1.3)
- Session: signed JWT in an httpOnly cookie (no token in the browser's JavaScript)
- Google sign-in (on hold, WBS T07); development email sign-in until then
- pytest

## Project Structure

```
aws-task-tracker-backend/
├── app/
│   ├── main.py                FastAPI app, CORS, security headers, error handling
│   ├── core/
│   │   ├── config.py          Settings from .env
│   │   ├── db.py              Database session per request (commit / rollback)
│   │   ├── security.py        Session cookie, current user, role checks
│   │   ├── audit.py           Audit log writer
│   │   └── errors.py          400 / 401 / 403 / 404 / 422 / 423 errors
│   ├── models/                Tables (match database/schema.sql)
│   ├── schemas/               Request and response formats (camelCase JSON)
│   ├── services/
│   │   ├── rules.py           Business rules with no database (8 hours, 72 hours, leave, roles)
│   │   └── access.py          Who can see what; locked-day checks
│   ├── api/
│   │   ├── auth.py            /api/auth       sign in (Google or dev), sign out, me
│   │   ├── admin.py           /api/admin      people, roles, business unit, projects, audit log
│   │   ├── setup.py           /api/setup      projects, tasks, items, templates
│   │   ├── assignments.py     /api/assignments
│   │   ├── activity.py        /api/activity   entries, breaks, Admin corrections
│   │   ├── leave.py           /api/leave
│   │   ├── locks.py           /api/locks      locks, unlock requests, 72-hour window
│   │   ├── notifications.py   /api/notifications
│   │   ├── reports.py         /api/reports    report rows, XLSX / CSV export
│   │   ├── dashboards.py      /api/dashboards grouped totals
│   │   └── convert.py         Database rows -> API responses
│   └── jobs/__main__.py       Scheduled job: expire unlock requests after 72 hours
├── database/
│   ├── schema.sql             Database Schema v1.3 (15 tables)
│   ├── migrations/            Changes after v1.3 (001: users.business_unit)
│   └── seed.sql               Sample people and projects (development only)
├── tests/
│   ├── test_rules.py          Business rules (no database needed)
│   └── test_api.py            API tests against PostgreSQL
├── .env.example
└── requirements.txt
```

## Setup

1. Install:
   ```
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Create the database:
   ```
   createdb task_tracker
   psql task_tracker -v ON_ERROR_STOP=1 -f database/schema.sql
   psql task_tracker -v ON_ERROR_STOP=1 -f database/migrations/001_users_business_unit.sql
   psql task_tracker -v ON_ERROR_STOP=1 -f database/seed.sql      # sample data, development only
   ```
3. Copy `.env.example` to `.env`. Set `DATABASE_URL` and a long random `JWT_SECRET` (the app will not start with the example value).
4. Run:
   ```
   uvicorn app.main:app --reload
   ```
   API: http://localhost:8000 · API docs: http://localhost:8000/docs
5. Connect the frontend: in the frontend `.env` set `VITE_USE_MOCK=false` and `VITE_API_URL=http://localhost:8000`.

Sample sign-ins (with `DEV_LOGIN=true`): `aisha.rahman@awsys-i.com` (Employee), `dana.lopez@awsys-i.com` (Team lead), `eli.park@awsys-i.com` (Manager), `fay.ong@awsys-i.com` (Admin).

## Scheduled job

Run every 15 minutes (cron on-premise, EventBridge on AWS):
```
python -m app.jobs
```

## Tests

```
pytest tests/test_rules.py                                    # no database needed
TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/task_tracker_test pytest
```
`TEST_DATABASE_URL` must point to an **empty test database**; the tests wipe and rebuild it.

## Main rules enforced

| Rule | Where |
|---|---|
| Only @awsys-i.com accounts; deactivated users lose access at once | auth.py, security.py |
| Employees see their own data; team leads add their team; Manager/Admin see all | access.py |
| Private projects only for members, their lead and Manager/Admin | access.py |
| Only project members log time; archived options refused | access.py |
| No future dates; end after start; max 24 h a day | rules.py |
| Locked days return 423; an allowed unlock opens one day for one person for 72 hours | rules.py, locks.py |
| Manager/Admin overrides and Admin corrections need a reason | rules.py, activity.py |
| Team leads assign their own team only | assignments.py |
| Templates shared with Everyone need Manager approval | setup.py |
| Export is Manager and Admin only | reports.py |
| Every change is audited; the audit table cannot be changed | audit.py, schema.sql |

## Rules for contributors

- Never commit `.env` or any key. Set `DEV_LOGIN=false` and `COOKIE_SECURE=true` in production.
- Database changes go in a new file in `database/migrations/`.
- Link each pull request to its FR ID and test case (TC-xxx).
