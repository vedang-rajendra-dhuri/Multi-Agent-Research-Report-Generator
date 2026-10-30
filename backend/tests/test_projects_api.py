from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import ProjectStatus, ResearchProject, User


class ProjectSessionStub:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.project = None

    def add(self, instance):
        self.project = instance
        instance.id = uuid4()
        instance.created_at = datetime.now(UTC)
        instance.updated_at = instance.created_at

    def commit(self):
        if self.project is not None and self.project.status is None:
            self.project.status = ProjectStatus.ACTIVE

    def refresh(self, instance):
        assert instance is self.project

    def scalar(self, statement):
        compiled = statement.compile(dialect=postgresql.dialect())
        params = list(compiled.params.values())
        if (
            self.project is None
            or self.project.owner_id != self.owner_id
            or self.project.id not in params
            or self.owner_id not in params
        ):
            return None
        return self.project


def build_client(user_id):
    session = ProjectSessionStub(user_id)
    user = User(id=user_id, email="owner@example.com", full_name="Owner", password_hash="unused")

    def provide_db():
        yield session

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), session


def test_project_create_and_get_are_owner_scoped():
    owner_id = uuid4()
    client, session = build_client(owner_id)
    try:
        created = client.post(
            "/api/v1/projects",
            json={"title": "Market analysis", "description": "Compare current products."},
        )
        assert created.status_code == 201
        project_id = created.json()["id"]
        assert session.project.owner_id == owner_id
        assert session.project.status == ProjectStatus.ACTIVE

        retrieved = client.get(f"/api/v1/projects/{project_id}")
        assert retrieved.status_code == 200
        assert retrieved.json()["title"] == "Market analysis"
    finally:
        app.dependency_overrides.clear()


def test_project_lookup_hides_resources_owned_by_other_users():
    owner_id = uuid4()
    client, session = build_client(owner_id)
    session.project = ResearchProject(
        id=uuid4(),
        owner_id=uuid4(),
        title="Private project",
        status=ProjectStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    try:
        response = client.get(f"/api/v1/projects/{session.project.id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found."
    finally:
        app.dependency_overrides.clear()
