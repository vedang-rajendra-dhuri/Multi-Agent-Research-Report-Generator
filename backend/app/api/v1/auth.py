import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.security import (
    create_access_token,
    hash_password,
    issue_refresh_token,
    refresh_session,
    revoke_refresh_token,
    validate_security_configuration,
    validate_csrf,
    rate_limit_auth_attempt,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_auth_cookies(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    secure = settings.is_production
    same_site = "none" if secure else "strict"
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path=f"{settings.api_v1_prefix}/auth",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )
    response.set_cookie(
        "csrf_token",
        secrets.token_urlsafe(32),
        httponly=False,
        secure=secure,
        samesite=same_site,
        path="/",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        "refresh_token",
        path=f"{settings.api_v1_prefix}/auth",
        samesite="none" if settings.is_production else "strict",
        secure=settings.is_production,
    )
    response.delete_cookie(
        "csrf_token",
        path="/",
        samesite="none" if settings.is_production else "strict",
        secure=settings.is_production,
    )


def _auth_response(user: User, refresh_token: str, response: Response) -> AuthResponse:
    _set_auth_cookies(response, refresh_token)
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    try:
        validate_security_configuration()
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from None
    email = str(body.email).strip().lower()
    rate_limit_auth_attempt(db, request, "register", email)
    user = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
        refresh_token = issue_refresh_token(db, user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        ) from None
    return _auth_response(user, refresh_token, response)


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    try:
        validate_security_configuration()
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from None
    email = str(body.email).strip().lower()
    rate_limit_auth_attempt(db, request, "login", email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    refresh_token = issue_refresh_token(db, user)
    db.commit()
    return _auth_response(user, refresh_token, response)


@router.post("/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response, db: DbSession) -> AuthResponse:
    validate_csrf(request)
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    user, rotated_token = refresh_session(db, token)
    return _auth_response(user, rotated_token, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> Response:
    validate_csrf(request)
    revoke_refresh_token(db, request.cookies.get("refresh_token"))
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)