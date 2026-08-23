"""Deterministic mapping from experimental Vision bboxes to OCR evidence IDs."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import math
import re
from statistics import median
from typing import Any

from backend.ai_extractor import OCRBlock
from backend.vision_extractor import VisionExtraction


VISION_OCR_OVERLAP_THRESHOLD = 0.25
VISION_OCR_COVERAGE_THRESHOLD = 0.15
VISION_OCR_IOU_THRESHOLD = 0.02
VISION_MANUFACTURER_SECONDARY_IOU_THRESHOLD = 0.15
VISION_BBOX_COORDINATE_MAX = 1000
VISION_FIELD_KEYS = (
    "commodity_name",
    "net_quantity",
    "mfg_date",
    "mrp",
    "manufacturer",
)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value if isinstance(value, Mapping) else {}


def _valid_bbox(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    x1, y1, x2, y2 = value
    return (
        all(isinstance(coordinate, (int, float)) for coordinate in value)
        and min(value) >= 0
        and x1 <= x2
        and y1 <= y2
    )


def convert_ocr_bbox_to_native(value: Any) -> list[int | float] | None:
    """Convert an OCR bbox from [x, y, width, height] to rectangle endpoints."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(
        not isinstance(coordinate, (int, float))
        or isinstance(coordinate, bool)
        or not math.isfinite(coordinate)
        for coordinate in value
    ):
        return None

    x, y, width, height = value
    if x < 0 or y < 0 or width < 0 or height < 0:
        return None
    x2 = x + width
    y2 = y + height
    if x2 < x or y2 < y:
        return None
    return [x, y, x2, y2]


def convert_vision_bbox_to_native(
    vision_bbox: Any,
    image_width: int,
    image_height: int,
) -> list[int] | None:
    """Convert a strict Gemini 0-1000 bbox into native pixel coordinates."""
    if (
        not isinstance(image_width, int)
        or isinstance(image_width, bool)
        or not isinstance(image_height, int)
        or isinstance(image_height, bool)
        or image_width <= 0
        or image_height <= 0
        or not _valid_bbox(vision_bbox)
        or any(coordinate > VISION_BBOX_COORDINATE_MAX for coordinate in vision_bbox)
    ):
        return None

    x1, y1, x2, y2 = vision_bbox
    native_bbox = [
        round(x1 * image_width / VISION_BBOX_COORDINATE_MAX),
        round(y1 * image_height / VISION_BBOX_COORDINATE_MAX),
        round(x2 * image_width / VISION_BBOX_COORDINATE_MAX),
        round(y2 * image_height / VISION_BBOX_COORDINATE_MAX),
    ]
    native_x1, native_y1, native_x2, native_y2 = native_bbox
    if not (
        native_x1 >= 0
        and native_y1 >= 0
        and native_x2 >= native_x1
        and native_y2 >= native_y1
        and native_x2 <= image_width
        and native_y2 <= image_height
    ):
        return None
    return native_bbox


def _infer_image_dimensions(
    blocks: list[Mapping[str, Any]],
) -> tuple[int, int] | None:
    """Recover the source dimensions from OCR's native/normalized coordinates."""
    width_candidates: list[float] = []
    height_candidates: list[float] = []
    for block in blocks:
        bbox = block.get("bbox")
        native_bbox = convert_ocr_bbox_to_native(bbox)
        if native_bbox is None:
            continue
        x1, y1, x2, y2 = native_bbox
        for native, normalized, candidates in (
            (x1, block.get("normalized_x1"), width_candidates),
            (x2, block.get("normalized_x2"), width_candidates),
            (y1, block.get("normalized_y1"), height_candidates),
            (y2, block.get("normalized_y2"), height_candidates),
        ):
            if isinstance(normalized, (int, float)) and normalized > 0:
                candidates.append(native / normalized)

    if not width_candidates or not height_candidates:
        return None
    return round(median(width_candidates)), round(median(height_candidates))


def _intersection_over_ocr_area(
    vision_bbox: list[int],
    ocr_bbox: list[int],
) -> float:
    return calculate_spatial_metrics(vision_bbox, ocr_bbox)["ocr_coverage"]


def calculate_spatial_metrics(
    vision_bbox: list[int | float],
    ocr_bbox: list[int | float],
) -> dict[str, float]:
    """Calculate two-sided spatial metrics for validated endpoint rectangles."""
    vision_x1, vision_y1, vision_x2, vision_y2 = vision_bbox
    ocr_x1, ocr_y1, ocr_x2, ocr_y2 = ocr_bbox
    intersection_width = max(0, min(vision_x2, ocr_x2) - max(vision_x1, ocr_x1))
    intersection_height = max(0, min(vision_y2, ocr_y2) - max(vision_y1, ocr_y1))
    intersection_area = intersection_width * intersection_height
    vision_area = max(0, vision_x2 - vision_x1) * max(0, vision_y2 - vision_y1)
    ocr_area = max(0, ocr_x2 - ocr_x1) * max(0, ocr_y2 - ocr_y1)
    union_area = vision_area + ocr_area - intersection_area
    return {
        "intersection_area": float(intersection_area),
        "ocr_coverage": intersection_area / ocr_area if ocr_area else 0.0,
        "vision_coverage": intersection_area / vision_area
        if vision_area
        else 0.0,
        "iou": intersection_area / union_area if union_area else 0.0,
    }


_NUMBER_PATTERN = re.compile(r"(?<!\d)\d+(?:[.,]\d+)*(?!\d)")
_DATE_PATTERN = re.compile(
    r"(?<!\d)(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?!\d)"
)


def _normalized_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _numeric_tokens(value: str) -> list[Decimal]:
    tokens: list[Decimal] = []
    for token in _NUMBER_PATTERN.findall(value):
        try:
            tokens.append(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    return tokens


def _normalized_unit(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", value.casefold())
    return {
        "grams": "g",
        "gram": "g",
        "g": "g",
        "kilograms": "kg",
        "kilogram": "kg",
        "kg": "kg",
        "milliliters": "ml",
        "milliliter": "ml",
        "ml": "ml",
        "liters": "l",
        "liter": "l",
        "l": "l",
        "nos": "n",
        "n": "n",
        "inr": "inr",
        "rs": "inr",
        "rupees": "inr",
    }.get(compact, compact)


def _date_signature(value: str) -> tuple[int, int, int] | None:
    match = _DATE_PATTERN.search(value)
    if match is None:
        return None
    first, second, third = (int(part) for part in match.groups())
    if len(match.group(1)) == 4:
        return first, second, third
    if len(match.group(3)) == 4:
        return third, second, first
    return None


def _numeric_field_matches(
    field_key: str,
    field_data: Mapping[str, Any],
    ocr_text: str,
) -> bool:
    value = field_data.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        expected_number = Decimal(str(value))
    except InvalidOperation:
        return False
    numbers = _numeric_tokens(ocr_text)
    if len(numbers) != 1 or numbers[0] != expected_number:
        return False

    if field_key == "net_quantity":
        expected_unit = _normalized_unit(str(field_data.get("unit") or ""))
        units = {
            _normalized_unit(token)
            for token in re.findall(r"[a-z]+", ocr_text.casefold())
        }
        return bool(expected_unit) and expected_unit in units

    # An unlabelled numeric MRP is allowed, but unrelated labelled numbers are not.
    words = set(re.findall(r"[a-z]+", ocr_text.casefold()))
    if not words:
        return True
    return bool(words & {"mrp", "price", "rs", "inr", "rupees"})


def _text_corroborates_field(
    field_key: str,
    field_data: Mapping[str, Any],
    ocr_text: Any,
) -> bool:
    value = field_data.get("value")
    raw_source = field_data.get("raw_source")
    if value is None or not isinstance(raw_source, str) or not isinstance(ocr_text, str):
        return False
    if field_key in {"net_quantity", "mrp"}:
        return _numeric_field_matches(field_key, field_data, ocr_text)
    if field_key == "mfg_date" and isinstance(value, str):
        expected = _date_signature(value)
        return expected is not None and _date_signature(ocr_text) == expected
    if field_key == "manufacturer" and isinstance(value, str):
        normalized_ocr = _normalized_text(ocr_text)
        normalized_value = _normalized_text(value)
        return bool(normalized_ocr) and normalized_ocr in normalized_value
    return False


def _secondary_evidence_allowed(
    field_key: str,
    field_data: Mapping[str, Any],
    block: Mapping[str, Any],
    metrics: Mapping[str, float],
) -> bool:
    if metrics["ocr_coverage"] >= VISION_OCR_COVERAGE_THRESHOLD:
        return False
    if field_key == "manufacturer":
        if metrics["iou"] < VISION_MANUFACTURER_SECONDARY_IOU_THRESHOLD:
            return False
    elif metrics["iou"] < VISION_OCR_IOU_THRESHOLD:
        return False
    return _text_corroborates_field(field_key, field_data, block.get("text"))


def _belongs_to_image(block_id: str, image_id: str) -> bool:
    prefix, separator, sequence = block_id.rpartition(":b")
    return separator == ":b" and prefix == image_id and sequence.isdigit()


def _block_sort_key(
    block: Mapping[str, Any], native_bbox: list[int | float]
) -> tuple[float, float, str]:
    bbox = native_bbox
    return (bbox[1], bbox[0], str(block.get("block_id", "")))


def map_vision_evidence(
    vision_result: VisionExtraction | Mapping[str, Any],
    ocr_blocks: list[OCRBlock | Mapping[str, Any]],
    image_id: str,
    image_width: int | None = None,
    image_height: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Attach matching current-image OCR IDs to each Vision field.

    Vision bboxes use the native image dimensions when explicit dimensions are
    supplied. Existing callers can derive those dimensions from OCR blocks,
    whose native and normalized coordinates are both part of the OCR contract.
    """
    vision_data = _as_mapping(vision_result)
    normalized_blocks = [_as_mapping(block) for block in ocr_blocks]
    if image_width is None or image_height is None:
        inferred_dimensions = _infer_image_dimensions(normalized_blocks)
        if inferred_dimensions is not None:
            image_width, image_height = inferred_dimensions
    mapped: dict[str, dict[str, Any]] = {}

    for field_key in VISION_FIELD_KEYS:
        field_data = dict(_as_mapping(vision_data.get(field_key)))
        source_block_ids: list[str] = []
        vision_bbox = field_data.get("bbox")
        native_bbox = None
        if image_width is not None and image_height is not None:
            native_bbox = convert_vision_bbox_to_native(
                vision_bbox, image_width, image_height
            )
        if field_data.get("value") is not None and native_bbox is not None:
            matching_blocks: list[tuple[Mapping[str, Any], list[int | float]]] = []
            for block in normalized_blocks:
                block_id = block.get("block_id")
                block_bbox = convert_ocr_bbox_to_native(block.get("bbox"))
                if not isinstance(block_id, str) or not _belongs_to_image(
                    block_id, image_id
                ):
                    continue
                if block_bbox is None:
                    continue
                metrics = calculate_spatial_metrics(native_bbox, block_bbox)
                primary_match = (
                    metrics["ocr_coverage"] >= VISION_OCR_COVERAGE_THRESHOLD
                    and metrics["iou"] >= VISION_OCR_IOU_THRESHOLD
                )
                secondary_match = _secondary_evidence_allowed(
                    field_key, field_data, block, metrics
                )
                if primary_match or secondary_match:
                    matching_blocks.append((block, block_bbox))

            matching_blocks.sort(
                key=lambda item: _block_sort_key(item[0], item[1])
            )
            source_block_ids = [
                str(block["block_id"]) for block, _ in matching_blocks
            ]

        field_data["source_block_ids"] = source_block_ids
        mapped[field_key] = field_data

    return mapped
