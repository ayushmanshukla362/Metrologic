import json

from backend.ai_extractor import (
    ExtractionError,
    RawAIExtraction,
    extract_ocr_blocks,
    parse_raw_ai_output,
)


def _clean_payload():
    return {
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
            "raw_source": "MFD: 2026-01-15",
            "source_block_ids": ["img_back:b001"],
        },
        "mrp": {
            "value": 50,
            "unit": "INR",
            "raw_source": "MRP Rs. 50",
            "source_block_ids": ["img_back:b002"],
        },
        "manufacturer": {
            "value": "Metro Foods",
            "raw_source": "Metro Foods",
            "source_block_ids": ["img_back:b003"],
        },
    }


def test_ocr_block_formatting(monkeypatch):
    data = {
        "text": ["", "Biscuits", "unusable"],
        "conf": ["-1", "94.0", "-1"],
        "left": [0, "12", 20],
        "top": [0, "24", 30],
        "width": [0, "100", 40],
        "height": [0, "25", 10],
    }
    monkeypatch.setattr(
        "backend.ai_extractor.pytesseract.image_to_data",
        lambda image, output_type: data,
    )

    image = type("Image", (), {"size": (200, 100)})()
    blocks = extract_ocr_blocks(image, "img_front")

    assert [block.model_dump() for block in blocks] == [
        {
            "block_id": "img_front:b001",
            "text": "Biscuits",
            "bbox": [12, 24, 100, 25],
            "ocr_confidence": 94.0,
            "normalized_x1": 0.06,
            "normalized_y1": 0.24,
            "normalized_x2": 0.56,
            "normalized_y2": 0.49,
        }
    ]


def test_deterministic_block_ids(monkeypatch):
    data = {
        "text": ["One", "Two"],
        "conf": ["90", "91"],
        "left": [1, 2],
        "top": [3, 4],
        "width": [5, 6],
        "height": [7, 8],
    }
    monkeypatch.setattr(
        "backend.ai_extractor.pytesseract.image_to_data",
        lambda image, output_type: data,
    )

    image = type("Image", (), {"size": (100, 100)})()
    blocks = extract_ocr_blocks(image, "img_front")

    assert [block.block_id for block in blocks] == [
        "img_front:b001",
        "img_front:b002",
    ]


def test_valid_clean_llm_json():
    result = parse_raw_ai_output(json.dumps(_clean_payload()))

    assert isinstance(result, RawAIExtraction)
    assert result.mrp.value == 50
    assert result.net_quantity.unit == "g"


def test_missing_mrp_and_mfg_date_are_nullable():
    payload = _clean_payload()
    payload["mrp"] = {
        "value": None,
        "unit": None,
        "raw_source": None,
        "source_block_ids": [],
    }
    payload["mfg_date"] = {
        "value": None,
        "raw_source": None,
        "source_block_ids": [],
    }

    result = parse_raw_ai_output(json.dumps(payload))

    assert isinstance(result, RawAIExtraction)
    assert result.mrp.value is None
    assert result.mfg_date.value is None


def test_numeric_mrp_and_quantity_types():
    result = parse_raw_ai_output(json.dumps(_clean_payload()))

    assert isinstance(result, RawAIExtraction)
    assert type(result.mrp.value) is int
    assert type(result.net_quantity.value) is int


def test_invalid_llm_json_returns_controlled_error():
    result = parse_raw_ai_output("not JSON")

    assert isinstance(result, ExtractionError)
    assert result.error == "invalid_json"


def test_markdown_fenced_json_is_parsed():
    result = parse_raw_ai_output(
        "```json\n" + json.dumps(_clean_payload()) + "\n```"
    )

    assert isinstance(result, RawAIExtraction)


def test_invalid_schema_is_rejected():
    payload = _clean_payload()
    payload["mrp"]["value"] = "50"
    payload["mrp"]["confidence"] = 0.95

    result = parse_raw_ai_output(json.dumps(payload))

    assert isinstance(result, ExtractionError)
    assert result.error == "schema_validation_error"


def test_multiple_source_block_ids_are_preserved():
    payload = _clean_payload()
    payload["commodity_name"]["source_block_ids"] = [
        "img_front:b001",
        "img_front:b002",
    ]

    result = parse_raw_ai_output(json.dumps(payload))

    assert isinstance(result, RawAIExtraction)
    assert result.commodity_name.source_block_ids == [
        "img_front:b001",
        "img_front:b002",
    ]
