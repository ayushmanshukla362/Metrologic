"""SQLAlchemy models for the MetroLogic Phase 2A database foundation."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class InspectionSession(Base):
    __tablename__ = "inspection_sessions"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str | None] = mapped_column(String(32))
    overall_status: Mapped[str | None] = mapped_column(String(32))
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)

    images: Mapped[list["InspectionImage"]] = relationship(
        back_populates="session"
    )
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="session"
    )
    compliance_results: Mapped[list["ComplianceResult"]] = relationship(
        back_populates="session"
    )


class InspectionImage(Base):
    __tablename__ = "inspection_images"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("inspection_sessions.id"),
        nullable=False,
        index=True,
    )
    panel_type: Mapped[str | None] = mapped_column(String(64))
    image_path: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped["InspectionSession"] = relationship(back_populates="images")
    ocr_blocks: Mapped[list["OCRBlock"]] = relationship(
        back_populates="image"
    )


class OCRBlock(Base):
    __tablename__ = "ocr_blocks"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    image_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("inspection_images.id"),
        nullable=False,
        index=True,
    )
    text: Mapped[str | None] = mapped_column(Text)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    width: Mapped[float | None] = mapped_column(Float)
    height: Mapped[float | None] = mapped_column(Float)
    normalized_x1: Mapped[float | None] = mapped_column(Float)
    normalized_y1: Mapped[float | None] = mapped_column(Float)
    normalized_x2: Mapped[float | None] = mapped_column(Float)
    normalized_y2: Mapped[float | None] = mapped_column(Float)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)

    image: Mapped["InspectionImage"] = relationship(back_populates="ocr_blocks")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("inspection_sessions.id"),
        nullable=False,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Any | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(32))
    raw_source: Mapped[str | None] = mapped_column(Text)
    source_block_ids: Mapped[Any | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(32))

    session: Mapped["InspectionSession"] = relationship(
        back_populates="extracted_fields"
    )


class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("inspection_sessions.id"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[Any | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped["InspectionSession"] = relationship(
        back_populates="compliance_results"
    )
