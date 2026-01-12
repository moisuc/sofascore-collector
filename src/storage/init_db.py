"""Database initialization script."""

import logging
from pathlib import Path

from src.storage.database import init_db, get_engine, is_postgresql
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database."""
    logger.info("Initializing database...")

    # Mask password in log output
    db_url = settings.database_url
    if "@" in db_url:
        # Hide password in URL for logging
        parts = db_url.split("@")
        prefix = parts[0].rsplit(":", 1)[0]  # Remove password
        masked_url = f"{prefix}:****@{parts[1]}"
        logger.info(f"Database URL: {masked_url}")
    else:
        logger.info(f"Database URL: {db_url}")

    # Database-specific preparation
    if db_url.startswith("sqlite"):
        # Ensure data directory exists for SQLite
        db_path = db_url.replace("sqlite:///", "")
        if db_path and db_path != ":memory:":
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Database directory: {db_dir}")
        logger.info("Using SQLite database")
    elif is_postgresql(db_url):
        logger.info("Using PostgreSQL database")
        logger.info("Note: Ensure database exists and connection credentials are correct")
        logger.info("JSON columns will use JSONB type for optimal performance")

    # Create all tables
    try:
        init_db()
    except Exception as e:
        error_msg = str(e)
        if "psycopg2" in error_msg or "No module named" in error_msg:
            logger.error("PostgreSQL driver not found!")
            logger.error("Install with: pip install psycopg2-binary")
            logger.error("Or for production: pip install psycopg2")
        raise

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
