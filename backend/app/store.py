"""In-memory task store for analysis jobs.

Phase 1 keeps this process-local; a persistent backend can replace it later
without changing the API layer.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.schemas import AnalysisResult, LanguageCode, TaskStatus


@dataclass
class TaskRecord:
    task_id: str
    document_url: str
    target_language: LanguageCode
    status: TaskStatus = TaskStatus.processing
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    parsed_markdown_path: str | None = None
    parser: str | None = None
    page_count: int | None = None
    from_cache: bool = False
    extracted_data: dict | None = None
    audit_report: dict | None = None
    simplified_script: str | None = None
    audio_output_url: str | None = None
    result: AnalysisResult | None = None
    error: str | None = None


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def create(self, document_url: str, target_language: LanguageCode) -> TaskRecord:
        task_id = uuid4().hex
        record = TaskRecord(
            task_id=task_id,
            document_url=document_url,
            target_language=target_language,
        )
        self._tasks[task_id] = record
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def clear(self) -> None:
        self._tasks.clear()


task_store = TaskStore()
