"""Deterministic confidence scoring for the AI-to-backend contract."""

import re

CONFIDENCE_THRESHOLD = 0.80


def _source_ids(field_data):
    source_ids = field_data.get("source_block_ids") or []
    if isinstance(source_ids, str):
        source_ids = [source_ids]
    if not source_ids and field_data.get("source_id"):
        source_ids = [field_data["source_id"]]
    return [str(source_id) for source_id in source_ids if source_id]


def _format_is_valid(field_key, field_data):
    value = field_data.get("value")
    if value in (None, ""):
        return False
    if field_key == "net_quantity":
        return str(field_data.get("unit") or "").lower() in {"g", "kg", "ml", "l", "n"}
    if field_key == "mrp":
        try:
            return float(value) >= 0
        except (TypeError, ValueError):
            return False
    if field_key == "mfg_date":
        return bool(re.search(r"\d", str(value)))
    return True


def _spatial_anchor_score(field_key, matched_blocks, ocr_blocks):
    """Score proximity of evidence to a deterministic label anchor in OCR layout."""
    anchors = {
        "commodity_name": ("commodity", "product", "name"),
        "net_quantity": ("net", "qty", "quantity", "weight", "volume"),
        "mfg_date": ("mfg", "manufactured", "manufacture", "date"),
        "mrp": ("mrp", "price", "rs", "inr"),
        "manufacturer": ("manufacturer", "manufactured", "marketed", "packed"),
    }
    keywords = anchors[field_key]
    anchor_blocks = [block for block in ocr_blocks if any(word in str(block.get("text", "")).lower() for word in keywords)]
    if not matched_blocks or not anchor_blocks:
        return 0.0
    for evidence in matched_blocks:
        if evidence in anchor_blocks:
            return 1.0
    distances = []
    for evidence in matched_blocks:
        e_box = evidence.get("box")
        if not e_box:
            continue
        ex, ey, ew, eh = e_box
        for anchor in anchor_blocks:
            a_box = anchor.get("box")
            if not a_box:
                continue
            ax, ay, aw, ah = a_box
            distances.append(abs((ex + ew / 2) - (ax + aw / 2)) + abs((ey + eh / 2) - (ay + ah / 2)))
    if not distances:
        return 0.0
    return round(max(0.0, 1.0 - min(distances) / 600.0), 2)


def calculate_field_confidence(field_key, field_data, ocr_blocks):
    """Calculate confidence from OCR evidence, anchors, and format validity only."""
    if not field_data or field_data.get("value") in (None, ""):
        return 0.0
    ocr_blocks = list(ocr_blocks)
    blocks_by_id = {str(block.get("block_id")): block for block in ocr_blocks}
    matched_blocks = [blocks_by_id[source_id] for source_id in _source_ids(field_data) if source_id in blocks_by_id]
    anchor_score = 1.0 if matched_blocks else 0.0
    ocr_score = sum(float(block.get("ocr_confidence", 0.0)) for block in matched_blocks) / len(matched_blocks) if matched_blocks else 0.0
    format_score = 1.0 if _format_is_valid(field_key, field_data) else 0.0
    proximity_score = _spatial_anchor_score(field_key, matched_blocks, ocr_blocks)
    return round((0.45 * ocr_score) + (0.20 * anchor_score) + (0.15 * format_score) + (0.20 * proximity_score), 2)


def process_extracted_data(ai_output, ocr_blocks):
    processed = {}
    for field_key in ("commodity_name", "net_quantity", "mfg_date", "mrp", "manufacturer"):
        field_data = (ai_output or {}).get(field_key) or {}
        processed[field_key] = {
            "field_key": field_key,
            "value": field_data.get("value"),
            "unit": field_data.get("unit"),
            "inclusive_of_taxes": field_data.get("inclusive_of_taxes"),
            "raw_source": field_data.get("raw_source", ""),
            "source_block_ids": _source_ids(field_data),
            "confidence": calculate_field_confidence(field_key, field_data, ocr_blocks),
        }
    return processed
