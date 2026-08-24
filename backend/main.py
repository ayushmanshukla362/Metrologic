"""Minimal FastAPI foundation for the MetroLogic MVP."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path
import shutil
import tempfile
from typing import Literal
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_session
from .models import InspectionSession
from .persistence import persist_inspection
from .pipeline import run_inspection


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


class InspectionResponse(BaseModel):
    session_id: UUID
    image_id: str
    overall_status: str
    extracted_fields: dict[str, Any]
    confidence: dict[str, float]
    compliance_evaluations: list[dict[str, Any]]
    errors: list[dict[str, Any]]


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://metrologic-frontend.onrender.com",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


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


@app.post("/api/inspection", response_model=InspectionResponse)
def create_inspection(
    file: UploadFile = File(...),
    database_session: Session = Depends(get_db),
) -> InspectionResponse:
    """Run and persist one uploaded package inspection."""
    if not file.filename or not file.content_type or not file.content_type.startswith(
        "image/"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A supported image file is required",
        )

    suffix = Path(file.filename).suffix.lower() or ".img"
    image_id = str(uuid4())

    try:
        with tempfile.TemporaryDirectory(
            prefix=".metrologic-",
            dir=Path(__file__).resolve().parent,
        ) as temp_dir:
            image_path = Path(temp_dir) / f"{image_id}{suffix}"
            with image_path.open("wb") as destination:
                shutil.copyfileobj(file.file, destination)

            try:
                with Image.open(image_path) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is not a valid image",
                ) from None

            try:
                pipeline_result = run_inspection(image_path, image_id=image_id)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Inspection processing failed",
                ) from None

            try:
                inspection_session = persist_inspection(
                    pipeline_result,
                    image_path,
                    database_session,
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to persist inspection",
                ) from None
    except HTTPException:
        raise
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to stage uploaded image",
        ) from None
    finally:
        file.file.close()

    compliance_result = pipeline_result.get("compliance_result") or {}
    return InspectionResponse(
        session_id=inspection_session.id,
        image_id=str(pipeline_result.get("image_id") or image_id),
        overall_status=str(compliance_result.get("overall_status") or "REVIEW_REQUIRED"),
        extracted_fields=pipeline_result.get("extracted_fields") or {},
        confidence=pipeline_result.get("confidence") or {},
        compliance_evaluations=compliance_result.get("evaluations") or [],
        errors=pipeline_result.get("errors") or [],
    )
