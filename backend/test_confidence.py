from backend.ai_extractor import RawAIExtraction
from backend.confidence import (
    CONFIDENCE_THRESHOLD,
    calculate_field_confidence,
    process_extracted_data,
)


def _ocr_blocks():
    return [
        {
            "block_id": "img_front:b001",
            "text": "MRP",
            "bbox": [10, 10, 50, 20],
            "ocr_confidence": 100.0,
        },
        {
            "block_id": "img_front:b002",
            "text": "INR 50",
            "bbox": [70, 10, 60, 20],
            "ocr_confidence": 100.0,
        },
    ]


def _raw_output():
    return RawAIExtraction.model_validate(
        {
            "commodity_name": {
                "value": "Biscuits",
                "raw_source": "Biscuits",
                "source_block_ids": ["img_front:b001"],
            },
            "net_quantity": {
                "value": 200,
                "unit": "g",
                "raw_source": "200 g",
                "source_block_ids": ["img_front:b002"],
            },
            "mfg_date": {
                "value": "2026-01-15",
                "raw_source": "MFD 2026-01-15",
                "source_block_ids": [],
            },
            "mrp": {
                "value": 50,
                "unit": "INR",
                "raw_source": "INR 50",
                "source_block_ids": ["img_front:b002"],
            },
            "manufacturer": {
                "value": "Metro Foods",
                "raw_source": "Metro Foods",
                "source_block_ids": ["img_front:b001"],
            },
        }
    )


def test_confidence_is_deterministic_and_uses_native_bbox():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "INR 50",
        "source_block_ids": ["img_front:b002"],
    }

    first = calculate_field_confidence("mrp", field, _ocr_blocks())
    second = calculate_field_confidence("mrp", field, _ocr_blocks())

    assert first == second
    assert first == 1.0


def test_missing_value_or_evidence_produces_zero_confidence():
    assert calculate_field_confidence(
        "mfg_date",
        {"value": None, "source_block_ids": []},
        _ocr_blocks(),
    ) == 0.0
    assert calculate_field_confidence(
        "mrp",
        {"value": 50, "unit": "INR", "source_block_ids": []},
        _ocr_blocks(),
    ) == 0.15
    assert 0.15 < CONFIDENCE_THRESHOLD


def test_all_source_ids_valid_keep_normal_confidence():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "MRP INR 50",
        "source_block_ids": ["img_front:b001", "img_front:b002"],
    }

    assert calculate_field_confidence("mrp", field, _ocr_blocks()) == 1.0


def test_valid_and_dangling_source_ids_zero_confidence_and_preserved():
    source_ids = ["img_front:b002", "img_front:b999"]
    processed = process_extracted_data(
        {
            "mrp": {
                "value": 50,
                "unit": "INR",
                "raw_source": "INR 50",
                "source_block_ids": source_ids,
            }
        },
        _ocr_blocks(),
    )

    assert processed["mrp"]["confidence"] == 0.0
    assert processed["mrp"]["source_block_ids"] == source_ids


def test_valid_and_empty_source_id_zero_confidence_and_preserved():
    source_ids = ["img_front:b002", ""]
    processed = process_extracted_data(
        {
            "mrp": {
                "value": 50,
                "unit": "INR",
                "raw_source": "INR 50",
                "source_block_ids": source_ids,
            }
        },
        _ocr_blocks(),
    )

    assert processed["mrp"]["confidence"] == 0.0
    assert processed["mrp"]["source_block_ids"] == source_ids


def test_empty_source_id_zero_confidence():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "INR 50",
        "source_block_ids": [""],
    }

    assert calculate_field_confidence("mrp", field, _ocr_blocks()) == 0.0


def test_valid_and_none_source_id_zero_confidence():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "INR 50",
        "source_block_ids": ["img_front:b002", None],
    }

    assert calculate_field_confidence("mrp", field, _ocr_blocks()) == 0.0


def test_wrong_image_source_id_zero_confidence():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "INR 50",
        "source_block_ids": ["img_back:b002"],
    }

    assert calculate_field_confidence("mrp", field, _ocr_blocks()) == 0.0


def test_all_source_ids_invalid_zero_confidence():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "INR 50",
        "source_block_ids": ["img_back:b001", "img_back:b002"],
    }

    assert calculate_field_confidence("mrp", field, _ocr_blocks()) == 0.0


def test_invalid_evidence_confidence_is_below_review_threshold():
    field = {
        "value": 50,
        "unit": "INR",
        "raw_source": "INR 50",
        "source_block_ids": ["img_front:b999"],
    }

    confidence = calculate_field_confidence("mrp", field, _ocr_blocks())

    assert confidence < CONFIDENCE_THRESHOLD


def test_processed_output_matches_validated_field_shape():
    processed = process_extracted_data(_raw_output(), _ocr_blocks())

    assert set(processed) == {
        "commodity_name",
        "net_quantity",
        "mfg_date",
        "mrp",
        "manufacturer",
    }
    assert set(processed["mrp"]) == {
        "value",
        "unit",
        "raw_source",
        "source_block_ids",
        "confidence",
    }
    assert "field_key" not in processed["mrp"]
    assert "inclusive_of_taxes" not in processed["mrp"]
    assert processed["mrp"]["source_block_ids"] == ["img_front:b002"]
