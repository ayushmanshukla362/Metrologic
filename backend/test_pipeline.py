from pathlib import Path

from backend.ai_extractor import OCRBlock
from backend.pipeline import run_inspection
from backend.rules import FAIL, PASS, REVIEW_REQUIRED
from backend.vision_extractor import VisionExtraction, VisionExtractionError


class _FakeImage:
    size = (1200, 1600)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def _ocr_blocks():
    fields = [
        ("test:b001", "commodity biscuits"),
        ("test:b002", "net 200 g"),
        ("test:b003", "mfg date 2026-01-15"),
        ("test:b004", "MRP INR 50"),
        ("test:b005", "manufactured Metro Foods"),
    ]
    return [
        OCRBlock(
            block_id=block_id,
            text=text,
            bbox=[10, index * 30, 100, 20],
            ocr_confidence=100.0,
            normalized_x1=0.0,
            normalized_y1=0.0,
            normalized_x2=1.0,
            normalized_y2=1.0,
        )
        for index, (block_id, text) in enumerate(fields)
    ]


def _vision_result(
    *,
    commodity_value="Biscuits",
    net_value=200,
    mfg_value="2026-01-15",
    mrp_value=50,
    manufacturer_value="Metro Foods",
):
    empty = {"value": None, "raw_source": None, "bbox": None}
    return VisionExtraction.model_validate(
        {
            "commodity_name": {
                "value": commodity_value,
                "raw_source": "Biscuits" if commodity_value else None,
                "bbox": [10, 10, 100, 30] if commodity_value else None,
            },
            "net_quantity": {
                "value": net_value,
                "unit": "g" if net_value is not None else None,
                "raw_source": "200 g" if net_value is not None else None,
                "bbox": [10, 40, 100, 60] if net_value is not None else None,
            },
            "mfg_date": {
                "value": mfg_value,
                "raw_source": "Mfg. Date: 2026-01-15" if mfg_value else None,
                "bbox": [10, 70, 100, 90] if mfg_value else None,
            },
            "mrp": {
                "value": mrp_value,
                "unit": "INR" if mrp_value is not None else None,
                "raw_source": "MRP INR 50" if mrp_value is not None else None,
                "bbox": [10, 100, 100, 120] if mrp_value is not None else None,
            },
            "manufacturer": {
                "value": manufacturer_value,
                "raw_source": "Manufactured Metro Foods" if manufacturer_value else None,
                "bbox": [10, 130, 100, 150] if manufacturer_value else None,
            },
        }
    )


def _patch_pipeline(monkeypatch, vision_result, mapped_fields=None):
    blocks = _ocr_blocks()
    calls = {}
    monkeypatch.setattr("backend.pipeline.Image.open", lambda _path: _FakeImage())

    def fake_ocr(path, image_id):
        calls["ocr"] = (path, image_id)
        return blocks, None

    def fake_vision(path):
        calls["vision"] = path
        return vision_result

    def fake_mapper(vision, ocr, image_id, width, height):
        calls["mapper"] = (vision, ocr, image_id, width, height)
        if mapped_fields is not None:
            return mapped_fields
        data = vision.model_dump()
        for index, field_key in enumerate(data):
            if data[field_key]["value"] is not None:
                data[field_key]["source_block_ids"] = [f"test:b{index + 1:03d}"]
        return data

    monkeypatch.setattr("backend.pipeline.extract_ocr_image", fake_ocr)
    monkeypatch.setattr("backend.pipeline.extract_vision_image", fake_vision)
    monkeypatch.setattr("backend.pipeline.map_vision_evidence", fake_mapper)
    return blocks, calls


def test_clean_pipeline_runs_confidence_and_rules(monkeypatch):
    blocks, calls = _patch_pipeline(monkeypatch, _vision_result())

    result = run_inspection("package.jpeg")

    assert result["image_id"] == "package"
    assert result["ocr_blocks"] == [block.model_dump() for block in blocks]
    assert result["confidence"] == {
        "commodity_name": 1.0,
        "net_quantity": 1.0,
        "mfg_date": 1.0,
        "mrp": 1.0,
        "manufacturer": 1.0,
    }
    assert result["compliance_result"]["overall_status"] == PASS
    assert all(
        evaluation["status"] == PASS
        for evaluation in result["compliance_result"]["evaluations"]
    )
    assert calls["mapper"][2:] == ("package", 1200, 1600)
    assert result["errors"] == []


def test_missing_field_completes_safely_and_preserves_rule_result(monkeypatch):
    _patch_pipeline(monkeypatch, _vision_result(mrp_value=None))

    result = run_inspection("package.jpeg")

    mrp = result["extracted_fields"]["mrp"]
    assert mrp["value"] is None
    assert mrp["source_block_ids"] == []
    assert mrp["confidence"] == 0.0
    mrp_evaluation = next(
        item
        for item in result["compliance_result"]["evaluations"]
        if item["rule_id"] == "LM-PCR-6-1-e"
    )
    assert mrp_evaluation["status"] == FAIL


def test_missing_evidence_reaches_rules_engine(monkeypatch):
    vision = _vision_result()
    mapped = vision.model_dump()
    mapped["mrp"]["source_block_ids"] = []
    _patch_pipeline(monkeypatch, vision, mapped_fields=mapped)

    result = run_inspection("package.jpeg")

    assert result["extracted_fields"]["mrp"]["confidence"] == 0.15
    mrp_evaluation = next(
        item
        for item in result["compliance_result"]["evaluations"]
        if item["rule_id"] == "LM-PCR-6-1-e"
    )
    assert mrp_evaluation["status"] == REVIEW_REQUIRED


def test_vision_failure_returns_controlled_review_state(monkeypatch):
    error = VisionExtractionError(
        error="vision_network_error",
        message="Vision request failed",
    )
    blocks, _ = _patch_pipeline(monkeypatch, error)

    result = run_inspection("package.jpeg")

    assert result["ocr_blocks"] == [block.model_dump() for block in blocks]
    assert result["compliance_result"] == {
        "overall_status": REVIEW_REQUIRED,
        "evaluations": [],
    }
    assert all(
        field_data["value"] is None
        for field_data in result["extracted_fields"].values()
    )
    assert result["errors"] == [error.model_dump()]


def test_pipeline_is_deterministic_for_same_mocked_inputs(monkeypatch):
    _patch_pipeline(monkeypatch, _vision_result())
    first = run_inspection(Path("package.jpeg"), image_id="fixed-id")

    _patch_pipeline(monkeypatch, _vision_result())
    second = run_inspection(Path("package.jpeg"), image_id="fixed-id")

    assert first == second
