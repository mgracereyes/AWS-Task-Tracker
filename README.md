# AWS Task Tracker

A timesheet and task-tracking web app for AWSYS-I. Employees log their daily work by project, task and item. Team leads and managers see effort, check missing hours and lock finished periods.

Only company Google accounts (@awsys-i.com) can sign in.

## Features

- **Sign-in and roles** – Google sign-in; Employee, Team Lead, Manager and Admin
- **Setup** – projects, tasks and items from templates; Save as template; Public or Private projects
- **Assignments** – add people to projects with a role and start/end dates
- **Activity** – Start, Break and End task timer; edit entries; 8-hour daily reminder
- **Leave** – VL and SL, whole or half day
- **Dashboards** – employee and team views, manager overview with filters and drill-down
- **Locks** – lock past dates; unlock requests open a day for 72 hours
- **Reports** – filter and export to XLSX or CSV (Manager and Admin)
- **Audit log** – records sign-ins, changes, locks and exports

## Tech Stack

| Part | Technology |
|---|---|
| Frontend | React |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 16 |
| Sign-in | Google SSO |
| Server | Nginx (local) or AWS (CloudFront, API Gateway, Lambda, RDS) |

## Project Structure

```
aws-task-tracker/
├── backend/            FastAPI app and API tests (pytest)
├── frontend/           React app and UI tests (Vitest)
├── database/
│   └── schema.sql      Database Schema v1.3 (15 tables)
├── e2e/                Playwright end-to-end tests
├── docs/
│   ├── requirements/   Requirements v1.2 (FR-001 to FR-035)
│   ├── design/         UI mockups, flowchart, architecture, database diagram
│   ├── technical/      Technical Documentation v1.3
│   ├── testing/        Test strategy and test cases (TC-001 to TC-152)
│   └── planning/       Estimation and WBS
├── .github/            Pull request and issue templates, CI workflow
└── README.md
```

## Documents

| Document | File |
|---|---|
| Requirements | `docs/requirements/AWS_Task_Tracker_Requirements_v1.2.xlsx` |
| Technical documentation | `docs/technical/Technical_Documentation_v1.3.xlsx` |
| Process flowchart | `docs/design/AWS_Task_Tracker_Flowchart_v1.3.png` |
| System architecture | `docs/design/System_Architecture_Local_v1.3.png`, `System_Architecture_AWS_v1.3.png` |
| Database schema | `docs/design/Database_Schema_v1.3.md`, `database/schema.sql` |
| Test strategy | `docs/testing/TEST_STRATEGY.md` |
| Test cases | `docs/testing/AWS_Task_Tracker_Testing.xlsx` |
| Plan | `docs/planning/AWS_Task_Tracker_Estimation_and_Planning.xlsx` |

## Getting Started

1. Create the database:
   ```
   psql "$DATABASE_URL" -f database/schema.sql
   ```
2. Copy `.env.example` to `.env` and fill in the database URL and Google sign-in keys. Never commit `.env`.
3. Start the backend and frontend (steps to be added when the code is set up).

## Status

Version 1.3 documents are ready. Development starts with Sprint 1 (sign-in and roles).
