"""Database configuration and connection management."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import URL
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


def get_connection_url() -> str:
    """Build database connection URL from settings."""
    if settings.DATABASE_URL:
        return settings.DATABASE_URL

    url = URL.create(
        drivername="mssql+pyodbc",
        username=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        database=settings.DATABASE_NAME,
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "TrustServerCertificate": "yes",
            "Encrypt": "yes",
        },
    )
    return str(url)


engine = create_engine(
    get_connection_url(),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


def create_db_and_tables() -> None:
    """Create all database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for getting database sessions."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
