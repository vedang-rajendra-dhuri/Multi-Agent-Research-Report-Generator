from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    ResearchReportRecord,
    ResearchSource,
    ResearchTask,
    ResearchTaskStatus,
    ReviewDecision,
    ReviewDecisionType,
    ReportVerificationStatus,
    ReportVersion,
    ReviewStatus,
    TaskEvent,
    User,
)


class RevisionResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class RevisionSessionStub:
    def __init__(self, report, task, version, sources):
        self.values = [report, task, version]
        self.sources = sources
        self.added = []
        self.commits = 0

    def scalar(self, statement):
        return self.values.pop(0)

    def scalars(self, statement):
        return RevisionResult(self.sources)

    def add(self, instance):
        self.added.append(instance)

    def commit(self):
        self.commits += 1

    def refresh(self, instance):
        return None


def build_client(report_status=ReviewStatus.APPROVED, source_ids=None):
    owner_id = uuid4()
    task_id = uuid4()
    report_id = uuid4()
    now = datetime.now(UTC)
    task = ResearchTask(
        id=task_id,
        owner_id=owner_id,
        project_id=uuid4(),
        brief_id=uuid4(),
        status=ResearchTaskStatus.COMPLETED,
        completed_at=now,
    )
    report = ResearchReportRecord(
        id=report_id,
        task_id=task_id,
        review_status=report_status,
        current_version=2,
    )
    version = ReportVersion(
        id=uuid4(),
        report_id=report_id,
        version=2,
        executive_summary="Prior summary",
        sections=[],
        methodology="Prior methodology",
        limitations=[],
        markdown="# Prior report\n",
    )
    sources = [
        ResearchSource(
            id=uuid4(),
            task_id=task_id,
            provider_source_id=provider_id,
            url="https://example.org/source",
            title="Research source",
            source_type="web",
            retrieval_status="retrieved",
            metadata_json={},
            created_at=now,
        )
        for provider_id in (source_ids or [])
    ]
    session = RevisionSessionStub(report, task, version, sources)
    user = User(id=owner_id, email="owner@example.com", full_name="Owner", password_hash="unused")

    def provide_db():
        yield session

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), session, report, task, version, user


def revision_payload(base_version=2, source_ids=None):
    return {
        "base_version": base_version,
        "executive_summary": "Revised summary.",
        "sections": [
            {
                "title": "Findings",
                "content": "Updated findings.",
                "source_ids": source_ids or [],
            }
        ],
        "methodology": "Updated methodology.",
        "limitations": ["Updated limitation."],
        "source_ids": source_ids or [],
    }


def test_report_revision_creates_version_and_returns_for_human_review():
    source_id = "1234567890abcdef"
    client, session, report, task, previous_version, user = build_client(
        source_ids=[source_id]
    )
    try:
        response = client.post(
            f"/api/v1/reports/{report.id}/revisions",
            json=revision_payload(source_ids=[source_id]),
        )

        assert response.status_code == 200
        assert response.json()["current_version"] == 3
        assert response.json()["review_status"] == "pending"
        assert response.json()["task_status"] == "waiting_review"
        assert report.current_version == 3
        assert report.review_status == ReviewStatus.PENDING
        assert task.status == ResearchTaskStatus.WAITING_REVIEW
        assert session.commits == 1
        revised_version = next(
            item for item in session.added if isinstance(item, ReportVersion)
        )
        assert revised_version.version == 3
        assert revised_version.created_by_id == user.id
        assert revised_version.verification_status == ReportVerificationStatus.PENDING
        assert "[1234567890abcdef]" in revised_version.markdown
        revision_decision = next(
            item for item in session.added if isinstance(item, ReviewDecision)
        )
        assert revision_decision.report_version_id == previous_version.id
        assert revision_decision.reviewer_id == user.id
        assert revision_decision.decision == ReviewDecisionType.REVISION_REQUESTED
    finally:
        app.dependency_overrides.clear()


def test_report_revision_rejects_stale_base_version():
    client, session, report, *_ = build_client()
    try:
        response = client.post(
            f"/api/v1/reports/{report.id}/revisions",
            json=revision_payload(base_version=1),
        )

        assert response.status_code == 409
        assert session.commits == 0
    finally:
        app.dependency_overrides.clear()


def test_report_revision_rejects_citations_outside_the_task():
    client, session, report, *_ = build_client(source_ids=["fedcba0987654321"])
    try:
        response = client.post(
            f"/api/v1/reports/{report.id}/revisions",
            json=revision_payload(source_ids=["not-a-real-source"]),
        )

        assert response.status_code == 422
        assert session.commits == 0
    finally:
        app.dependency_overrides.clear()


def test_report_revision_is_unavailable_while_review_is_pending():
    client, session, report, *_ = build_client(report_status=ReviewStatus.PENDING)
    try:
        response = client.post(
            f"/api/v1/reports/{report.id}/revisions",
            json=revision_payload(),
        )

        assert response.status_code == 409
        assert session.commits == 0
    finally:
        app.dependency_overrides.clear()


def test_failed_revision_verification_can_be_requeued_by_its_owner():
    client, session, report, task, version, user = build_client(
        report_status=ReviewStatus.PENDING
    )
    task.status = ResearchTaskStatus.WAITING_REVIEW
    version.verification_status = ReportVerificationStatus.FAILED
    try:
        response = client.post(
            f"/api/v1/reports/{report.id}/versions/{version.version}/reverify"
        )

        assert response.status_code == 200
        assert response.json()["review_status"] == "pending"
        assert version.verification_status == ReportVerificationStatus.PENDING
        assert session.commits == 1
        assert any(isinstance(item, TaskEvent) for item in session.added)
    finally:
        app.dependency_overrides.clear()
