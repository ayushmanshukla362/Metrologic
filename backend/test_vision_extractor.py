import base64
import json
from pathlib import Path

import httpx

from backend.vision_extractor import (
    DEFAULT_VISION_MODEL,
    VISION_PROMPT,
    VISION_RETRY_PROMPT,
    VisionClient,
    VisionConfig,
    VisionExtraction,
    VisionExtractionError,
    parse_vision_output,
)


def _client():
    return VisionClient(
        VisionConfig(
            api_key="test-api-key",
            model=DEFAULT_VISION_MODEL,
            endpoint=(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{DEFAULT_VISION_MODEL}:generateContent"
            ),
        )
    )


def _image(monkeypatch, suffix=".png", image_bytes=b"test-image-bytes"):
    path = Path(f"package{suffix}")
    monkeypatch.setattr(Path, "read_bytes", lambda self: image_bytes)
    return path


def _vision_payload():
    return {
        "commodity_name": {
            "value": "Biscuits",
            "raw_source": "Biscuits",
            "bbox": [10, 20, 100, 45],
        },
        "net_quantity": {
            "value": 200,
            "unit": "g",
            "raw_source": "200 g",
            "bbox": [10, 50, 90, 75],
        },
        "mfg_date": {
            "value": "2026-01-15",
            "raw_source": "Mfg. Date: 2026-01-15",
            "bbox": [10, 80, 180, 105],
        },
        "mrp": {
            "value": 50,
            "unit": "INR",
            "raw_source": "MRP Rs. 50",
            "bbox": [10, 110, 130, 135],
        },
        "manufacturer": {
            "value": "Metro Foods",
            "raw_source": "Manufactured by Metro Foods",
            "bbox": [10, 140, 220, 175],
        },
    }


def _response(endpoint, text, status_code=200):
    return httpx.Response(
        status_code,
        json={"candidates": [{"content": {"parts": [{"text": text}]}}]},
        request=httpx.Request("POST", endpoint),
    )


def test_native_multimodal_request_has_model_prompt_and_encoded_image(monkeypatch):
    captured = {}
    image_bytes = b"jpeg-or-png-bytes"
    image_path = _image(monkeypatch, image_bytes=image_bytes)

    def fake_post(endpoint, **kwargs):
        captured["endpoint"] = endpoint
        captured["kwargs"] = kwargs
        return _response(endpoint, json.dumps(_vision_payload()))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)

    result = _client().extract(image_path)

    assert isinstance(result, VisionExtraction)
    assert captured["endpoint"].endswith(f"/{DEFAULT_VISION_MODEL}:generateContent")
    body = captured["kwargs"]["json"]
    part = body["contents"][0]["parts"]
    assert body["contents"][0]["role"] == "user"
    assert part[0]["text"] == VISION_PROMPT
    assert part[1]["inline_data"]["mime_type"] == "image/png"
    assert part[1]["inline_data"]["data"] == base64.b64encode(image_bytes).decode()
    assert captured["kwargs"]["headers"]["x-goog-api-key"] == "test-api-key"


def test_native_request_uses_configured_model_and_endpoint(monkeypatch):
    captured = {}
    custom_endpoint = "https://vision.example/generateContent"
    client = VisionClient(
        VisionConfig(api_key="test-api-key", model="custom-model", endpoint=custom_endpoint)
    )

    def fake_post(endpoint, **kwargs):
        captured["endpoint"] = endpoint
        captured["body"] = kwargs["json"]
        return _response(endpoint, json.dumps(_vision_payload()))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)

    result = client.extract(_image(monkeypatch, ".jpg"))

    assert isinstance(result, VisionExtraction)
    assert captured["endpoint"] == custom_endpoint
    assert captured["body"]["generationConfig"] == {
        "responseMimeType": "application/json"
    }


def test_successful_response_is_strictly_validated(monkeypatch):
    monkeypatch.setattr(
        "backend.vision_extractor.httpx.post",
        lambda endpoint, **kwargs: _response(endpoint, json.dumps(_vision_payload())),
    )

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtraction)
    assert result.mrp.value == 50
    assert result.net_quantity.unit == "g"


def test_valid_first_response_makes_exactly_one_request(monkeypatch):
    calls = []

    def fake_post(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return _response(endpoint, json.dumps(_vision_payload()))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtraction)
    assert len(calls) == 1
    assert calls[0][1]["json"]["contents"][0]["parts"][0]["text"] == VISION_PROMPT


def test_invalid_first_bbox_valid_retry_returns_success(monkeypatch):
    invalid_payload = _vision_payload()
    invalid_bbox = [902, 395, 579, 845]
    invalid_payload["mrp"]["bbox"] = invalid_bbox.copy()
    responses = [
        json.dumps(invalid_payload),
        json.dumps(_vision_payload()),
    ]
    calls = []

    def fake_post(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return _response(endpoint, responses.pop(0))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)
    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtraction)
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert calls[0][1]["json"]["contents"][0]["parts"][1] == calls[1][1]["json"]["contents"][0]["parts"][1]
    retry_prompt = calls[1][1]["json"]["contents"][0]["parts"][0]["text"]
    assert retry_prompt.startswith(VISION_RETRY_PROMPT)
    assert "mrp.bbox" in retry_prompt
    assert "x1 <= x2" in retry_prompt
    assert "y1 <= y2" in retry_prompt
    assert "0..1000" in retry_prompt
    assert "bbox: null" in retry_prompt
    assert '"commodity_name"' in retry_prompt
    assert invalid_payload["mrp"]["bbox"] == invalid_bbox
    assert result.mrp.value == 50
    assert result.mrp.raw_source == "MRP Rs. 50"


def test_invalid_mrp_bbox_null_retry_returns_success_without_losing_value(monkeypatch):
    invalid_payload = _vision_payload()
    invalid_bbox = [933, 395, 593, 446]
    invalid_payload["mrp"]["bbox"] = invalid_bbox.copy()
    retry_payload = _vision_payload()
    retry_payload["mrp"]["bbox"] = None
    responses = [json.dumps(invalid_payload), json.dumps(retry_payload)]
    calls = []

    def fake_post(endpoint, **kwargs):
        calls.append(kwargs)
        return _response(endpoint, responses.pop(0))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)
    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtraction)
    assert len(calls) == 2
    assert result.mrp.value == 50
    assert result.mrp.raw_source == "MRP Rs. 50"
    assert result.mrp.bbox is None
    assert "mrp.bbox" in calls[1]["json"]["contents"][0]["parts"][0]["text"]
    assert invalid_payload["mrp"]["bbox"] == invalid_bbox


def test_retry_prompt_does_not_expose_api_key(monkeypatch):
    invalid_payload = _vision_payload()
    invalid_payload["mrp"]["bbox"] = [933, 395, 593, 446]
    responses = [json.dumps(invalid_payload), json.dumps(_vision_payload())]
    calls = []

    def fake_post(endpoint, **kwargs):
        calls.append(kwargs)
        return _response(endpoint, responses.pop(0))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)
    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtraction)
    retry_prompt = calls[1]["json"]["contents"][0]["parts"][0]["text"]
    assert "test-api-key" not in retry_prompt


def test_invalid_first_bbox_invalid_retry_returns_schema_error(monkeypatch):
    invalid_payload = _vision_payload()
    invalid_payload["mrp"]["bbox"] = [902, 395, 579, 845]
    responses = [json.dumps(invalid_payload), json.dumps(invalid_payload)]
    calls = []

    def fake_post(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return _response(endpoint, responses.pop(0))

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)
    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"
    assert len(calls) == 2
    assert "mrp.bbox" in result.message
    assert "[902,395,579,845]" in result.message


def test_malformed_json_is_controlled(monkeypatch):
    monkeypatch.setattr(
        "backend.vision_extractor.httpx.post",
        lambda endpoint, **kwargs: _response(endpoint, "not json"),
    )

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_malformed_response"


def test_schema_validation_failure_is_controlled(monkeypatch):
    payload = _vision_payload()
    del payload["mrp"]
    monkeypatch.setattr(
        "backend.vision_extractor.httpx.post",
        lambda endpoint, **kwargs: _response(endpoint, json.dumps(payload)),
    )

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"


def test_schema_validation_reports_field_and_sanitized_offending_value():
    payload = _vision_payload()
    payload["mrp"]["bbox"] = [902, 395, 579, 845]
    payload["mrp"]["raw_source"] = "test-api-key"

    result = parse_vision_output(json.dumps(payload), api_key="test-api-key")

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"
    assert "mrp.bbox" in result.message
    assert "[902,395,579,845]" in result.message
    assert "test-api-key" not in result.message


def test_http_401_does_not_expose_api_key(monkeypatch):
    def fake_post(endpoint, **kwargs):
        return httpx.Response(
            401,
            text='{"error":"invalid key"}',
            request=httpx.Request("POST", endpoint),
        )

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_authentication_error"
    assert "test-api-key" not in result.message
    assert "x-goog-api-key" not in result.message


def test_http_400_is_controlled_without_credentials(monkeypatch):
    def fake_post(endpoint, **kwargs):
        return httpx.Response(
            400,
            text='{"error":"bad request"}',
            request=httpx.Request("POST", endpoint),
        )

    monkeypatch.setattr("backend.vision_extractor.httpx.post", fake_post)

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_http_error"
    assert "400" in result.message
    assert "test-api-key" not in result.message


def test_timeout_is_controlled(monkeypatch):
    monkeypatch.setattr(
        "backend.vision_extractor.httpx.post",
        lambda endpoint, **kwargs: (_ for _ in ()).throw(
            httpx.TimeoutException("timed out")
        ),
    )

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_timeout"
    assert "test-api-key" not in result.message


def test_invalid_bbox_is_rejected(monkeypatch):
    payload = _vision_payload()
    payload["mrp"]["bbox"] = [1, 2, 3]
    monkeypatch.setattr(
        "backend.vision_extractor.httpx.post",
        lambda endpoint, **kwargs: _response(endpoint, json.dumps(payload)),
    )

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"


def test_bbox_x1_greater_than_x2_is_rejected():
    payload = _vision_payload()
    payload["mrp"]["bbox"] = [90, 10, 20, 40]

    result = parse_vision_output(json.dumps(payload))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"


def test_bbox_y1_greater_than_y2_is_rejected():
    payload = _vision_payload()
    payload["mrp"]["bbox"] = [10, 90, 20, 40]

    result = parse_vision_output(json.dumps(payload))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"


def test_bbox_negative_coordinate_is_rejected():
    payload = _vision_payload()
    payload["mrp"]["bbox"] = [-1, 10, 20, 40]

    result = parse_vision_output(json.dumps(payload))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"


def test_correct_bbox_is_accepted():
    payload = _vision_payload()
    payload["mrp"]["bbox"] = [10, 20, 90, 100]

    result = parse_vision_output(json.dumps(payload))

    assert isinstance(result, VisionExtraction)
    assert result.mrp.bbox == [10, 20, 90, 100]


def test_mrp_rs_unit_is_normalized_to_inr():
    payload = _vision_payload()
    payload["mrp"]["unit"] = "Rs"

    result = parse_vision_output(json.dumps(payload))

    assert isinstance(result, VisionExtraction)
    assert result.mrp.unit == "INR"


def test_extra_unexpected_field_is_rejected(monkeypatch):
    payload = _vision_payload()
    payload["mrp"]["confidence"] = 0.99
    monkeypatch.setattr(
        "backend.vision_extractor.httpx.post",
        lambda endpoint, **kwargs: _response(endpoint, json.dumps(payload)),
    )

    result = _client().extract(_image(monkeypatch))

    assert isinstance(result, VisionExtractionError)
    assert result.error == "vision_schema_validation_error"
