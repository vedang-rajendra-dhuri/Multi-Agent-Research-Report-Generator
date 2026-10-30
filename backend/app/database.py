from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    configured = get_settings().database_url
    if configured is None or not configured.get_secret_value().strip():
        raise RuntimeError(
            "DATABASE_URL is required. Configure a PostgreSQL connection string; "
            "SQLite is not supported."
        )

    url = configured.get_secret_value().strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    elif not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must use PostgreSQL with the psycopg 3 driver.")
    try:
        host = make_url(url).host
    except ArgumentError as error:
        raise RuntimeError("DATABASE_URL is not a valid PostgreSQL connection string.") from error
    if not host:
        raise RuntimeError("DATABASE_URL must specify a PostgreSQL server host.")
    return url


def create_database_engine() -> Engine:
    return create_engine(
        _database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"sslmode": get_settings().database_sslmode},
    )


@lru_cache
def get_engine() -> Engine:
    return create_database_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_engine())


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise