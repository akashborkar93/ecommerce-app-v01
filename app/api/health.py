import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["Ops"])
logger = logging.getLogger("app.health")


@router.get("/health", summary="Liveness check")
def health() -> dict:
    """Process-only check. Does not touch dependencies."""
    return {"status": "healthy"}


@router.get(
    "/ready",
    summary="Readiness check",
    responses={503: {"description": "Database unavailable"}},
)
def ready(db: Session = Depends(get_db)):
    """Verifies the database is reachable. Intended for load balancer health checks."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("readiness check failed", extra={"error_type": type(exc).__name__})
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
