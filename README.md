# AWS Task Tracker – Backend
 
API for the AWS Task Tracker timesheet app. Handles sign-in, roles, projects, time logging, leave, dashboards, locks, reports, export and the audit log. Every request checks the user's role and project membership.
 
## Tech Stack
 
- Python 3.12, FastAPI
- PostgreSQL 16
- Google SSO (@awsys-i.com only)
- pytest for tests
## Project Structure
 
```
aws-task-tracker-backend/
├── app/
│   ├── main.py              App start-up and routes
│   ├── core/                Settings, database connection, security, roles
│   ├── models/              Database tables
│   ├── schemas/             Request and response formats
│   ├── api/                 Endpoints by feature
│   │   ├── auth.py          Sign-in, session, sign-out
│   │   ├── setup.py         Projects, tasks, items, templates
│   │   ├── assignments.py   Project members, role, start/end dates
│   │   ├── activity.py      Start, Break, End task, edit, corrections
│   │   ├── leave.py         VL and SL
│   │   ├── dashboards.py    Dashboards, filters, drill-down
│   │   ├── locks.py         Locks, unlock requests, overrides
│   │   ├── notifications.py Notifications
│   │   ├── reports.py       Reports and XLSX/CSV export
│   │   └── admin.py         Users, roles, audit log
│   ├── services/            Business rules (8-hour check, 72-hour expiry, totals)
│   └── jobs/                Scheduled jobs (reminders, unlock expiry)
├── database/
│   └── schema.sql           Database Schema v1.3 (15 tables)
├── tests/                   pytest tests
├── .env.example             Settings template
├── requirements.txt         Python packages
└── README.md
```
 
## Setup
 
1. Clone and install:
```
   git clone <repo-url> aws-task-tracker-backend
   cd aws-task-tracker-backend
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
```
2. Create the database:
```
   createdb task_tracker
   psql task_tracker -f database/schema.sql
```
3. Copy `.env.example` to `.env` and fill in:
```
   DATABASE_URL=postgresql://user:password@localhost:5432/task_tracker
   GOOGLE_CLIENT_ID=
   GOOGLE_CLIENT_SECRET=
   JWT_SECRET=
   ADMIN_EMAILS=admin@awsys-i.com
   ALLOWED_DOMAIN=awsys-i.com
   FRONTEND_URL=http://localhost:5173
```
4. Run the API:
```
   uvicorn app.main:app --reload
```
   API: http://localhost:8000 · API docs: http://localhost:8000/docs
 
## Tests
 
```
pytest
```
 
## Rules
 
- Never commit `.env` or any keys.
- Check permissions in the API, not only in the frontend.
- Link each pull request to its FR ID and test case (TC-xxx).
 
