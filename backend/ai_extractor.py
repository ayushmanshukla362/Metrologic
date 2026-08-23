"""Standalone OCR-to-raw-AI-extraction bridge for MetroLogic Phase 3B."""

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytesseract
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
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
GEMINI_CHAT_COMPLETIONS_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
)
LLM_DOTENV_PATH = Path(__file__).resolve().parent / ".env"
_SENSITIVE_BODY_VALUE = re.compile(
    r"(?i)\"?(?:authorization|api[-_ ]?key|access[-_ ]?token|"
    r"refresh[-_ ]?token|token|secret|password)\"?\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,}]+)"
)
_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _load_llm_environment() -> None:
    """Load local LLM settings without overriding explicit environment values."""
    load_dotenv(dotenv_path=LLM_DOTENV_PATH)


_load_llm_environment()


def _safe_request_url(url: str) -> str:
    """Keep the diagnostic URL while removing credentials and query values."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except ValueError:
        return "<redacted URL>"


def _sanitize_response_body(body: str, api_key: str | None) -> str:
    """Return a short body diagnostic with credential-like values removed."""
    sanitized = body
    if api_key:
        sanitized = sanitized.replace(api_key, "[REDACTED]")
    sanitized = _BEARER_VALUE.sub("[REDACTED]", sanitized)
    sanitized = _SENSITIVE_BODY_VALUE.sub("[REDACTED]", sanitized)
    sanitized = " ".join(sanitized.split())
    if not sanitized:
        return "<empty response body>"
    return sanitized[:300]


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

    if _needs_secondary_ocr(blocks):
        return _run_secondary_ocr(image, image_id, blocks)
    return blocks


def _needs_secondary_ocr(blocks: list[OCRBlock]) -> bool:
    """Trigger a second pass only for sparse or label-like noisy OCR output."""
    if not blocks:
        return True
    numeric_tokens = sum(
        bool(re.fullmatch(r"[\d.,:/-]+", block.text))
        for block in blocks
    )
    label_tokens = sum(
        bool(re.search(r"\b(?:mfg|mrp|exp|date)\b", block.text, re.IGNORECASE))
        for block in blocks
    )
    return numeric_tokens >= 2 or (label_tokens and numeric_tokens >= 1)


def _preprocess_for_secondary_ocr(image: Any) -> tuple[list[Any], float]:
    """Create restrained grayscale variants and preserve a scale to native pixels."""
    image_width, image_height = image.size
    scale = 2.0
    enlarged_size = (int(image_width * scale), int(image_height * scale))
    grayscale = ImageOps.grayscale(image)
    enhanced = ImageEnhance.Contrast(grayscale).enhance(1.5)
    enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    enhanced = enhanced.resize(enlarged_size, Image.Resampling.LANCZOS)
    thresholded = enhanced.point(lambda value: 255 if value >= 160 else 0)
    return [enhanced, thresholded], scale


def _secondary_blocks_from_data(
    data: dict[str, list[Any]],
    image_id: str,
    image_size: tuple[int, int],
    scale: float,
    pass_index: int,
) -> list[OCRBlock]:
    """Convert secondary-pass coordinates back to the original image space."""
    image_width, image_height = image_size
    blocks: list[OCRBlock] = []
    for index in range(len(data.get("text", []))):
        text = str(data["text"][index]).strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][index])
            if not math.isfinite(confidence) or confidence < 0:
                continue
            bbox = [
                int(round(_as_int(data["left"][index]) / scale)),
                int(round(_as_int(data["top"][index]) / scale)),
                int(round(_as_int(data["width"][index]) / scale)),
                int(round(_as_int(data["height"][index]) / scale)),
            ]
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            continue

        blocks.append(
            OCRBlock(
                block_id=f"{image_id}:secondary{pass_index}:{len(blocks) + 1:03d}",
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


def _bbox_iou(first: list[int], second: list[int]) -> float:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    first_right = first_x + first_width
    first_bottom = first_y + first_height
    second_right = second_x + second_width
    second_bottom = second_y + second_height
    intersection_width = max(0, min(first_right, second_right) - max(first_x, second_x))
    intersection_height = max(0, min(first_bottom, second_bottom) - max(first_y, second_y))
    intersection = intersection_width * intersection_height
    union = (first_width * first_height) + (second_width * second_height) - intersection
    return intersection / union if union > 0 else 0.0


def _is_duplicate_secondary_block(
    candidate: OCRBlock,
    existing_blocks: list[OCRBlock],
) -> bool:
    candidate_text = re.sub(r"\s+", " ", candidate.text).strip().casefold()
    return any(
        candidate_text == re.sub(r"\s+", " ", block.text).strip().casefold()
        and _bbox_iou(candidate.bbox, block.bbox) >= 0.5
        for block in existing_blocks
    )


def _text_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _has_consistent_secondary_evidence(
    candidate: OCRBlock,
    existing_blocks: list[OCRBlock],
) -> bool:
    candidate_tokens = _text_tokens(candidate.text)
    has_overlap = False
    for block in existing_blocks:
        if _bbox_iou(candidate.bbox, block.bbox) <= 0:
            continue
        has_overlap = True
        if candidate_tokens & _text_tokens(block.text):
            return True
    return not has_overlap


def _merge_secondary_ocr_blocks(
    original_blocks: list[OCRBlock],
    secondary_blocks: list[OCRBlock],
    image_id: str,
) -> list[OCRBlock]:
    """Retain original blocks and add only non-duplicate secondary evidence."""
    merged = list(original_blocks)
    for candidate in secondary_blocks:
        if _is_duplicate_secondary_block(candidate, merged):
            continue
        if not _has_consistent_secondary_evidence(candidate, merged):
            continue
        merged.append(
            candidate.model_copy(
                update={"block_id": f"{image_id}:b{len(merged) + 1:03d}"}
            )
        )
    return merged


def _run_secondary_ocr(
    image: Any,
    image_id: str,
    original_blocks: list[OCRBlock],
) -> list[OCRBlock]:
    """Run conservative dense-label OCR passes and merge traceable candidates."""
    variants, scale = _preprocess_for_secondary_ocr(image)
    merged = list(original_blocks)
    for pass_index, (variant, psm) in enumerate(zip(variants, (6, 11)), start=1):
        data = pytesseract.image_to_data(
            variant,
            output_type=Output.DICT,
            config=f"--psm {psm}",
        )
        candidates = _secondary_blocks_from_data(
            data,
            image_id,
            image.size,
            scale,
            pass_index,
        )
        merged = _merge_secondary_ocr_blocks(merged, candidates, image_id)
    return merged


def _same_visual_line(block: OCRBlock, line_blocks: list[OCRBlock]) -> bool:
    """Use conservative vertical alignment to keep words on one visual row."""
    _, block_y, _, block_height = block.bbox
    block_bottom = block_y + block_height
    line_top = min(item.bbox[1] for item in line_blocks)
    line_bottom = max(item.bbox[1] + item.bbox[3] for item in line_blocks)
    line_height = line_bottom - line_top
    overlap = max(0, min(block_bottom, line_bottom) - max(block_y, line_top))
    minimum_height = min(block_height, line_height)
    block_center = block_y + block_height / 2
    line_center = (line_top + line_bottom) / 2

    if minimum_height <= 0:
        return False
    return (
        overlap >= minimum_height * 0.5
        or abs(block_center - line_center) <= max(block_height, line_height) * 0.5
    )


def group_ocr_blocks_into_lines(
    blocks: list[OCRBlock],
) -> list[dict[str, list[str] | str]]:
    """Group word blocks into compact prompt lines without changing their text."""
    sorted_blocks = sorted(blocks, key=lambda block: (block.bbox[1], block.bbox[0]))
    grouped: list[list[OCRBlock]] = []

    for block in sorted_blocks:
        if grouped and _same_visual_line(block, grouped[-1]):
            grouped[-1].append(block)
        else:
            grouped.append([block])

    lines = []
    for line_blocks in grouped:
        line_blocks.sort(key=lambda block: block.bbox[0])
        lines.append(
            {
                "text": " ".join(block.text for block in line_blocks),
                "source_block_ids": [
                    block.block_id for block in line_blocks
                ],
            }
        )
    return lines


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
    line_json = json.dumps(
        group_ocr_blocks_into_lines(blocks), ensure_ascii=False
    )
    return (
        "Extract only information explicitly supported by the OCR lines. "
        "Never hallucinate missing values. For a missing field, use value null, "
        "raw_source null, and source_block_ids []. Numeric fields must be actual "
        "JSON numbers, not strings. net_quantity.unit must contain the unit only. "
        "Normalize mrp.unit to INR when the OCR detects INR, Rs, Rs., or the rupee "
        "symbol. Preserve the exact supporting OCR text in raw_source. Use only "
        "source block IDs supplied in the OCR lines, including all contributing IDs "
        "when a field spans multiple blocks. Return JSON only. Do not output "
        "confidence, PASS, FAIL, REVIEW_REQUIRED, or legal interpretation.\n\n"
        f"Required JSON contract:\n{json.dumps(contract, indent=2)}\n\n"
        f"OCR lines:\n{line_json}"
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

    def _request_endpoint(self) -> str:
        if self.config.provider.lower() == "gemini":
            return GEMINI_CHAT_COMPLETIONS_ENDPOINT
        return self.config.endpoint

    def generate(self, prompt: str) -> str:
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        endpoint = self._request_endpoint()
        if self.config.provider.lower() == "gemini":
            request_body = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
            }
        else:
            endpoint = self.config.endpoint
            request_body = {"model": self.config.model, "prompt": prompt}
        response = httpx.post(
            endpoint,
            json=request_body,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and choices:
                choice = choices[0]
                if isinstance(choice, dict):
                    message = choice.get("message")
                    if isinstance(message, dict) and isinstance(
                        message.get("content"), str
                    ):
                        return message["content"]
            for key in ("text", "output", "response"):
                if isinstance(payload.get(key), str):
                    return payload[key]
        return response.text

    def extract(self, blocks: list[OCRBlock]) -> ExtractionResult:
        try:
            return parse_raw_ai_output(self.generate(build_extraction_prompt(blocks)))
        except httpx.HTTPStatusError as error:
            response = error.response
            url = _safe_request_url(str(response.request.url))
            body = _sanitize_response_body(response.text, self.config.api_key)
            return ExtractionError(
                error="llm_request_error",
                message=f"HTTP {response.status_code} from {url}: {body}",
            )
        except httpx.TimeoutException:
            return ExtractionError(
                error="llm_request_error",
                message=(
                    "LLM request timeout contacting "
                    f"{_safe_request_url(self._request_endpoint())}"
                ),
            )
        except httpx.RequestError:
            return ExtractionError(
                error="llm_request_error",
                message=(
                    "LLM network/transport error contacting "
                    f"{_safe_request_url(self._request_endpoint())}"
                ),
            )
        except httpx.HTTPError:
            return ExtractionError(
                error="llm_request_error",
                message=(
                    "LLM network/transport error contacting "
                    f"{_safe_request_url(self._request_endpoint())}"
                ),
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
