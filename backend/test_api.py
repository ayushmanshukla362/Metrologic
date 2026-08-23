from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_db
from backend.models import InspectionSession


class InMemorySession:
    """Small test double for the SQLAlchemy session dependency."""

    def __init__(self, records):
        self.records = records
        self.pending = None

    def add(self, record):
        self.pending = record

    def commit(self):
        if self.pending.id is None:
            self.pending.id = uuid4()
        if self.pending.created_at is None:
            self.pending.created_at = datetime.now(timezone.utc)
        self.records[self.pending.id] = self.pending

    def refresh(self, record):
        return record

    def get(self, model, record_id):
        assert model is InspectionSession
        return self.records.get(record_id)

    def rollback(self):
        self.pending = None

    def close(self):
        return None


@pytest.fixture
def records():
    return {}


@pytest.fixture
def client(records):
    def override_get_db():
        yield InMemorySession(records)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_initialize_session(client):
    response = client.post("/api/session/init", json={"status": "CREATED"})

    assert response.status_code == 201
    body = response.json()
    UUID(body["session_id"])
    assert body["status"] == "CREATED"


def test_get_existing_session(client, records):
    session_id = uuid4()
    records[session_id] = InspectionSession(
        id=session_id,
        status="CREATED",
        overall_status=None,
        created_at=datetime.now(timezone.utc),
        processing_time_ms=None,
    )

    response = client.get(f"/api/session/{session_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == str(session_id)
    assert body["status"] == "CREATED"
    assert body["overall_status"] is None
    assert body["processing_time_ms"] is None
    assert body["created_at"]


def test_get_nonexistent_session_returns_404(client):
    response = client.get(f"/api/session/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Inspection session not found"}
