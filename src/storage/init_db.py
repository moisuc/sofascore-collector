"""Database initialization script."""

import logging
from pathlib import Path

from src.storage.database import init_db, get_engine
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database."""
    logger.info("Initializing database...")
    logger.info(f"Database URL: {settings.database_url}")

    # Ensure data directory exists for SQLite
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory: {db_dir}")

    # Create all tables
    init_db()

    # Verify tables were created
    engine = get_engine()
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    logger.info(f"Created {len(tables)} tables:")
    for table in tables:
        logger.info(f"  - {table}")

    logger.info("Database initialization complete!")


if __name__ == "__main__":
    main()
