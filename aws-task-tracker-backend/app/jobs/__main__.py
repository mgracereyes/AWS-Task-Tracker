"""Scheduled jobs. Run every 15 minutes from cron / EventBridge:

    python -m app.jobs

- Marks unlock requests older than 72 hours as expired (FR-011, FR-026).
- Revokes nothing: allowed overrides simply stop working after their expiry time.
"""
from app.api.locks import expire_old_requests
from app.core.audit import audit
from app.core.db import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        n = expire_old_requests(db)
        if n:
            audit(db, None, "unlock_requests_expired", count=n)
        db.commit()
        print(f"expired {n} unlock request(s)")


if __name__ == "__main__":
    main()
