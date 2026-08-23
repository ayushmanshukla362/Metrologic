"""Experimental direct-image Gemini extraction for MetroLogic."""

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
)


DEFAULT_VISION_MODEL = "gemini-3.5-flash-lite"
DEFAULT_VISION_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
VISION_DOTENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=VISION_DOTENV_PATH)


class _VisionFieldBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bbox: list[StrictInt] | None = Field(min_length=4, max_length=4)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        x1, y1, x2, y2 = value
        if min(value) < 0:
            raise ValueError("bbox coordinates must be non-negative")
        if x1 > x2 or y1 > y2:
            raise ValueError("bbox coordinates must be ordered x1 <= x2 and y1 <= y2")
        return value


class _VisionTextField(_VisionFieldBase):
    value: StrictStr | None
    raw_source: StrictStr | None


class _VisionQuantityField(_VisionFieldBase):
    value: StrictInt | StrictFloat | None
    unit: StrictStr | None
    raw_source: StrictStr | None


class VisionExtraction(BaseModel):
    """Experimental image extraction output; it contains no legal decisions."""

    model_config = ConfigDict(extra="forbid")

    commodity_name: _VisionTextField
    net_quantity: _VisionQuantityField
    mfg_date: _VisionTextField
    mrp: _VisionQuantityField
    manufacturer: _VisionTextField

    @field_validator("mrp")
    @classmethod
    def normalize_mrp_unit(cls, value: _VisionQuantityField) -> _VisionQuantityField:
        if value.unit and value.unit.strip().casefold() in {"rs", "rs.", "₹", "inr"}:
            value.unit = "INR"
        return value


class VisionExtractionError(BaseModel):
    """Controlled failure returned by the experimental vision extractor."""

    model_config = ConfigDict(extra="forbid")

    error: Literal[
        "vision_configuration_error",
        "vision_authentication_error",
        "vision_http_error",
        "vision_timeout",
        "vision_network_error",
        "vision_malformed_response",
        "vision_schema_validation_error",
    ]
    message: StrictStr


VisionExtractionResult = VisionExtraction | VisionExtractionError


VISION_PROMPT = """Analyze this package image and extract only the five fields in the required JSON contract.
Never hallucinate. If a field is not clearly readable in the image, use null for its value,
raw_source, and bbox. raw_source must contain only visibly supported text. bbox must be an
approximate pixel box [x1, y1, x2, y2] for the visual evidence, or null.
Numeric values must be JSON numbers, not strings. Do not confuse batch numbers, FSSAI license
numbers, barcodes, phone numbers, or other numbers with MRP, dates, or quantity. Pay special
attention to visible labels such as Mfg. Date, Exp. Date, MRP, and currency symbols.
For manufacturer, include the complete visible manufacturer declaration when clearly readable.
Do not output confidence, PASS, FAIL, REVIEW_REQUIRED, or legal interpretation. Return JSON only.

Required JSON contract:
{
  "commodity_name": {"value": "string | null", "raw_source": "string | null", "bbox": [x1, y1, x2, y2] | null},
  "net_quantity": {"value": "number | null", "unit": "string | null", "raw_source": "string | null", "bbox": [x1, y1, x2, y2] | null},
  "mfg_date": {"value": "string | null", "raw_source": "string | null", "bbox": [x1, y1, x2, y2] | null},
  "mrp": {"value": "number | null", "unit": "string | null", "raw_source": "string | null", "bbox": [x1, y1, x2, y2] | null},
  "manufacturer": {"value": "string | null", "raw_source": "string | null", "bbox": [x1, y1, x2, y2] | null}
}
"""
VISION_RETRY_PROMPT = VISION_PROMPT + """

This is a schema-validation retry. For the named invalid bbox field(s), use exactly
[x1,y1,x2,y2], where x1 <= x2, y1 <= y2, and every coordinate is in the range 0..1000.
Do not guess bbox values. If visual evidence is unclear, return bbox: null.
Return the same JSON contract and do not repair values by inference.
"""


_MISSING = object()


def _payload_value(payload: Any, location: tuple[Any, ...]) -> Any:
    current = payload
    for part in location:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return _MISSING
    return current


def _sanitize_diagnostic_value(value: Any, api_key: str | None) -> Any:
    if value is _MISSING:
        return "<missing>"
    if isinstance(value, dict):
        sanitized = {}
        for key, item in list(value.items())[:8]:
            if str(key).casefold() in {
                "api_key",
                "authorization",
                "password",
                "secret",
                "token",
            }:
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_diagnostic_value(item, api_key)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_diagnostic_value(item, api_key) for item in value[:8]]
    if isinstance(value, str):
        sanitized = value.replace(api_key, "[REDACTED]") if api_key else value
        return sanitized[:160]
    return value


def _validation_diagnostic(
    error: ValidationError,
    payload: Any,
    api_key: str | None,
) -> str:
    invalid_fields = []
    for detail in error.errors()[:8]:
        location = tuple(detail.get("loc", ()))
        invalid_fields.append(
            {
                "field": ".".join(str(part) for part in location) or "<root>",
                "message": detail.get("msg", "validation failed"),
                "value": _sanitize_diagnostic_value(
                    _payload_value(payload, location), api_key
                ),
            }
        )
    return json.dumps(invalid_fields, ensure_ascii=False, separators=(",", ":"))


def _invalid_bbox_fields(error: ValidationError) -> list[str]:
    """Return deterministic field paths for bbox-specific schema failures."""
    fields: list[str] = []
    for detail in error.errors():
        location = tuple(detail.get("loc", ()))
        if not location or location[-1] != "bbox":
            continue
        field_path = ".".join(str(part) for part in location)
        if field_path not in fields:
            fields.append(field_path)
    return fields


def _retry_prompt(invalid_bbox_fields: list[str]) -> str:
    if not invalid_bbox_fields:
        return VISION_RETRY_PROMPT
    fields = ", ".join(invalid_bbox_fields)
    return VISION_RETRY_PROMPT + (
        f"\nThe following bbox field(s) failed validation and must be checked explicitly: {fields}."
        " Return the complete JSON object again, including every required field."
    )


def parse_vision_output(
    text: str,
    api_key: str | None = None,
) -> VisionExtractionResult:
    """Strictly parse the JSON text returned by Gemini Vision."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return VisionExtractionError(
            error="vision_malformed_response",
            message="Gemini Vision response was not valid JSON",
        )

    try:
        return VisionExtraction.model_validate(payload)
    except ValidationError as error:
        diagnostic = _validation_diagnostic(
            error,
            payload,
            api_key if api_key is not None else os.getenv("LLM_API_KEY"),
        )
        return VisionExtractionError(
            error="vision_schema_validation_error",
            message=(
                "Gemini Vision response failed schema validation; "
                f"invalid_fields={diagnostic}"
            ),
        )


def _image_mime_type(image_path: Path) -> str | None:
    suffix = image_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return None


def _safe_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))
    except ValueError:
        return "<redacted URL>"


@dataclass(frozen=True)
class VisionConfig:
    api_key: str
    model: str = DEFAULT_VISION_MODEL
    endpoint: str = ""

    @classmethod
    def from_environment(cls) -> "VisionConfig | VisionExtractionError":
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            return VisionExtractionError(
                error="vision_configuration_error",
                message="LLM_API_KEY environment variable is required",
            )
        model = os.getenv("VISION_MODEL") or DEFAULT_VISION_MODEL
        endpoint = os.getenv("VISION_ENDPOINT") or DEFAULT_VISION_ENDPOINT.format(
            model=model
        )
        return cls(api_key=api_key, model=model, endpoint=endpoint)


class VisionClient:
    """Minimal native Gemini GenerateContent client for isolated experiments."""

    def __init__(self, config: VisionConfig, timeout: float = 60.0):
        self.config = config
        self.timeout = timeout

    def _request_body(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str = VISION_PROMPT,
    ) -> dict[str, Any]:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }

    def generate(
        self,
        image_path: str | Path,
        prompt: str = VISION_PROMPT,
    ) -> str | VisionExtractionError:
        path = Path(image_path)
        mime_type = _image_mime_type(path)
        if mime_type is None:
            return VisionExtractionError(
                error="vision_configuration_error",
                message="Only JPEG and PNG images are supported",
            )

        try:
            image_bytes = path.read_bytes()
        except OSError:
            return VisionExtractionError(
                error="vision_configuration_error",
                message="Vision image could not be read",
            )

        try:
            response = httpx.post(
                self.config.endpoint,
                json=self._request_body(image_bytes, mime_type, prompt),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.config.api_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            error_type = (
                "vision_authentication_error"
                if status_code in {401, 403}
                else "vision_http_error"
            )
            return VisionExtractionError(
                error=error_type,
                message=(
                    f"Gemini Vision HTTP {status_code} from "
                    f"{_safe_url(str(error.response.request.url))}"
                ),
            )
        except httpx.TimeoutException:
            return VisionExtractionError(
                error="vision_timeout",
                message=(
                    "Gemini Vision request timed out at "
                    f"{_safe_url(self.config.endpoint)}"
                ),
            )
        except httpx.RequestError:
            return VisionExtractionError(
                error="vision_network_error",
                message=(
                    "Gemini Vision network request failed at "
                    f"{_safe_url(self.config.endpoint)}"
                ),
            )

        try:
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError):
            return VisionExtractionError(
                error="vision_malformed_response",
                message="Gemini Vision response had an unexpected shape",
            )
        if not isinstance(text, str):
            return VisionExtractionError(
                error="vision_malformed_response",
                message="Gemini Vision response content was not text",
            )
        return text

    def extract(self, image_path: str | Path) -> VisionExtractionResult:
        generated = self.generate(image_path)
        if isinstance(generated, VisionExtractionError):
            return generated
        try:
            first_payload = json.loads(generated)
        except json.JSONDecodeError:
            first_payload = None
        try:
            result = VisionExtraction.model_validate(first_payload)
        except (ValidationError, TypeError):
            result = parse_vision_output(generated, api_key=self.config.api_key)
        if not (
            isinstance(result, VisionExtractionError)
            and result.error == "vision_schema_validation_error"
        ):
            return result

        invalid_bbox_fields: list[str] = []
        try:
            VisionExtraction.model_validate(first_payload)
        except ValidationError as error:
            invalid_bbox_fields = _invalid_bbox_fields(error)

        retry_generated = self.generate(
            image_path, prompt=_retry_prompt(invalid_bbox_fields)
        )
        if isinstance(retry_generated, VisionExtractionError):
            return retry_generated
        return parse_vision_output(retry_generated, api_key=self.config.api_key)


def extract_image(image_path: str | Path) -> VisionExtractionResult:
    """Load configuration and perform one isolated direct-image extraction."""
    config = VisionConfig.from_environment()
    if isinstance(config, VisionExtractionError):
        return config
    return VisionClient(config).extract(image_path)
