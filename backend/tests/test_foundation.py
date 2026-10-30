from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr, ValidationError
from fastapi.testclient import TestClient

from app import database, security
from app.config import Settings
from app.schemas.auth import RegisterRequest
from app.schemas.project import ProjectCreate, ProjectUpdate, ResearchBriefCreate
from app import main


def test_postgres_url_is_normalized_to_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(database_url=SecretStr("postgresql://user:pass@db.example/app"))
    monkeypatch.setattr(database, "get_settings", lambda: settings)

    assert database._database_url() == "postgresql+psycopg://user:pass@db.example/app"


@pytest.mark.parametrize(
    "value",
    [
        None,
        SecretStr(""),
        SecretStr("sqlite:///local.db"),
        SecretStr("postgresql://user:pass@localhost/app"),
        SecretStr("postgresql://user:pass@127.0.0.1/app"),
    ],
)
def test_database_accepts_local_postgres_and_rejects_missing_or_sqlite(
    monkeypatch: pytest.MonkeyPatch, value: SecretStr | None
) -> None:
    settings = Settings(database_url=value)
    monkeypatch.setattr(database, "get_settings", lambda: settings)

    if value is not None and value.get_secret_value().startswith(
        ("postgres://", "postgresql://", "postgresql+psycopg://")
    ):
        assert database._database_url().startswith("postgresql+psycopg://")
    else:
        with pytest.raises(RuntimeError, match="DATABASE_URL|PostgreSQL"):
            database._database_url()


def test_registration_requires_strong_password() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="person@example.com", password="short", full_name="Person")


def test_empty_provider_placeholders_are_treated_as_unconfigured() -> None:
    settings = Settings(
        llm_provider="",
        search_provider="",
        openai_api_key="",
        gemini_api_key="",
        search_provider_api_key="",
    )

    assert settings.llm_provider is None
    assert settings.search_provider is None
    assert settings.openai_api_key is None
    assert settings.gemini_api_key is None
    assert settings.search_provider_api_key is None


def test_project_schemas_trim_titles_and_reject_empty_titles() -> None:
    assert ProjectCreate(title="  Market research  ").title == "Market research"
    with pytest.raises(ValidationError):
        ProjectCreate(title="  ")
    with pytest.raises(ValidationError):
        ProjectUpdate(title=" ")


def test_research_brief_validates_question_depth_and_options() -> None:
    brief = ResearchBriefCreate(
        research_question="Compare current renewable energy storage options",
        objectives=["  Compare costs  "],
        source_preferences=[" Academic studies "],
        depth="deep",
    )

    assert brief.objectives == ["Compare costs"]
    assert brief.source_preferences == ["Academic studies"]
    with pytest.raises(ValidationError):
        ResearchBriefCreate(research_question="too short")
    with pytest.raises(ValidationError):
        ResearchBriefCreate(
            research_question="Compare storage options",
            objectives=["   "],
        )


@pytest.mark.parametrize(
    "origins,app_env",
    [(["*"], "development"), (["https://example.com/path"], "production"), (["http://example.com"], "production")],
)
def test_cors_origins_must_be_explicit_and_secure(
    origins: list[str], app_env: str
) -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(cors_origins=origins, app_env=app_env)


def test_access_token_has_expiry_and_access_type(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(secret_key=SecretStr("a-secure-test-secret-value-with-32-chars"))
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    user_id = uuid4()

    token = security.create_access_token(user_id)
    claims = jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=["HS256"],
    )

    assert claims["sub"] == str(user_id)
    assert claims["type"] == "access"
    assert "exp" in claims


def test_access_tokens_fail_when_secret_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(security, "get_settings", lambda: Settings(_env_file=None))

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        security.create_access_token(uuid4())


def test_auth_configuration_is_rejected_before_registration_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.deps import get_db
    from app.main import app

    monkeypatch.setattr(
        "app.api.v1.auth.validate_security_configuration",
        lambda: (_ for _ in ()).throw(RuntimeError("SECRET_KEY must be configured.")),
    )

    def database_dependency():
        yield object()

    app.dependency_overrides[get_db] = database_dependency
    try:
        response = TestClient(app).post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "a-very-long-password",
                "full_name": "New User",
            },
        )
        assert response.status_code == 503
        assert "SECRET_KEY" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_health_endpoints_report_actual_dependency_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "get_engine", lambda: (_ for _ in ()).throw(RuntimeError("DATABASE_URL is required.")))
    client = TestClient(main.app)

    assert client.get("/health/live").status_code == 200
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["dependency"] == "database"
    assert ready.json()["detail"] == "DATABASE_URL is required."


def test_research_task_preflight_allows_idempotency_header() -> None:
    response = TestClient(main.app).options(
        "/api/v1/projects/project-id/briefs/brief-id/tasks",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization,content-type,idempotency-key,last-event-id,x-csrf-token"
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()
    assert "last-event-id" in response.headers["access-control-allow-headers"].lower()
