from io import BytesIO
from datetime import UTC, datetime
from uuid import uuid4

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.dialects import postgresql

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    ResearchReportRecord,
    ResearchTask,
    ResearchTaskStatus,
    ReportVersion,
    ReviewStatus,
    User,
)


class SourceRows:
    def all(self):
        return []


class ExportSessionStub:
    def __init__(self, report, task, version, user_id):
        self.report = report
        self.task = task
        self.version = version
        self.user_id = user_id

    def scalar(self, statement):
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        params = list(compiled.params.values())
        if "report_versions" in sql:
            return self.version
        if self.user_id not in params:
            return None
        return self.report

    def get(self, model, key):
        return self.task if model is ResearchTask else None

    def scalars(self, statement):
        return SourceRows()


def build_client(review_status=ReviewStatus.APPROVED):
    user_id = uuid4()
    report_id = uuid4()
    task_id = uuid4()
    version_id = uuid4()
    now = datetime.now(UTC)
    report = ResearchReportRecord(
        id=report_id,
        task_id=task_id,
        review_status=review_status,
        current_version=1,
    )
    task = ResearchTask(
        id=task_id,
        owner_id=user_id,
        project_id=uuid4(),
        brief_id=uuid4(),
        status=ResearchTaskStatus.COMPLETED,
    )
    version = ReportVersion(
        id=version_id,
        report_id=report_id,
        version=1,
        executive_summary="<script>alert('safe')</script>",
        sections=[
            {
                "title": "Finding",
                "content": "A verified section.",
                "source_ids": [],
            }
        ],
        methodology="Reviewed project evidence.",
        limitations=["A known limit."],
        markdown="# Report\n",
        created_at=now,
    )
    user = User(id=user_id, email="owner@example.com", full_name="Owner", password_hash="unused")
    session = ExportSessionStub(report, task, version, user_id)

    def provide_db():
        yield session

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), report


def test_pdf_export_is_valid_and_escapes_report_markup():
    client, report = build_client()
    try:
        response = client.get(f"/api/v1/reports/{report.id}/export/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
        extracted = PdfReader(BytesIO(response.content)).pages[0].extract_text()
        assert "<script>alert('safe')</script>" in extracted
    finally:
        app.dependency_overrides.clear()


def test_docx_export_contains_report_sections():
    client, report = build_client()
    try:
        response = client.get(f"/api/v1/reports/{report.id}/export/docx")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        document = Document(BytesIO(response.content))
        paragraphs = "\n".join(paragraph.text for paragraph in document.paragraphs)
        assert "Executive summary" in paragraphs
        assert "<script>alert('safe')</script>" in paragraphs
        assert "A verified section." in paragraphs
    finally:
        app.dependency_overrides.clear()


def test_non_approved_report_cannot_be_exported_as_pdf():
    client, report = build_client(ReviewStatus.PENDING)
    try:
        response = client.get(f"/api/v1/reports/{report.id}/export/pdf")

        assert response.status_code == 409
        assert response.json()["detail"] == "Only an approved report version can be exported."
    finally:
        app.dependency_overrides.clear()
