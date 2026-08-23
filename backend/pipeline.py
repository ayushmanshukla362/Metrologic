"""In-memory Phase 4A orchestration for a single MetroLogic inspection."""

from pathlib import Path
from typing import Any

from PIL import Image

from backend.ai_extractor import OCRBlock, extract_image as extract_ocr_image
from backend.confidence import FIELD_KEYS, process_extracted_data
from backend.rules import REVIEW_REQUIRED, evaluate_all_rules
from backend.vision_evidence import map_vision_evidence
from backend.vision_extractor import (
    VisionExtractionError,
    extract_image as extract_vision_image,
)


def _empty_extraction() -> dict[str, dict[str, Any]]:
    return {
        field_key: {
            "value": None,
            "raw_source": None,
            "source_block_ids": [],
        }
        for field_key in FIELD_KEYS
    }


def _confidence_summary(
    extracted_fields: dict[str, dict[str, Any]],
) -> dict[str, float]:
    return {
        field_key: float(field_data.get("confidence", 0.0))
        for field_key, field_data in extracted_fields.items()
    }


def _result(
    image_id: str,
    ocr_blocks: list[OCRBlock],
    extracted_fields: dict[str, dict[str, Any]],
    compliance_result: dict[str, Any],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "image_id": image_id,
        "ocr_blocks": [block.model_dump() for block in ocr_blocks],
        "extracted_fields": extracted_fields,
        "confidence": _confidence_summary(extracted_fields),
        "compliance_result": compliance_result,
        "errors": errors,
    }


def run_inspection(
    image_path: str | Path,
    image_id: str | None = None,
    is_food_product: bool = False,
) -> dict[str, Any]:
    """Run OCR, Vision, evidence mapping, confidence, and legal evaluation in memory."""
    path = Path(image_path)
    resolved_image_id = image_id or path.stem

    try:
        with Image.open(path) as image:
            image_width, image_height = image.size
        ocr_blocks, _ = extract_ocr_image(path, resolved_image_id)
    except (OSError, RuntimeError, ValueError) as error:
        empty_fields = process_extracted_data(_empty_extraction(), [])
        return _result(
            resolved_image_id,
            [],
            empty_fields,
            {"overall_status": REVIEW_REQUIRED, "evaluations": []},
            [{"error": "ocr_error", "message": str(error)}],
        )

    vision_result = extract_vision_image(path)
    if isinstance(vision_result, VisionExtractionError):
        empty_fields = process_extracted_data(_empty_extraction(), ocr_blocks)
        return _result(
            resolved_image_id,
            ocr_blocks,
            empty_fields,
            {"overall_status": REVIEW_REQUIRED, "evaluations": []},
            [vision_result.model_dump()],
        )

    mapped_fields = map_vision_evidence(
        vision_result,
        ocr_blocks,
        resolved_image_id,
        image_width,
        image_height,
    )
    extracted_fields = process_extracted_data(mapped_fields, ocr_blocks)
    compliance_result = evaluate_all_rules(
        extracted_fields,
        is_food_product=is_food_product,
    )
    return _result(
        resolved_image_id,
        ocr_blocks,
        extracted_fields,
        compliance_result,
        [],
    )
