"""AWS Task Tracker API (FastAPI). Run: uvicorn app.main:app --reload"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import activity, admin, assignments, auth, dashboards, leave, locks, notifications, reports, setup
from app.core.config import settings
from app.services.rules import RuleError

app = FastAPI(title="AWS Task Tracker API", version="1.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,  # the session is a cookie
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RuleError)
def rule_error(_: Request, exc: RuleError) -> JSONResponse:
    """Business rule broken -> 400 (or the status the rule sets, e.g. 403, 422, 423)."""
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


for module in (auth, admin, setup, assignments, activity, leave, locks, notifications, reports, dashboards):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
