"""Minimal FastAPI foundation for the MetroLogic MVP."""

from collections.abc import Generator
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_session
from .models import InspectionSession


class HealthResponse(BaseModel):
    status: Literal["ok"]


class SessionInitRequest(BaseModel):
    status: Literal["CREATED"]


class SessionInitResponse(BaseModel):
    session_id: UUID
    status: str


class InspectionSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    status: str | None
    overall_status: str | None
    created_at: datetime
    processing_time_ms: int | None


def get_db() -> Generator[Session, None, None]:
    """Provide a request-scoped SQLAlchemy session."""
    try:
        database_session = get_session()
    except (RuntimeError, SQLAlchemyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None

    try:
        yield database_session
    finally:
        database_session.close()


app = FastAPI(title="MetroLogic API")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/api/session/init",
    response_model=SessionInitResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_session(
    payload: SessionInitRequest, database_session: Session = Depends(get_db)
) -> SessionInitResponse:
    inspection_session = InspectionSession(status=payload.status)
    try:
        database_session.add(inspection_session)
        database_session.commit()
        database_session.refresh(inspection_session)
    except SQLAlchemyError:
        database_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to create inspection session",
        ) from None

    return SessionInitResponse(
        session_id=inspection_session.id,
        status=inspection_session.status or payload.status,
    )


@app.get(
    "/api/session/{session_id}",
    response_model=InspectionSessionResponse,
)
def get_inspection_session(
    session_id: UUID, database_session: Session = Depends(get_db)
) -> InspectionSessionResponse:
    try:
        inspection_session = database_session.get(InspectionSession, session_id)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch inspection session",
        ) from None

    if inspection_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection session not found",
        )

    return InspectionSessionResponse(
        session_id=inspection_session.id,
        status=inspection_session.status,
        overall_status=inspection_session.overall_status,
        created_at=inspection_session.created_at,
        processing_time_ms=inspection_session.processing_time_ms,
    )
