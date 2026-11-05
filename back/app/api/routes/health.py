from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Report whether the API process is ready to receive requests."""

    return HealthResponse(status="ok", service="cinequote-ai-api")


@router.get("/health/ready", response_model=HealthResponse)
def readiness_check() -> HealthResponse:
    """Report readiness only when the configured database is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database is unavailable") from error
    return HealthResponse(status="ok", service="cinequote-ai-api")

