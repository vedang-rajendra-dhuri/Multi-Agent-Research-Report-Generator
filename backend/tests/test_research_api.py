from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models import ResearchTask, ResearchTaskStatus, User


class TaskResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class TaskSessionStub:
    def __init__(self, owner_id, tasks):
        self.owner_id = owner_id
        self.tasks = tasks

    def scalar(self, statement):
        self._assert_owner_scope(statement)
        return sum(task.owner_id == self.owner_id for task in self.tasks)

    def scalars(self, statement):
        self._assert_owner_scope(statement)
        return TaskResult([task for task in self.tasks if task.owner_id == self.owner_id])

    def _assert_owner_scope(self, statement):
        params = statement.compile(dialect=postgresql.dialect()).params.values()
        assert self.owner_id in params


def build_client(user_id, tasks):
    session = TaskSessionStub(user_id, tasks)
    user = User(id=user_id, email="owner@example.com", full_name="Owner", password_hash="unused")

    def provide_db():
        yield session

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_task_history_lists_only_the_authenticated_users_tasks():
    owner_id = uuid4()
    now = datetime.now(UTC)
    owned_task = ResearchTask(
        id=uuid4(),
        owner_id=owner_id,
        project_id=uuid4(),
        brief_id=uuid4(),
        status=ResearchTaskStatus.COMPLETED,
        attempt_count=1,
        created_at=now,
        started_at=now,
        completed_at=now,
    )
    private_task = ResearchTask(
        id=uuid4(),
        owner_id=uuid4(),
        project_id=uuid4(),
        brief_id=uuid4(),
        status=ResearchTaskStatus.COMPLETED,
        attempt_count=1,
        created_at=now,
        started_at=now,
        completed_at=now,
    )
    client = build_client(owner_id, [owned_task, private_task])
    try:
        response = client.get("/api/v1/tasks")

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == str(owned_task.id)
        assert response.json()["items"][0]["status"] == "completed"
    finally:
        app.dependency_overrides.clear()
