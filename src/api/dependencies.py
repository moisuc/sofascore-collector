"""FastAPI dependencies for database session and common utilities."""

from typing import Generator

from sqlalchemy.orm import Session

from src.storage.database import get_session


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/matches")
        def get_matches(db: Session = Depends(get_db)):
            return db.query(Match).all()
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()
