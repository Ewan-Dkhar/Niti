"""Live end-to-end checks against real government PDFs.

Run explicitly: ``uv run pytest -m live``. The default suite excludes these so
normal development stays offline and fast.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.live

LIVE_DOCUMENTS = [
    "https://labour.gov.in/static/uploads/2026/06/0c9a83a81e01bef6936dc4437c7fc310.pdf",
    "https://www.dpiit.gov.in/static/uploads/2026/05/56bdc6d167272593fbeae8b4c44d6cc4.pdf",
    "https://www.texmin.gov.in/static/uploads/2026/04/e092828a803ecf8151a14810141fdc68.pdf",
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("document_url", LIVE_DOCUMENTS)
def test_live_document_end_to_end(client: TestClient, document_url: str) -> None:
    created = client.post(
        "/api/v1/analyze",
        json={"document_url": document_url, "target_language": "hi-IN"},
    )
    assert created.status_code == 202
    task_id = created.json()["task_id"]

    response = client.get(f"/api/v1/results/{task_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed", body.get("error")
    result = body["result"]
    assert result["policy_data"]["policy_name"]
    assert result["audit_status"]["is_grounded"] is True
    assert result["audit_status"]["confidence_score"] == 1.0
    assert result["voice_payload"]["plain_text_script"]
    assert result["audio_url"]

    audio = client.get(result["audio_url"])
    assert audio.status_code == 200
    assert audio.content.startswith(b"RIFF")
