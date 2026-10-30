from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    DocumentChunk,
    ProjectDocument,
    ProjectStatus,
    ResearchProject,
    User,
)


class DocumentSessionStub:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.project = ResearchProject(
            id=uuid4(),
            owner_id=owner_id,
            title="Owned project",
            status=ProjectStatus.ACTIVE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.documents = []
        self.chunks = []
        self.deleted = None

    def scalar(self, statement):
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        params = list(compiled.params.values())
        if (
            "FROM research_projects" in sql
            and self.project.id in params
            and self.owner_id in params
            and self.project.owner_id == self.owner_id
        ):
            return self.project
        return None

    def add(self, instance):
        if isinstance(instance, ProjectDocument):
            instance.id = uuid4()
            instance.created_at = datetime.now(UTC)
            self.documents.append(instance)

    def add_all(self, instances):
        self.chunks.extend(instances)
        document = self.documents[-1]
        document.chunks = instances

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, instance):
        return None

    def delete(self, instance):
        self.deleted = instance


def build_client(owner_id):
    session = DocumentSessionStub(owner_id)
    user = User(id=owner_id, email="owner@example.com", full_name="Owner", password_hash="unused")

    def provide_db():
        yield session

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), session


def test_document_upload_extracts_text_and_persists_bounded_chunks():
    client, session = build_client(uuid4())
    try:
        response = client.post(
            f"/api/v1/projects/{session.project.id}/documents",
            files={"file": ("notes.txt", b"Research text for evidence." * 100, "text/plain")},
        )

        assert response.status_code == 201
        result = response.json()
        assert result["file_name"] == "notes.txt"
        assert result["file_type"] == ".txt"
        assert result["chunk_count"] == len(session.chunks)
        assert all(isinstance(chunk, DocumentChunk) for chunk in session.chunks)
        assert all(chunk.document_id == session.documents[0].id for chunk in session.chunks)
    finally:
        app.dependency_overrides.clear()


def test_document_upload_hides_projects_owned_by_another_user():
    client, session = build_client(uuid4())
    session.project.owner_id = uuid4()
    try:
        response = client.post(
            f"/api/v1/projects/{session.project.id}/documents",
            files={"file": ("notes.txt", b"Private text", "text/plain")},
        )

        assert response.status_code == 404
        assert session.documents == []
    finally:
        app.dependency_overrides.clear()
