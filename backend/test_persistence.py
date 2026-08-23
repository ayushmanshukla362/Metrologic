from pathlib import Path
from uuid import UUID

import pytest

from backend import persistence
from backend.models import (
    ComplianceResult,
    ExtractedField,
    InspectionImage,
    InspectionSession,
    OCRBlock,
)


class _FakeImage:
    size = (1528, 993)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class _FakeSession:
    def __init__(self, fail_on=None, fail_commit=False):
        self.objects = []
        self.fail_on = fail_on
        self.fail_commit = fail_commit
        self.committed = False
        self.rollback_called = False

    def add(self, obj):
        if self.fail_on is not None and isinstance(obj, self.fail_on):
            raise RuntimeError("simulated persistence failure")
        self.objects.append(obj)

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("simulated commit failure")
        self.committed = True

    def rollback(self):
        self.rollback_called = True
        self.objects.clear()


def _pipeline_result():
    fields = {
        "commodity_name": {
            "value": "Biscuits",
            "raw_source": "Biscuits",
            "source_block_ids": ["tests:b001"],
            "confidence": 1.0,
        },
        "net_quantity": {
            "value": 125,
            "unit": "g",
            "raw_source": "125 g",
            "source_block_ids": ["tests:b002"],
            "confidence": 0.95,
        },
        "mfg_date": {
            "value": "23/05/2025",
            "raw_source": "Mfg. Date: 23/05/2025",
            "source_block_ids": [],
            "confidence": 0.15,
        },
        "mrp": {
            "value": 449,
            "unit": "INR",
            "raw_source": "MRP 449",
            "source_block_ids": ["tests:b003"],
            "confidence": 0.9,
        },
        "manufacturer": {
            "value": "Metro Foods",
            "raw_source": "Manufactured By: Metro Foods",
            "source_block_ids": ["tests:b004"],
            "confidence": 0.88,
        },
    }
    evaluations = [
        {
            "rule_id": rule_id,
            "requirement": requirement,
            "status": status,
            "reason": reason,
            "evidence": evidence,
        }
        for rule_id, requirement, status, reason, evidence in (
            (
                "LM-PCR-6-1-b",
                "Generic/Common Commodity Name",
                "PASS",
                "",
                ["tests:b001"],
            ),
            ("LM-PCR-6-1-c", "Net Quantity", "PASS", "", ["tests:b002"]),
            (
                "LM-PCR-6-1-d",
                "Date of Manufacture",
                "REVIEW_REQUIRED",
                "Low extraction confidence",
                [],
            ),
            (
                "LM-PCR-6-1-e",
                "Maximum Retail Price (MRP)",
                "PASS",
                "",
                ["tests:b003"],
            ),
            (
                "LM-PCR-6-1-a",
                "Manufacturer Details",
                "PASS",
                "",
                ["tests:b004"],
            ),
        )
    ]
    return {
        "image_id": "tests",
        "ocr_blocks": [
            {
                "block_id": "tests:b001",
                "text": "Biscuits",
                "bbox": [10, 20, 30, 40],
                "normalized_x1": 0.01,
                "normalized_y1": 0.02,
                "normalized_x2": 0.03,
                "normalized_y2": 0.06,
                "ocr_confidence": 96.0,
            },
            {
                "block_id": "tests:b002",
                "text": "125g",
                "bbox": [40, 50, 60, 25],
                "normalized_x1": 0.03,
                "normalized_y1": 0.05,
                "normalized_x2": 0.07,
                "normalized_y2": 0.08,
                "ocr_confidence": 95.0,
            },
        ],
        "extracted_fields": fields,
        "confidence": {key: value["confidence"] for key, value in fields.items()},
        "compliance_result": {
            "overall_status": "REVIEW_REQUIRED",
            "evaluations": evaluations,
        },
        "errors": [],
    }


def _persist(monkeypatch, fake_session, result=None, **kwargs):
    monkeypatch.setattr(
        persistence.Image,
        "open",
        lambda _path: _FakeImage(),
    )
    return persistence.persist_inspection(
        result or _pipeline_result(),
        Path("tests.png"),
        fake_session,
        **kwargs,
    )


def test_session_image_metadata_and_relationships_are_persisted(monkeypatch):
    database_session = _FakeSession()

    inspection_session = _persist(
        monkeypatch, database_session, processing_time_ms=123
    )

    image = next(obj for obj in database_session.objects if isinstance(obj, InspectionImage))
    assert inspection_session.status == "COMPLETED"
    assert inspection_session.overall_status == "REVIEW_REQUIRED"
    assert inspection_session.processing_time_ms == 123
    assert image.session is inspection_session
    assert image.image_path == "tests.png"
    assert (image.width, image.height) == (1528, 993)
    assert database_session.committed is True


def test_ocr_blocks_preserve_native_geometry_and_confidence(monkeypatch):
    database_session = _FakeSession()
    _persist(monkeypatch, database_session)

    blocks = [obj for obj in database_session.objects if isinstance(obj, OCRBlock)]
    assert len(blocks) == 2
    assert blocks[0].image is blocks[1].image
    assert (blocks[0].x, blocks[0].y, blocks[0].width, blocks[0].height) == (
        10,
        20,
        30,
        40,
    )
    assert blocks[0].ocr_confidence == 96.0
    assert blocks[0].normalized_x2 == 0.03


def test_extracted_fields_jsonb_evidence_confidence_and_status(monkeypatch):
    database_session = _FakeSession()
    _persist(monkeypatch, database_session)

    fields = [obj for obj in database_session.objects if isinstance(obj, ExtractedField)]
    mrp = next(field for field in fields if field.field_key == "mrp")
    mfg_date = next(field for field in fields if field.field_key == "mfg_date")
    assert mrp.value == 449
    assert mrp.unit == "INR"
    assert mrp.source_block_ids == ["tests:b003"]
    assert mrp.confidence == 0.9
    assert mrp.status == "PASS"
    assert mfg_date.source_block_ids == []
    assert mfg_date.status == "REVIEW_REQUIRED"


def test_compliance_rows_and_overall_status_are_persisted(monkeypatch):
    database_session = _FakeSession()
    inspection_session = _persist(monkeypatch, database_session)

    rows = [obj for obj in database_session.objects if isinstance(obj, ComplianceResult)]
    assert len(rows) == 5
    assert {row.status for row in rows} == {"PASS", "REVIEW_REQUIRED"}
    assert all(row.session is inspection_session for row in rows)
    assert next(row for row in rows if row.rule_id == "LM-PCR-6-1-c").evidence == [
        "tests:b002"
    ]


def test_transaction_rolls_back_and_reraises_midway_failure(monkeypatch):
    database_session = _FakeSession(fail_on=ExtractedField)

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        _persist(monkeypatch, database_session)

    assert database_session.rollback_called is True
    assert database_session.committed is False
    assert database_session.objects == []


def test_commit_failure_rolls_back(monkeypatch):
    database_session = _FakeSession(fail_commit=True)

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        _persist(monkeypatch, database_session)

    assert database_session.rollback_called is True
    assert database_session.committed is False


def test_existing_uuid_primary_key_columns_are_unchanged():
    assert isinstance(InspectionSession.__table__.c.id.type.python_type, type)
    assert InspectionSession.__table__.c.id.type.python_type is UUID
    assert InspectionImage.__table__.c.id.type.python_type is UUID
    assert OCRBlock.__table__.c.id.type.python_type is UUID
    assert ExtractedField.__table__.c.id.type.python_type is UUID
    assert ComplianceResult.__table__.c.id.type.python_type is UUID
