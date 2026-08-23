"""Small manual integration helper for Vision-to-OCR evidence inspection."""

import argparse
import json
from pathlib import Path
from typing import Any

from backend.ai_extractor import extract_image as extract_ocr_image
from backend.vision_evidence import map_vision_evidence
from backend.vision_extractor import VisionExtractionError, extract_image as extract_vision_image


def inspect_vision_evidence(image_path: str | Path = "test.jpeg") -> dict[str, Any]:
    """Run OCR and Vision for one image, then print mapped evidence IDs."""
    path = Path(image_path)
    image_id = path.stem
    ocr_blocks, _ = extract_ocr_image(path, image_id)
    vision_result = extract_vision_image(path)

    if isinstance(vision_result, VisionExtractionError):
        output: dict[str, Any] = {"error": vision_result.model_dump()}
    else:
        output = map_vision_evidence(vision_result, ocr_blocks, image_id)

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Vision OCR evidence mapping")
    parser.add_argument("image_path", nargs="?", default="test.jpeg")
    args = parser.parse_args()
    inspect_vision_evidence(args.image_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
