import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthRateLimit, User, UserSession

password_hasher = PasswordHash.recommended()
AUTH_RATE_LIMIT_WINDOW = timedelta(minutes=15)
AUTH_RATE_LIMIT_PER_IP = 30
AUTH_RATE_LIMIT_PER_IDENTITY = 10


def _secret_key() -> str:
    secret = get_settings().secret_key
    if secret is None or len(secret.get_secret_value()) < 32:
        raise RuntimeError("SECRET_KEY must be configured with at least 32 characters.")
    return secret.get_secret_value()


def validate_security_configuration() -> None:
    _secret_key()


def _rate_limit_key(scope: str) -> str:
    return hmac.new(_secret_key().encode("utf-8"), scope.encode("utf-8"), hashlib.sha256).hexdigest()


def _consume_auth_bucket(
    db: Session,
    key_hash: str,
    now: datetime,
) -> tuple[int, datetime]:
    cutoff = now - AUTH_RATE_LIMIT_WINDOW
    statement = insert(AuthRateLimit).values(
        key_hash=key_hash,
        window_started_at=now,
        request_count=1,
        updated_at=now,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[AuthRateLimit.key_hash],
        set_={
            "window_started_at": case(
                (AuthRateLimit.window_started_at <= cutoff, now),
                else_=AuthRateLimit.window_started_at,
            ),
            "request_count": case(
                (AuthRateLimit.window_started_at <= cutoff, 1),
                else_=AuthRateLimit.request_count + 1,
            ),
            "updated_at": now,
        },
    ).returning(AuthRateLimit.request_count, AuthRateLimit.window_started_at)
    return db.execute(statement).one()


def rate_limit_auth_attempt(
    db: Session,
    request: Request,
    endpoint: str,
    email: str,
) -> None:
    now = datetime.now(UTC)
    client_ip = request.client.host if request.client else "unknown"
    ip_count, ip_window_start = _consume_auth_bucket(
        db,
        _rate_limit_key(f"auth-ip:{endpoint}:{client_ip}"),
        now,
    )
    identity_count, identity_window_start = _consume_auth_bucket(
        db,
        _rate_limit_key(f"auth-identity:{endpoint}:{email}"),
        now,
    )
    db.commit()
    retry_after = 0
    if ip_count > AUTH_RATE_LIMIT_PER_IP:
        retry_after = ceil(
            (ip_window_start + AUTH_RATE_LIMIT_WINDOW - now).total_seconds()
        )
    if identity_count > AUTH_RATE_LIMIT_PER_IDENTITY:
        retry_after = max(
            retry_after,
            ceil(
                (identity_window_start + AUTH_RATE_LIMIT_WINDOW - now).total_seconds()
            ),
        )
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
            headers={"Retry-After": str(max(1, retry_after))},
        )


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def _digest_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        _secret_key(),
        algorithm="HS256",
    )


def issue_refresh_token(db: Session, user: User) -> str:
    settings = get_settings()
    token = secrets.token_urlsafe(48)
    db.add(
        UserSession(
            user_id=user.id,
            refresh_token_hash=_digest_refresh_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    return token


def validate_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("x-csrf-token")
    origin = request.headers.get("origin")
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
        or (origin is not None and origin not in get_settings().cors_origins)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")


def refresh_session(db: Session, token: str) -> tuple[User, str]:
    token_hash = _digest_refresh_token(token)
    session = db.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash).with_for_update()
    )
    now = datetime.now(UTC)
    if session is None or session.expires_at <= now:
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is unavailable.")

    rotated_token = secrets.token_urlsafe(48)
    session.refresh_token_hash = _digest_refresh_token(rotated_token)
    session.expires_at = now + timedelta(days=get_settings().refresh_token_days)
    db.commit()
    return user, rotated_token


def revoke_refresh_token(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == _digest_refresh_token(token)
        )
    )
    if session is not None:
        db.delete(session)
        db.commit()
