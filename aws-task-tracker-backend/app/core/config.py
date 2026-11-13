"""Settings read from environment variables (.env). Secrets never live in code (NFR-004)."""
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load KEY=VALUE lines from .env without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://task_tracker:task_tracker@localhost:5432/task_tracker")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    session_hours: int = int(os.getenv("SESSION_HOURS", "8"))
    allowed_domain: str = os.getenv("ALLOWED_DOMAIN", "awsys-i.com").lower()
    admin_emails: frozenset[str] = field(
        default_factory=lambda: frozenset(e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip())
    )
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    dev_login: bool = _bool("DEV_LOGIN")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    cookie_secure: bool = _bool("COOKIE_SECURE")
    export_dir: str = os.getenv("EXPORT_DIR", "./exports")

    expected_minutes_per_day: int = 480  # FR-020
    unlock_hours: int = 72  # FR-026
    max_range_days: int = 92  # FR-021


settings = Settings()

if not settings.jwt_secret or settings.jwt_secret.startswith("change-me"):
    # Fail early rather than run with a guessable session key.
    raise RuntimeError("Set JWT_SECRET in .env to a long random value")
