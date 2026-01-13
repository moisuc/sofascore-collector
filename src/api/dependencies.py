"""FastAPI dependencies for database session and common utilities."""

from typing import Generator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.config import settings
from src.storage.database import get_session


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Raises:
        HTTPException: 503 if database storage is disabled

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/matches")
        def get_matches(db: Session = Depends(get_db)):
            return db.query(Match).all()
    """
    if not settings.storage_mode.uses_database():
        raise HTTPException(
            status_code=503,
            detail="Database storage is disabled. Use /files endpoints instead."
        )

    db = get_session()
    try:
        yield db
    finally:
        db.close()
