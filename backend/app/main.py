import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.api.v1.router import api_router
from app.config import get_settings
from app.database import get_engine
from app.services.document_ingestion import MAX_UPLOAD_BYTES

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for field in ("method", "path", "status_code", "duration_ms", "error_type"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload)


logging.basicConfig(level=logging.INFO)
for log_handler in logging.getLogger().handlers:
    log_handler.setFormatter(JsonLogFormatter())
logger = logging.getLogger("researchpilot")
settings = get_settings()
alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
expected_migration = ScriptDirectory.from_config(alembic_config).get_current_head()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "Last-Event-ID",
        "X-CSRF-Token",
        "X-Request-ID",
    ],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID")
    try:
        request_id = str(UUID(supplied_id)) if supplied_id else str(uuid4())
    except ValueError:
        request_id = str(uuid4())
    request.state.request_id = request_id
    context_token = request_id_context.set(request_id)
    started_at = perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http.request.completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return response
    finally:
        request_id_context.reset(context_token)


@app.middleware("http")
async def limit_document_upload_size(request: Request, call_next):
    if (
        request.method == "POST"
        and request.url.path.startswith(f"{settings.api_v1_prefix}/projects/")
        and request.url.path.endswith("/documents")
    ):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                body_size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header."},
                )
            if body_size > MAX_UPLOAD_BYTES + 64 * 1024:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Documents are limited to 10 MB."},
                )
    return await call_next(request)


@app.get("/health/live", tags=["operations"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["operations"])
def readiness():
    try:
        with get_engine().connect() as connection:
            current_migration = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
    except RuntimeError as error:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "dependency": "database", "detail": str(error)},
        )
    except SQLAlchemyError as error:
        logger.error(
            "database.readiness_failed",
            extra={"error_type": type(error).__name__},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "dependency": "database",
                "detail": "PostgreSQL is unavailable or its migrations are not applied.",
            },
        )
    if current_migration != expected_migration:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "dependency": "database",
                "detail": "Database migrations are not current. Apply the Alembic migrations.",
            },
        )
    return {"status": "ready", "database": "connected"}


app.include_router(api_router, prefix=settings.api_v1_prefix)