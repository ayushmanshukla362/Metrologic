"""Standalone OCR-to-raw-AI-extraction bridge for MetroLogic Phase 3B."""

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
import pytesseract
from PIL import Image
from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, StrictStr, ValidationError
from pytesseract import Output


class OCRBlock(BaseModel):
    """A native-pixel OCR block supplied to the LLM."""

    model_config = ConfigDict(extra="forbid")

    block_id: StrictStr
    text: StrictStr
    bbox: list[StrictInt]
    ocr_confidence: StrictFloat
    normalized_x1: StrictFloat
    normalized_y1: StrictFloat
    normalized_x2: StrictFloat
    normalized_y2: StrictFloat


class _RawField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_source: StrictStr | None
    source_block_ids: list[StrictStr]


class RawCommodityField(_RawField):
    value: StrictStr | None


class RawQuantityField(_RawField):
    value: StrictInt | StrictFloat | None
    unit: StrictStr | None


class RawDateField(_RawField):
    value: StrictStr | None


class RawMRPField(_RawField):
    value: StrictInt | StrictFloat | None
    unit: StrictStr | None


class RawManufacturerField(_RawField):
    value: StrictStr | None


class RawAIExtraction(BaseModel):
    """The exact raw AI output contract; no confidence or legal status fields."""

    model_config = ConfigDict(extra="forbid")

    commodity_name: RawCommodityField
    net_quantity: RawQuantityField
    mfg_date: RawDateField
    mrp: RawMRPField
    manufacturer: RawManufacturerField


class ExtractionError(BaseModel):
    """Controlled error returned when an LLM response cannot be accepted."""

    error: Literal[
        "invalid_json",
        "schema_validation_error",
        "llm_configuration_error",
        "llm_request_error",
    ]
    message: StrictStr


ExtractionResult = RawAIExtraction | ExtractionError


def _as_int(value: Any) -> int:
    return int(value)


def extract_ocr_blocks(image: Any, image_id: str) -> list[OCRBlock]:
    """Extract valid OCR entries with deterministic IDs and native pixel boxes."""
    configured_tesseract_cmd = os.getenv("TESSERACT_CMD")
    if configured_tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = configured_tesseract_cmd
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    blocks: list[OCRBlock] = []
    image_width, image_height = image.size

    for index in range(len(data.get("text", []))):
        raw_text = data["text"][index]
        text = str(raw_text).strip()
        if not text:
            continue

        try:
            confidence = float(data["conf"][index])
            if not math.isfinite(confidence) or confidence < 0:
                continue
            bbox = [
                _as_int(data["left"][index]),
                _as_int(data["top"][index]),
                _as_int(data["width"][index]),
                _as_int(data["height"][index]),
            ]
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            continue

        blocks.append(
            OCRBlock(
                block_id=f"{image_id}:b{len(blocks) + 1:03d}",
                text=text,
                bbox=bbox,
                ocr_confidence=confidence,
                normalized_x1=bbox[0] / image_width,
                normalized_y1=bbox[1] / image_height,
                normalized_x2=(bbox[0] + bbox[2]) / image_width,
                normalized_y2=(bbox[1] + bbox[3]) / image_height,
            )
        )

    return blocks


def build_extraction_prompt(blocks: list[OCRBlock]) -> str:
    """Build the provider-neutral extraction prompt and OCR input."""
    contract = {
        "commodity_name": {
            "value": "string | null",
            "raw_source": "string | null",
            "source_block_ids": ["string"],
        },
        "net_quantity": {
            "value": "number | null",
            "unit": "string | null",
            "raw_source": "string | null",
            "source_block_ids": ["string"],
        },
        "mfg_date": {
            "value": "string | null",
            "raw_source": "string | null",
            "source_block_ids": ["string"],
        },
        "mrp": {
            "value": "number | null",
            "unit": "string | null",
            "raw_source": "string | null",
            "source_block_ids": ["string"],
        },
        "manufacturer": {
            "value": "string | null",
            "raw_source": "string | null",
            "source_block_ids": ["string"],
        },
    }
    block_json = json.dumps([block.model_dump() for block in blocks], ensure_ascii=False)
    return (
        "Extract only information explicitly supported by the OCR blocks. "
        "Never hallucinate missing values. For a missing field, use value null, "
        "raw_source null, and source_block_ids []. Numeric fields must be actual "
        "JSON numbers, not strings. net_quantity.unit must contain the unit only. "
        "Normalize mrp.unit to INR when the OCR detects INR, Rs, Rs., or the rupee "
        "symbol. Preserve the exact supporting OCR text in raw_source. Use only "
        "source block IDs supplied in the OCR input, including all contributing IDs "
        "when a field spans multiple blocks. Return JSON only. Do not output "
        "confidence, PASS, FAIL, REVIEW_REQUIRED, or legal interpretation.\n\n"
        f"Required JSON contract:\n{json.dumps(contract, indent=2)}\n\n"
        f"OCR blocks:\n{block_json}"
    )


def _extract_json_object(text: str) -> str | None:
    """Extract the first balanced JSON object without repairing its contents."""
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_raw_ai_output(text: str) -> ExtractionResult:
    """Parse, then strictly validate, a model response against the raw contract."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        candidate = _extract_json_object(text)
        if candidate is None:
            return ExtractionError(
                error="invalid_json",
                message="LLM response did not contain a valid JSON object",
            )
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return ExtractionError(
                error="invalid_json",
                message="LLM response contained an invalid JSON object",
            )

    try:
        return RawAIExtraction.model_validate(payload)
    except ValidationError:
        return ExtractionError(
            error="schema_validation_error",
            message="LLM response failed raw extraction schema validation",
        )


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    endpoint: str
    model: str
    api_key: str | None = None

    @classmethod
    def from_environment(cls) -> "LLMConfig | ExtractionError":
        missing = [
            name
            for name in ("LLM_PROVIDER", "LLM_ENDPOINT", "LLM_MODEL")
            if not os.getenv(name)
        ]
        if missing:
            return ExtractionError(
                error="llm_configuration_error",
                message="Missing LLM configuration: " + ", ".join(missing),
            )
        return cls(
            provider=os.environ["LLM_PROVIDER"],
            endpoint=os.environ["LLM_ENDPOINT"],
            model=os.environ["LLM_MODEL"],
            api_key=os.getenv("LLM_API_KEY"),
        )


class LLMClient:
    """Provider-neutral HTTP client for an endpoint that accepts prompt text."""

    def __init__(self, config: LLMConfig, timeout: float = 60.0):
        self.config = config
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        response = httpx.post(
            self.config.endpoint,
            json={"model": self.config.model, "prompt": prompt},
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            for key in ("text", "output", "response"):
                if isinstance(payload.get(key), str):
                    return payload[key]
        return response.text

    def extract(self, blocks: list[OCRBlock]) -> ExtractionResult:
        try:
            return parse_raw_ai_output(self.generate(build_extraction_prompt(blocks)))
        except httpx.HTTPError:
            return ExtractionError(
                error="llm_request_error",
                message="LLM request failed",
            )


def extract_image(
    image_path: str | Path,
    image_id: str,
    llm_client: LLMClient | None = None,
) -> tuple[list[OCRBlock], ExtractionResult | None]:
    """Load an image, run OCR, and optionally request validated raw extraction."""
    with Image.open(image_path) as image:
        blocks = extract_ocr_blocks(image, image_id)
    if llm_client is None:
        return blocks, None
    return blocks, llm_client.extract(blocks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MetroLogic OCR extraction")
    parser.add_argument("image_path", type=Path)
    args = parser.parse_args(argv)

    image_id = args.image_path.stem
    try:
        blocks, _ = extract_image(args.image_path, image_id)
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"error": "ocr_error", "message": str(error)}))
        return 1

    print(json.dumps([block.model_dump() for block in blocks], indent=2))
    config = LLMConfig.from_environment()
    if isinstance(config, ExtractionError):
        print(config.model_dump_json(indent=2))
        return 0

    extraction = LLMClient(config).extract(blocks)
    print(extraction.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
