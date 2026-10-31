import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import TaskStatus
from app.services.parser import IngestionError
from app.store import task_store

client = TestClient(app)


def test_analyze_returns_task_id() -> None:
    response = client.post(
        "/api/v1/analyze",
        json={
            "document_url": "https://egazette.gov.in/sample.pdf",
            "target_language": "hi-IN",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert body["task_id"]


def test_analyze_result_is_pollable() -> None:
    created = client.post(
        "/api/v1/analyze",
        json={"document_url": "https://pib.gov.in/sample.pdf", "target_language": "ta-IN"},
    ).json()

    response = client.get(f"/api/v1/results/{created['task_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == created["task_id"]
    assert body["status"] == "processing"
    assert body["result"] is None


def test_analyze_records_ingestion_metadata() -> None:
    created = client.post(
        "/api/v1/analyze",
        json={"document_url": "https://pib.gov.in/sample.pdf", "target_language": "bn-IN"},
    ).json()

    record = task_store.get(created["task_id"])

    assert record is not None
    assert record.parser == "pypdf"
    assert record.page_count == 1
    assert record.parsed_markdown_path is not None
    assert record.status is TaskStatus.processing


def test_analyze_marks_task_failed_when_ingestion_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_parse(document_url: str, *, task_id: str, **kwargs: object) -> None:
        raise IngestionError("blocked by upstream")

    monkeypatch.setattr("app.api.v1.analyze.parse_document", failing_parse)

    created = client.post(
        "/api/v1/analyze",
        json={"document_url": "https://pib.gov.in/broken.pdf", "target_language": "te-IN"},
    ).json()

    record = task_store.get(created["task_id"])

    assert record is not None
    assert record.status is TaskStatus.failed
    assert record.error is not None
    assert "blocked by upstream" in record.error


def test_unknown_task_returns_404() -> None:
    response = client.get("/api/v1/results/does-not-exist")

    assert response.status_code == 404


def test_analyze_rejects_invalid_url() -> None:
    response = client.post(
        "/api/v1/analyze",
        json={"document_url": "not-a-url", "target_language": "hi-IN"},
    )

    assert response.status_code == 422


def test_analyze_rejects_unknown_language() -> None:
    response = client.post(
        "/api/v1/analyze",
        json={"document_url": "https://egazette.gov.in/sample.pdf", "target_language": "fr-FR"},
    )

    assert response.status_code == 422


def test_verify_citizen_is_not_implemented_yet() -> None:
    response = client.post(
        "/api/v1/verify-citizen",
        json={
            "policy_id": "sample",
            "citizen_profile": {"income": 180000, "occupation": "street_vendor", "state": "Delhi"},
        },
    )

    assert response.status_code == 501


def test_openapi_schema_renders() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/analyze" in paths
    assert "/api/v1/results/{task_id}" in paths
    assert "/api/v1/verify-citizen" in paths
