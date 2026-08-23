import json
import os
from pathlib import Path

import httpx
import pytest
from PIL import Image

import backend.ai_extractor as ai_extractor
from backend.ai_extractor import (
    ExtractionError,
    LLMClient,
    LLMConfig,
    OCRBlock,
    RawAIExtraction,
    build_extraction_prompt,
    extract_ocr_blocks,
    group_ocr_blocks_into_lines,
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


def test_llm_config_loads_backend_dotenv_without_exposing_real_key(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_ENDPOINT", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    loaded_path = {}

    def fake_load_dotenv(dotenv_path):
        loaded_path["value"] = dotenv_path
        values = {
            "LLM_PROVIDER": "gemini",
            "LLM_ENDPOINT": "https://configured.example/ignored",
            "LLM_MODEL": "test-gemini-model",
            "LLM_API_KEY": "unit-test-key",
        }
        for name, value in values.items():
            if name not in os.environ:
                monkeypatch.setenv(name, value)
        return True

    monkeypatch.setattr(ai_extractor, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv("LLM_MODEL", "explicit-model")

    ai_extractor._load_llm_environment()
    config = LLMConfig.from_environment()

    assert loaded_path["value"] == Path(ai_extractor.__file__).resolve().parent / ".env"
    assert config.provider == "gemini"
    assert config.endpoint == "https://configured.example/ignored"
    assert config.model == "explicit-model"
    assert config.api_key == "unit-test-key"


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


def _noisy_ocr_data():
    return {
        "text": ["80006", "00"],
        "conf": ["91", "88"],
        "left": [20, 90],
        "top": [30, 30],
        "width": [50, 30],
        "height": [20, 20],
    }


def _secondary_ocr_data():
    return {
        "text": ["MRP 80006"],
        "conf": ["96"],
        "left": [40],
        "top": [60],
        "width": [100],
        "height": [40],
    }


def test_secondary_preprocessing_preserves_original_ocr_blocks(monkeypatch):
    calls = []

    def fake_image_to_data(image, output_type, config=None):
        calls.append(config)
        return _noisy_ocr_data() if config is None else {"text": []}

    monkeypatch.setattr(
        "backend.ai_extractor.pytesseract.image_to_data", fake_image_to_data
    )
    image = Image.new("RGB", (200, 100), "white")

    blocks = extract_ocr_blocks(image, "img_label")

    assert calls == [None, "--psm 6", "--psm 11"]
    assert [block.model_dump() for block in blocks] == [
        {
            "block_id": "img_label:b001",
            "text": "80006",
            "bbox": [20, 30, 50, 20],
            "ocr_confidence": 91.0,
            "normalized_x1": 0.1,
            "normalized_y1": 0.3,
            "normalized_x2": 0.35,
            "normalized_y2": 0.5,
        },
        {
            "block_id": "img_label:b002",
            "text": "00",
            "bbox": [90, 30, 30, 20],
            "ocr_confidence": 88.0,
            "normalized_x1": 0.45,
            "normalized_y1": 0.3,
            "normalized_x2": 0.6,
            "normalized_y2": 0.5,
        },
    ]


def test_secondary_ocr_produces_valid_native_space_blocks(monkeypatch):
    def fake_image_to_data(image, output_type, config=None):
        if config is None:
            return _noisy_ocr_data()
        return _secondary_ocr_data() if config == "--psm 6" else _secondary_ocr_data()

    monkeypatch.setattr(
        "backend.ai_extractor.pytesseract.image_to_data", fake_image_to_data
    )
    image = Image.new("RGB", (200, 100), "white")

    blocks = extract_ocr_blocks(image, "img_label")
    secondary = blocks[-1]

    assert secondary.text == "MRP 80006"
    assert secondary.bbox == [20, 30, 50, 20]
    assert secondary.ocr_confidence == 96.0
    assert 0 <= secondary.normalized_x1 <= secondary.normalized_x2 <= 1
    assert 0 <= secondary.normalized_y1 <= secondary.normalized_y2 <= 1


def test_secondary_block_ids_are_deterministic(monkeypatch):
    def fake_image_to_data(image, output_type, config=None):
        if config is None:
            return _noisy_ocr_data()
        return _secondary_ocr_data()

    monkeypatch.setattr(
        "backend.ai_extractor.pytesseract.image_to_data", fake_image_to_data
    )
    image = Image.new("RGB", (200, 100), "white")

    first = extract_ocr_blocks(image, "img_label")
    second = extract_ocr_blocks(image, "img_label")

    assert [block.block_id for block in first] == [
        "img_label:b001",
        "img_label:b002",
        "img_label:b003",
    ]
    assert [block.block_id for block in second] == [block.block_id for block in first]


def test_overlapping_duplicate_secondary_result_is_not_added():
    original = [_ocr_block("img_label:b001", "MRP", 20, 30, 50, 20)]
    duplicate = [_ocr_block("img_label:secondary1:001", "MRP", 20, 30, 50, 20)]

    merged = ai_extractor._merge_secondary_ocr_blocks(
        original, duplicate, "img_label"
    )

    assert len(merged) == 1
    assert merged[0].block_id == "img_label:b001"
    assert merged[0].text == "MRP"


def test_overlapping_conflicting_secondary_result_is_not_added():
    original = [_ocr_block("img_label:b001", "MRP", 20, 30, 50, 20)]
    conflicting = [_ocr_block("img_label:secondary1:001", "EXP", 20, 30, 50, 20)]

    merged = ai_extractor._merge_secondary_ocr_blocks(
        original, conflicting, "img_label"
    )

    assert [block.block_id for block in merged] == ["img_label:b001"]


def _ocr_block(block_id, text, x, y, width=40, height=20):
    return OCRBlock(
        block_id=block_id,
        text=text,
        bbox=[x, y, width, height],
        ocr_confidence=95.0,
        normalized_x1=x / 400,
        normalized_y1=y / 200,
        normalized_x2=(x + width) / 400,
        normalized_y2=(y + height) / 200,
    )


def test_words_on_same_visual_line_are_grouped_with_original_text():
    blocks = [
        _ocr_block("img_back:b001", "Manufactured", 10, 20),
        _ocr_block("img_back:b002", "By", 60, 20, width=20),
        _ocr_block("img_back:b003", ":", 90, 20, width=10),
        _ocr_block("img_back:b004", "Spectacle Foods,", 110, 20, width=120),
    ]

    lines = group_ocr_blocks_into_lines(blocks)

    assert lines == [
        {
            "text": "Manufactured By : Spectacle Foods,",
            "source_block_ids": [
                "img_back:b001",
                "img_back:b002",
                "img_back:b003",
                "img_back:b004",
            ],
        }
    ]


def test_words_on_different_visual_lines_stay_separate():
    blocks = [
        _ocr_block("img_back:b001", "Manufactured", 10, 20),
        _ocr_block("img_back:b002", "By", 60, 20, width=20),
        _ocr_block("img_back:b003", "Dhanwada,", 10, 60),
        _ocr_block("img_back:b004", "Gujarat,", 80, 60),
    ]

    lines = group_ocr_blocks_into_lines(blocks)

    assert [line["text"] for line in lines] == [
        "Manufactured By",
        "Dhanwada, Gujarat,",
    ]


def test_line_grouping_preserves_all_contributing_block_ids_and_text():
    blocks = [
        _ocr_block("img_back:b002", "Sub", 40, 40),
        _ocr_block("img_back:b001", "Plot", 10, 40),
        _ocr_block("img_back:b003", "no.13,14/3,", 80, 40),
    ]

    line = group_ocr_blocks_into_lines(blocks)[0]

    assert line["source_block_ids"] == [
        "img_back:b001",
        "img_back:b002",
        "img_back:b003",
    ]
    assert line["text"] == "Plot Sub no.13,14/3,"
    assert all(block.text in line["text"] for block in blocks)


def test_prompt_uses_grouped_lines_and_preserves_block_ids():
    blocks = [
        _ocr_block("img_back:b001", "Manufactured", 10, 20),
        _ocr_block("img_back:b002", "By", 60, 20, width=20),
    ]

    prompt = build_extraction_prompt(blocks)

    assert "OCR lines:" in prompt
    assert "Manufactured By" in prompt
    assert "img_back:b001" in prompt
    assert "img_back:b002" in prompt


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


def _gemini_client():
    return LLMClient(
        LLMConfig(
            provider="gemini",
            endpoint="https://configured.example/ignored",
            model="configured-gemini-model",
            api_key="test-key",
        )
    )


def test_gemini_request_uses_chat_completions_shape(monkeypatch):
    captured = {}

    def fake_post(endpoint, **kwargs):
        captured["endpoint"] = endpoint
        captured["kwargs"] = kwargs
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
            request=httpx.Request("POST", endpoint),
        )

    monkeypatch.setattr("backend.ai_extractor.httpx.post", fake_post)
    prompt = build_extraction_prompt([])

    assert _gemini_client().generate(prompt) == "ok"
    assert captured["endpoint"] == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    assert captured["kwargs"]["json"] == {
        "model": "configured-gemini-model",
        "messages": [{"role": "user", "content": prompt}],
    }
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer test-key"}


def test_gemini_response_content_is_validated_as_raw_extraction(monkeypatch):
    raw_json = json.dumps(_clean_payload())

    monkeypatch.setattr(
        "backend.ai_extractor.httpx.post",
        lambda endpoint, **kwargs: httpx.Response(
            200,
            json={"choices": [{"message": {"content": raw_json}}]},
            request=httpx.Request("POST", endpoint),
        ),
    )

    result = _gemini_client().extract([])

    assert isinstance(result, RawAIExtraction)
    assert result.mrp.value == 50


@pytest.mark.parametrize("status_code", [400, 401, 404, 429, 503])
def test_llm_http_errors_are_safe_and_diagnostic(monkeypatch, status_code):
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )

    def fake_post(endpoint, **kwargs):
        request = httpx.Request("POST", endpoint)
        return httpx.Response(
            status_code,
            text=(
                '{"error":"request failed","api_key":"test-key",'
                '"authorization":"Bearer test-key"}'
            ),
            request=request,
        )

    monkeypatch.setattr("backend.ai_extractor.httpx.post", fake_post)

    result = _gemini_client().extract([])

    assert isinstance(result, ExtractionError)
    assert result.error == "llm_request_error"
    assert result.message.startswith(f"HTTP {status_code} from {endpoint}: ")
    assert "[REDACTED]" in result.message
    assert "test-key" not in result.message
    assert "Bearer" not in result.message
    assert "Authorization" not in result.message


def test_llm_timeout_returns_controlled_error(monkeypatch):
    def fake_post(endpoint, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("backend.ai_extractor.httpx.post", fake_post)

    result = _gemini_client().extract([])

    assert isinstance(result, ExtractionError)
    assert result.error == "llm_request_error"
    assert "timeout" in result.message.lower()
    assert "generativelanguage.googleapis.com" in result.message


def test_llm_transport_error_is_distinguished(monkeypatch):
    def fake_post(endpoint, **kwargs):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr("backend.ai_extractor.httpx.post", fake_post)

    result = _gemini_client().extract([])

    assert isinstance(result, ExtractionError)
    assert result.error == "llm_request_error"
    assert "network/transport" in result.message
    assert "generativelanguage.googleapis.com" in result.message


def test_invalid_gemini_response_shape_is_controlled(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_extractor.httpx.post",
        lambda endpoint, **kwargs: httpx.Response(
            200,
            json={"choices": []},
            request=httpx.Request("POST", endpoint),
        ),
    )

    result = _gemini_client().extract([])

    assert isinstance(result, ExtractionError)
    assert result.error == "schema_validation_error"


def test_generic_response_keys_remain_supported(monkeypatch):
    for key in ("text", "output", "response"):
        monkeypatch.setattr(
            "backend.ai_extractor.httpx.post",
            lambda endpoint, key=key, **kwargs: httpx.Response(
                200,
                json={key: "generic response"},
                request=httpx.Request("POST", endpoint),
            ),
        )

        assert _gemini_client().generate("prompt") == "generic response"
