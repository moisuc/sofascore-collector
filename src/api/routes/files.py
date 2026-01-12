"""API endpoints for accessing stored JSON files."""

import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.api.schemas import FileListResponse, FileMetadata
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Regex pattern to parse filename: {pattern}_{sport}_{date}.json
FILENAME_PATTERN = re.compile(r"^(\w+)_([\w-]+)_(\d{4}_\d{2}_\d{2})\.json$")


def get_files_directory() -> Path:
    """Get the files storage directory path."""
    return Path(settings.file_storage_base_path)


def parse_filename(filename: str) -> dict | None:
    """
    Parse filename into components.

    Args:
        filename: Filename like "scheduled_football_2025_01_12.json"

    Returns:
        Dict with pattern, sport, date or None if invalid
    """
    match = FILENAME_PATTERN.match(filename)
    if not match:
        return None
    return {
        "pattern": match.group(1),
        "sport": match.group(2),
        "date": match.group(3),
    }


@router.get("", response_model=FileListResponse)
def list_files(
    pattern: str | None = Query(None, description="Filter by pattern (live, scheduled, featured, inverse)"),
    sport: str | None = Query(None, description="Filter by sport (football, tennis, etc)"),
    date: str | None = Query(None, description="Filter by date (YYYY_MM_DD format)"),
) -> FileListResponse:
    """
    List all stored JSON files with metadata.

    Files are sorted by modification time (newest first).

    Args:
        pattern: Optional filter by API pattern
        sport: Optional filter by sport type
        date: Optional filter by date

    Returns:
        FileListResponse: List of files with metadata
    """
    files_dir = get_files_directory()

    if not files_dir.exists():
        return FileListResponse(total=0, files=[])

    files: list[FileMetadata] = []

    for file_path in files_dir.glob("*.json"):
        if not file_path.is_file():
            continue

        parsed = parse_filename(file_path.name)
        if not parsed:
            logger.warning(f"Skipping file with invalid name format: {file_path.name}")
            continue

        # Apply filters
        if pattern and parsed["pattern"] != pattern:
            continue
        if sport and parsed["sport"] != sport:
            continue
        if date and parsed["date"] != date:
            continue

        stat = file_path.stat()
        files.append(
            FileMetadata(
                filename=file_path.name,
                pattern=parsed["pattern"],
                sport=parsed["sport"],
                date=parsed["date"],
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        )

    # Sort by modified time (newest first)
    files.sort(key=lambda f: f.modified_at, reverse=True)

    return FileListResponse(total=len(files), files=files)


@router.get("/{filename}")
def download_file(filename: str) -> FileResponse:
    """
    Download a specific JSON file.

    Args:
        filename: Name of the file to download (e.g., "scheduled_football_2025_01_12.json")

    Returns:
        FileResponse: The JSON file for download

    Raises:
        HTTPException: 404 if file not found, 400 if invalid filename
    """
    # Validate filename format to prevent path traversal
    if not FILENAME_PATTERN.match(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename format. Expected: {pattern}_{sport}_{date}.json"
        )

    files_dir = get_files_directory()
    file_path = files_dir / filename

    # Security check: ensure the resolved path is still within files_dir
    try:
        file_path = file_path.resolve()
        files_dir_resolved = files_dir.resolve()
        if not str(file_path).startswith(str(files_dir_resolved)):
            raise HTTPException(status_code=400, detail="Invalid filename")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {filename}"
        )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/json",
    )


@router.get("/{filename}/content")
def get_file_content(filename: str) -> dict:
    """
    Get the content of a specific JSON file directly.

    This returns the JSON content inline rather than as a download.

    Args:
        filename: Name of the file (e.g., "scheduled_football_2025_01_12.json")

    Returns:
        dict: The JSON content of the file

    Raises:
        HTTPException: 404 if file not found, 400 if invalid filename
    """
    import json

    # Validate filename format to prevent path traversal
    if not FILENAME_PATTERN.match(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename format. Expected: {pattern}_{sport}_{date}.json"
        )

    files_dir = get_files_directory()
    file_path = files_dir / filename

    # Security check: ensure the resolved path is still within files_dir
    try:
        file_path = file_path.resolve()
        files_dir_resolved = files_dir.resolve()
        if not str(file_path).startswith(str(files_dir_resolved)):
            raise HTTPException(status_code=400, detail="Invalid filename")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {filename}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing JSON file: {e}"
        )
