"""FastAPI application for SofaScore data API."""

from datetime import datetime, UTC
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.routes import live, matches, sports, stats
from src.api.schemas import HealthResponse
from src.storage.database import get_engine

# API metadata
API_TITLE = "SofaScore Collector API"
API_DESCRIPTION = """
Sports data API powered by SofaScore.com browser interception.

## Features

* **Live Matches** - Real-time match data via WebSocket interception
* **Match History** - Scheduled, finished, and postponed matches
* **Statistics** - Detailed match statistics and incidents
* **Multi-Sport** - Football, Tennis, Basketball, Handball, Volleyball

## Data Source

Data is collected by intercepting HTTP/WebSocket traffic from SofaScore.com
using browser automation (Playwright). No direct API calls are made.
"""
API_VERSION = "0.1.0"

# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    root_path="/python/sofascore-collector/src/api",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
STATIC_DIR = Path(__file__).parent.parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    API health check.

    Returns:
        HealthResponse: Health status with database connectivity
    """
    database_connected = True
    try:
        # Test database connection
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
    except Exception:
        database_connected = False

    return HealthResponse(
        status="healthy" if database_connected else "degraded",
        timestamp=datetime.now(UTC),
        database_connected=database_connected,
    )


# Include routers
app.include_router(live.router, prefix="/live", tags=["Live Matches"])
app.include_router(matches.router, prefix="/matches", tags=["Matches"])
app.include_router(sports.router, prefix="/sports", tags=["Sports"])
app.include_router(stats.router, prefix="/stats", tags=["Statistics"])


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """
    API root endpoint.

    Returns:
        dict: Welcome message and API info
    """
    return {
        "message": "SofaScore Collector API",
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
    }


# Dashboard endpoint
@app.get("/dashboard", tags=["System"])
async def dashboard():
    """
    Serve the web dashboard.

    Returns:
        HTML: Dashboard interface
    """
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Dashboard not found"}
