from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import ResearchTaskStatus, ReviewStatus, User


class AnalyticsSessionStub:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.scalar_results = iter([3, 2, 4])
        today = datetime.now(UTC).date()
        self.execute_results = iter(
            [
                [
                    (ResearchTaskStatus.COMPLETED, 2),
                    (ResearchTaskStatus.FAILED, 1),
                ],
                [
                    (today, ResearchTaskStatus.COMPLETED, 2),
                    (today, ResearchTaskStatus.FAILED, 1),
                ],
                [(ReviewStatus.APPROVED, 1)],
                [
                    (
                        uuid4(),
                        uuid4(),
                        "A research project",
                        ResearchTaskStatus.COMPLETED,
                        datetime.now(UTC),
                    )
                ],
            ]
        )
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return next(self.scalar_results)

    def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: next(self.execute_results))


def build_client(owner_id):
    session = AnalyticsSessionStub(owner_id)
    user = User(id=owner_id, email="owner@example.com", full_name="Owner", password_hash="unused")

    def provide_db():
        yield session

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), session


def test_workspace_analytics_returns_selected_period_and_owner_scoped_counts():
    owner_id = uuid4()
    client, session = build_client(owner_id)
    try:
        response = client.get("/api/v1/analytics/workspace?days=7")

        assert response.status_code == 200, response.text
        result = response.json()
        assert result["period_days"] == 7
        assert result["projects_total"] == 3
        assert result["projects_active"] == 2
        assert result["tasks_total"] == 3
        assert result["reports_total"] == 1
        assert result["sources_total"] == 4
        assert len(result["daily_tasks"]) == 7
        assert result["daily_tasks"][-1]["day"] == datetime.now(UTC).date().isoformat()
        assert result["daily_tasks"][-1]["failed"] == 1
        assert result["recent_tasks"][0]["project_title"] == "A research project"

        for statement in session.statements:
            compiled = statement.compile(dialect=postgresql.dialect())
            assert owner_id in compiled.params.values()
    finally:
        app.dependency_overrides.clear()


def test_workspace_analytics_rejects_unsupported_periods():
    owner_id = uuid4()
    client, _ = build_client(owner_id)
    try:
        response = client.get("/api/v1/analytics/workspace?days=14")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
