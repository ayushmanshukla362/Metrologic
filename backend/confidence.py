"""Deterministic confidence scoring for validated MetroLogic extraction fields."""

import math
import re
from collections.abc import Mapping
from typing import Any


CONFIDENCE_THRESHOLD = 0.80
FIELD_KEYS = (
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


def _source_ids(field_data: Mapping[str, Any]) -> list[Any]:
    source_ids = field_data.get("source_block_ids") or []
    if isinstance(source_ids, str):
        source_ids = [source_ids]
    return list(source_ids)


def _block_data(block: Any) -> Mapping[str, Any]:
    return _as_mapping(block)


def _valid_block_ids(ocr_blocks: list[Mapping[str, Any]]) -> set[str]:
    return {
        str(block["block_id"])
        for block in ocr_blocks
        if block.get("block_id")
    }


def _format_is_valid(field_key: str, field_data: Mapping[str, Any]) -> bool:
    value = field_data.get("value")
    if value is None or value == "":
        return False
    if field_key == "net_quantity":
        return str(field_data.get("unit") or "").lower() in {"g", "kg", "ml", "l", "n"}
    if field_key == "mrp":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and float(value) >= 0
        )
    if field_key == "mfg_date":
        return bool(re.search(r"\d", str(value)))
    return True


def _spatial_anchor_score(
    field_key: str,
    matched_blocks: list[Mapping[str, Any]],
    ocr_blocks: list[Mapping[str, Any]],
) -> float:
    """Score proximity of evidence to a deterministic OCR text anchor."""
    anchors = {
        "commodity_name": ("commodity", "product", "name"),
        "net_quantity": ("net", "qty", "quantity", "weight", "volume"),
        "mfg_date": ("mfg", "manufactured", "manufacture", "date"),
        "mrp": ("mrp", "price", "rs", "inr"),
        "manufacturer": ("manufacturer", "manufactured", "marketed", "packed"),
    }
    anchor_blocks = [
        block
        for block in ocr_blocks
        if any(word in str(block.get("text", "")).lower() for word in anchors[field_key])
    ]
    if not matched_blocks or not anchor_blocks:
        return 0.0
    if any(evidence in anchor_blocks for evidence in matched_blocks):
        return 1.0

    distances = []
    for evidence in matched_blocks:
        evidence_box = evidence.get("bbox")
        if not evidence_box or len(evidence_box) != 4:
            continue
        ex, ey, ew, eh = evidence_box
        for anchor in anchor_blocks:
            anchor_box = anchor.get("bbox")
            if not anchor_box or len(anchor_box) != 4:
                continue
            ax, ay, aw, ah = anchor_box
            distances.append(
                abs((ex + ew / 2) - (ax + aw / 2))
                + abs((ey + eh / 2) - (ay + ah / 2))
            )
    if not distances:
        return 0.0
    return round(max(0.0, 1.0 - min(distances) / 600.0), 2)


def calculate_field_confidence(
    field_key: str,
    field_data: Mapping[str, Any] | Any,
    ocr_blocks: list[Mapping[str, Any]] | list[Any],
) -> float:
    """Calculate explainable confidence from OCR, format, evidence, and proximity."""
    field_data = _as_mapping(field_data)
    if field_key not in FIELD_KEYS or field_data.get("value") in (None, ""):
        return 0.0

    normalized_blocks = [_block_data(block) for block in ocr_blocks]
    source_ids = _source_ids(field_data)
    if source_ids and any(
        source_id not in _valid_block_ids(normalized_blocks)
        for source_id in source_ids
    ):
        return 0.0

    blocks_by_id = {
        str(block.get("block_id")): block for block in normalized_blocks
    }
    matched_blocks = [
        blocks_by_id[source_id]
        for source_id in source_ids
        if source_id in blocks_by_id
    ]
    anchor_score = 1.0 if matched_blocks else 0.0
    ocr_scores = []
    for block in matched_blocks:
        try:
            score = float(block.get("ocr_confidence", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        if score > 1.0:
            score /= 100.0
        ocr_scores.append(max(0.0, min(1.0, score)))
    ocr_score = sum(ocr_scores) / len(ocr_scores) if ocr_scores else 0.0
    format_score = 1.0 if _format_is_valid(field_key, field_data) else 0.0
    proximity_score = _spatial_anchor_score(
        field_key, matched_blocks, normalized_blocks
    )
    return round(
        (0.45 * ocr_score)
        + (0.20 * anchor_score)
        + (0.15 * format_score)
        + (0.20 * proximity_score),
        2,
    )


def process_extracted_data(
    ai_output: Mapping[str, Any] | Any,
    ocr_blocks: list[Mapping[str, Any]] | list[Any],
) -> dict[str, dict[str, Any]]:
    """Add deterministic confidence without adding legal or domain fields."""
    ai_output = _as_mapping(ai_output)
    processed: dict[str, dict[str, Any]] = {}
    for field_key in FIELD_KEYS:
        field_data = _as_mapping(ai_output.get(field_key) or {})
        source_block_ids = field_data.get("source_block_ids") or []
        if isinstance(source_block_ids, list):
            source_block_ids = source_block_ids.copy()
        validated_field = {
            "value": field_data.get("value"),
            "raw_source": field_data.get("raw_source"),
            "source_block_ids": source_block_ids,
            "confidence": calculate_field_confidence(
                field_key, field_data, ocr_blocks
            ),
        }
        if "unit" in field_data:
            validated_field["unit"] = field_data.get("unit")
        processed[field_key] = validated_field
    return processed
