"""API tests need PostgreSQL 16. Set TEST_DATABASE_URL to an EMPTY test database, e.g.
    TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/task_tracker_test pytest
The database is wiped and rebuilt from database/*.sql for the test run.
Tests in test_rules.py run without a database."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = os.getenv("TEST_DATABASE_URL")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
    os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
    os.environ["DEV_LOGIN"] = "true"
    os.environ["ALLOWED_DOMAIN"] = "awsys-i.com"


@pytest.fixture(scope="session")
def db_ready():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    from sqlalchemy import create_engine

    engine = create_engine(TEST_DB)
    with engine.connect() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.commit()
        for f in ["database/schema.sql", *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "database/migrations").glob("*.sql")), "database/seed.sql"]:
            conn.exec_driver_sql((ROOT / f).read_text())
            conn.commit()
    engine.dispose()


@pytest.fixture
def client_for(db_ready):
    """client_for('aisha.rahman') -> a TestClient signed in as that user."""
    from fastapi.testclient import TestClient

    from app.main import app

    def make(name: str) -> TestClient:
        c = TestClient(app)
        r = c.post("/api/auth/login", json={"email": f"{name}@awsys-i.com"})
        assert r.status_code == 200, r.text
        return c

    return make
