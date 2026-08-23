from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import main


_png_buffer = BytesIO()
Image.new("RGB", (1, 1), color="white").save(_png_buffer, format="PNG")
VALID_PNG = _png_buffer.getvalue()


@pytest.fixture
def client(monkeypatch):
    database_session = SimpleNamespace(close=lambda: None)
    main.app.dependency_overrides[main.get_db] = lambda: database_session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def _pipeline_result(overall_status="PASS", errors=None):
    return {
        "image_id": "inspection-image",
        "ocr_blocks": [],
        "extracted_fields": {"mrp": {"value": 449, "source_block_ids": []}},
        "confidence": {"mrp": 0.0},
        "compliance_result": {
            "overall_status": overall_status,
            "evaluations": [{"rule_id": "LM-PCR-6-1-e", "status": overall_status}],
        },
        "errors": errors or [],
    }


def _patch_flow(monkeypatch, pipeline_result):
    session = SimpleNamespace(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        status="COMPLETED",
    )
    calls = {}

    def fake_pipeline(image_path, image_id):
        calls["pipeline"] = (image_path, image_id)
        return pipeline_result

    def fake_persist(result, image_path, database_session):
        calls["persist"] = (result, image_path, database_session)
        return session

    monkeypatch.setattr(main, "run_inspection", fake_pipeline)
    monkeypatch.setattr(main, "persist_inspection", fake_persist)
    return calls, session


def _image_upload(content=VALID_PNG, filename="package.png"):
    return {"file": (filename, content, "image/png")}


def test_successful_inspection(client, monkeypatch):
    calls, session = _patch_flow(monkeypatch, _pipeline_result())
    response = client.post("/api/inspection", files=_image_upload())

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session.id)
    assert body["image_id"] == "inspection-image"
    assert body["overall_status"] == "PASS"
    assert body["compliance_evaluations"][0]["rule_id"] == "LM-PCR-6-1-e"
    assert isinstance(calls["pipeline"][1], str)


def test_review_required_inspection_returns_200(client, monkeypatch):
    _patch_flow(
        monkeypatch,
        _pipeline_result(
            overall_status="REVIEW_REQUIRED",
            errors=[{"error": "vision_schema_validation_error"}],
        ),
    )
    response = client.post("/api/inspection", files=_image_upload())

    assert response.status_code == 200
    assert response.json()["overall_status"] == "REVIEW_REQUIRED"
    assert response.json()["errors"] == [
        {"error": "vision_schema_validation_error"}
    ]


def test_invalid_image_upload_returns_400(client, monkeypatch):
    monkeypatch.setattr(main, "run_inspection", pytest.fail)
    response = client.post(
        "/api/inspection",
        files=_image_upload(content=b"not-a-real-image"),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is not a valid image"}


def test_non_image_upload_returns_400(client):
    response = client.post(
        "/api/inspection",
        files={"file": ("package.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 400


def test_pipeline_failure_returns_controlled_500(client, monkeypatch):
    monkeypatch.setattr(main, "run_inspection", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("secret")))
    response = client.post(
        "/api/inspection", files=_image_upload()
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Inspection processing failed"}


def test_persistence_failure_returns_controlled_500(client, monkeypatch):
    _patch_flow(monkeypatch, _pipeline_result())
    monkeypatch.setattr(
        main,
        "persist_inspection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("secret")),
    )
    response = client.post(
        "/api/inspection", files=_image_upload()
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to persist inspection"}


def test_session_id_is_uuid_and_response_shape(client, monkeypatch):
    _, session = _patch_flow(monkeypatch, _pipeline_result())
    response = client.post("/api/inspection", files=_image_upload())

    body = response.json()
    UUID(body["session_id"])
    assert set(body) == {
        "session_id",
        "image_id",
        "overall_status",
        "extracted_fields",
        "confidence",
        "compliance_evaluations",
        "errors",
    }
    assert body["session_id"] == str(session.id)
