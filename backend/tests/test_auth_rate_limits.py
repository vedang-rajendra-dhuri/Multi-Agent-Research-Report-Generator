from datetime import UTC, datetime

import pytest
from fastapi import HTTPException, Request
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql

from app import security
from app.config import Settings


class RateLimitResult:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value


class RateLimitSessionStub:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.statements = []
        self.committed = False

    def execute(self, statement):
        self.statements.append(statement)
        return RateLimitResult(next(self.outcomes))

    def commit(self):
        self.committed = True


def request_from_ip(ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": (ip, 12345),
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_auth_rate_limit_buckets_are_hashed_and_commit_before_rejection(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = Settings(secret_key=SecretStr("a-secure-test-secret-value-with-32-chars"))
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    now = datetime.now(UTC)
    db = RateLimitSessionStub([(31, now), (11, now)])

    with pytest.raises(HTTPException) as error:
        security.rate_limit_auth_attempt(
            db,
            request_from_ip("203.0.113.8"),
            "login",
            "private@example.com",
        )

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"].isdigit()
    assert db.committed
    for statement in db.statements:
        compiled = statement.compile(dialect=postgresql.dialect())
        assert "private@example.com" not in repr(compiled.params)
        assert "203.0.113.8" not in repr(compiled.params)


def test_auth_rate_limit_allows_requests_within_limits(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(secret_key=SecretStr("a-secure-test-secret-value-with-32-chars"))
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    now = datetime.now(UTC)
    db = RateLimitSessionStub([(3, now), (2, now)])

    security.rate_limit_auth_attempt(
        db,
        request_from_ip("203.0.113.8"),
        "login",
        "private@example.com",
    )

    assert db.committed
    assert len(db.statements) == 2
