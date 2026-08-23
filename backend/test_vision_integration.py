import json
import sys
from pathlib import Path

from backend.ai_extractor import OCRBlock
from backend.vision_extractor import VisionExtraction
from backend.vision_integration import inspect_vision_evidence, main


def _vision_result():
    empty_text = {"value": None, "raw_source": None, "bbox": None}
    return VisionExtraction.model_validate(
        {
            "commodity_name": empty_text,
            "net_quantity": {
                "value": None,
                "unit": None,
                "raw_source": None,
                "bbox": None,
            },
            "mfg_date": {
                "value": "2026-01-15",
                "raw_source": "Mfg. Date: 2026-01-15",
                "bbox": [10, 10, 100, 30],
            },
            "mrp": {
                "value": 50,
                "unit": "INR",
                "raw_source": "MRP Rs. 50",
                "bbox": [10, 40, 100, 60],
            },
            "manufacturer": {
                "value": "Metro Foods",
                "raw_source": "Manufactured by Metro Foods",
                "bbox": [10, 70, 160, 95],
            },
        }
    )


def _ocr_block(block_id, bbox):
    return OCRBlock(
        block_id=block_id,
        text="evidence",
        bbox=bbox,
        ocr_confidence=95.0,
        normalized_x1=0.0,
        normalized_y1=0.0,
        normalized_x2=1.0,
        normalized_y2=1.0,
    )


def test_integration_wires_ocr_vision_and_evidence_mapper(monkeypatch, capsys):
    ocr_blocks = [_ocr_block("test:b001", [10, 10, 100, 30])]
    vision_result = _vision_result()
    calls = {}

    def fake_ocr(image_path, image_id):
        calls["ocr"] = (image_path, image_id)
        return ocr_blocks, None

    def fake_vision(image_path):
        calls["vision"] = image_path
        return vision_result

    def fake_mapper(vision, blocks, image_id):
        calls["mapper"] = (vision, blocks, image_id)
        return {
            "mfg_date": {
                "value": vision.mfg_date.value,
                "raw_source": vision.mfg_date.raw_source,
                "bbox": vision.mfg_date.bbox,
                "source_block_ids": ["test:b001"],
            },
            "mrp": {
                "value": vision.mrp.value,
                "unit": vision.mrp.unit,
                "raw_source": vision.mrp.raw_source,
                "bbox": vision.mrp.bbox,
                "source_block_ids": [],
            },
            "manufacturer": {
                "value": vision.manufacturer.value,
                "raw_source": vision.manufacturer.raw_source,
                "bbox": vision.manufacturer.bbox,
                "source_block_ids": [],
            },
            "commodity_name": {
                "value": None,
                "raw_source": None,
                "bbox": None,
                "source_block_ids": [],
            },
            "net_quantity": {
                "value": None,
                "unit": None,
                "raw_source": None,
                "bbox": None,
                "source_block_ids": [],
            },
        }

    monkeypatch.setattr("backend.vision_integration.extract_ocr_image", fake_ocr)
    monkeypatch.setattr("backend.vision_integration.extract_vision_image", fake_vision)
    monkeypatch.setattr("backend.vision_integration.map_vision_evidence", fake_mapper)

    output = inspect_vision_evidence("test.jpeg")

    assert calls["ocr"] == (Path("test.jpeg"), "test")
    assert calls["vision"] == Path("test.jpeg")
    assert calls["mapper"] == (vision_result, ocr_blocks, "test")
    assert output["mfg_date"]["source_block_ids"] == ["test:b001"]
    assert output["mrp"]["source_block_ids"] == []
    assert output["manufacturer"]["source_block_ids"] == []
    assert output["commodity_name"]["source_block_ids"] == []
    assert output["net_quantity"]["source_block_ids"] == []
    assert json.loads(capsys.readouterr().out) == output


def _patch_cli_pipeline(monkeypatch, calls):
    vision_result = _vision_result()
    ocr_blocks = [_ocr_block("tests:b001", [10, 10, 100, 30])]

    def fake_ocr(image_path, image_id):
        calls["ocr"] = (image_path, image_id)
        return ocr_blocks, None

    def fake_vision(image_path):
        calls["vision"] = image_path
        return vision_result

    def fake_mapper(vision, blocks, image_id):
        calls["mapper"] = (vision, blocks, image_id)
        return {"mfg_date": {"source_block_ids": []}}

    monkeypatch.setattr("backend.vision_integration.extract_ocr_image", fake_ocr)
    monkeypatch.setattr("backend.vision_integration.extract_vision_image", fake_vision)
    monkeypatch.setattr("backend.vision_integration.map_vision_evidence", fake_mapper)


def test_cli_accepts_explicit_image_path(monkeypatch):
    calls = {}
    _patch_cli_pipeline(monkeypatch, calls)
    monkeypatch.setattr(sys, "argv", ["vision_integration", ".\\tests.png"])

    assert main() == 0
    assert calls["ocr"] == (Path("tests.png"), "tests")
    assert calls["vision"] == Path("tests.png")
    assert calls["mapper"][2] == "tests"


def test_cli_without_path_retains_test_jpeg_default(monkeypatch):
    calls = {}
    _patch_cli_pipeline(monkeypatch, calls)
    monkeypatch.setattr(sys, "argv", ["vision_integration"])

    assert main() == 0
    assert calls["ocr"] == (Path("test.jpeg"), "test")
    assert calls["vision"] == Path("test.jpeg")


def test_cli_image_id_is_the_filename_stem(monkeypatch):
    calls = {}
    _patch_cli_pipeline(monkeypatch, calls)
    monkeypatch.setattr(
        sys,
        "argv",
        ["vision_integration", "C:\\images\\package-front.jpeg"],
    )

    assert main() == 0
    assert calls["ocr"][1] == "package-front"
    assert calls["mapper"][2] == "package-front"
