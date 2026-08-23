"""Persistence adapter for the in-memory Phase 4A inspection result."""

from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from PIL import Image
from sqlalchemy.orm import Session

from backend.models import (
    ComplianceResult,
    ExtractedField,
    InspectionImage,
    InspectionSession,
    OCRBlock,
)
from backend.rules import REVIEW_REQUIRED


FIELD_RULE_IDS = {
    "commodity_name": "LM-PCR-6-1-b",
    "net_quantity": "LM-PCR-6-1-c",
    "mfg_date": "LM-PCR-6-1-d",
    "mrp": "LM-PCR-6-1-e",
    "manufacturer": "LM-PCR-6-1-a",
}
SESSION_PROCESSING = "PROCESSING"
SESSION_COMPLETED = "COMPLETED"


def _image_dimensions(image_path: str | Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def _evaluation_by_field(
    evaluations: list[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    rule_to_field = {rule_id: field for field, rule_id in FIELD_RULE_IDS.items()}
    return {
        rule_to_field[evaluation["rule_id"]]: evaluation
        for evaluation in evaluations
        if evaluation.get("rule_id") in rule_to_field
    }


def persist_inspection(
    pipeline_result: Mapping[str, Any],
    image_path: str | Path,
    database_session: Session,
    *,
    panel_type: str | None = None,
    processing_time_ms: int | None = None,
) -> InspectionSession:
    """Persist one complete pipeline result in a single database transaction."""
    started = perf_counter()
    path = Path(image_path)
    width, height = _image_dimensions(path)
    image_id = str(pipeline_result.get("image_id") or path.stem)
    compliance_result = pipeline_result.get("compliance_result") or {}
    overall_status = compliance_result.get("overall_status")
    errors = pipeline_result.get("errors") or []
    evaluations = compliance_result.get("evaluations") or []
    evaluation_by_field = _evaluation_by_field(evaluations)

    inspection_session = InspectionSession(
        status=SESSION_PROCESSING,
        overall_status=overall_status,
    )
    image = InspectionImage(
        session=inspection_session,
        panel_type=panel_type,
        image_path=str(path),
        width=width,
        height=height,
    )

    try:
        database_session.add(inspection_session)
        database_session.add(image)

        for block in pipeline_result.get("ocr_blocks") or []:
            bbox = block.get("bbox") or [None, None, None, None]
            database_session.add(
                OCRBlock(
                    image=image,
                    text=block.get("text"),
                    x=bbox[0],
                    y=bbox[1],
                    width=bbox[2],
                    height=bbox[3],
                    normalized_x1=block.get("normalized_x1"),
                    normalized_y1=block.get("normalized_y1"),
                    normalized_x2=block.get("normalized_x2"),
                    normalized_y2=block.get("normalized_y2"),
                    ocr_confidence=block.get("ocr_confidence"),
                )
            )

        for field_key, field_data in (
            pipeline_result.get("extracted_fields") or {}
        ).items():
            evaluation = evaluation_by_field.get(field_key) or {}
            source_block_ids = field_data.get("source_block_ids") or []
            database_session.add(
                ExtractedField(
                    session=inspection_session,
                    field_key=field_key,
                    value=field_data.get("value"),
                    unit=field_data.get("unit"),
                    raw_source=field_data.get("raw_source"),
                    source_block_ids=list(source_block_ids),
                    confidence=field_data.get("confidence"),
                    status=evaluation.get("status"),
                )
            )

        for evaluation in evaluations:
            database_session.add(
                ComplianceResult(
                    session=inspection_session,
                    rule_id=evaluation["rule_id"],
                    requirement=evaluation["requirement"],
                    status=evaluation["status"],
                    reason=evaluation.get("reason"),
                    evidence=list(evaluation.get("evidence") or []),
                )
            )

        elapsed_ms = int((perf_counter() - started) * 1000)
        inspection_session.processing_time_ms = (
            processing_time_ms if processing_time_ms is not None else elapsed_ms
        )
        inspection_session.status = (
            REVIEW_REQUIRED if errors else SESSION_COMPLETED
        )
        database_session.commit()
        return inspection_session
    except Exception:
        database_session.rollback()
        raise
