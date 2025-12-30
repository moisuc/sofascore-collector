# SofaScore Collector

Live sports data collection system that intercepts SofaScore.com HTTP/WebSocket traffic via browser automation with REST API access.

## Overview

Python-based sports data collector that uses Playwright to automate browsers, intercept network traffic, and store match data in SQLite. No direct SofaScore API calls - navigates like a real user and captures responses. Includes a FastAPI REST API for accessing collected data.

## Stack

- **Language**: Python 3.14+
- **Framework**: FastAPI (REST API server)
- **Browser Automation**: Playwright
- **Database**: SQLite (SQLAlchemy ORM)
- **Task Scheduling**: APScheduler
- **Cache** (optional): Redis
- **Testing**: pytest + pytest-asyncio (4,883 test lines)
- **Linter**: Ruff

## Commands

```bash
# Setup
uv sync                          # Install dependencies
uv sync --group dev              # Install dev dependencies
playwright install               # Install browser binaries

# Run
uv run python main.py            # Run orchestrator with live trackers
uv run uvicorn src.api.main:app --reload  # Start FastAPI server (dev mode)
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000  # Production

# Examples
uv run python examples/browser_usage.py
uv run python examples/collector_usage.py
uv run python examples/orchestrator_usage.py

# Testing
uv run pytest                    # Run all tests
uv run pytest tests/parsers/     # Run specific test module
uv run pytest -v                 # Verbose output
uv run pytest -k "test_name"     # Run specific test

# Linting
uv run ruff check .              # Check code quality
uv run ruff format .             # Format code
uv run ruff check --fix .        # Auto-fix issues

# Database
uv run python -m src.storage.init_db  # Initialize database
```

## Structure

```
sofascore-collector/
├── src/
│   ├── browser/         # Playwright browser automation + interceptors
│   │   ├── manager.py           # Browser instance management
│   │   ├── interceptor.py       # HTTP response interception
│   │   └── ws_interceptor.py    # WebSocket message interception
│   ├── collectors/      # Data collection strategies
│   │   ├── base.py              # Abstract base collector
│   │   ├── live_tracker.py      # Live match tracking
│   │   └── daily_events.py      # Scheduled match collection
│   ├── parsers/         # Response parsing logic
│   │   ├── api_response.py      # HTTP API response parsing
│   │   └── ws_message.py        # WebSocket message parsing
│   ├── storage/         # Database layer
│   │   ├── database.py          # SQLAlchemy models
│   │   ├── repositories.py      # CRUD operations (with field filtering)
│   │   └── init_db.py           # Database initialization
│   ├── models/          # Pydantic models (data validation)
│   │   └── schemas.py           # API request/response schemas
│   ├── orchestrator/    # Multi-collector coordination
│   │   ├── coordinator.py       # Main orchestrator
│   │   └── handlers.py          # Data persistence handlers
│   ├── api/             # FastAPI REST API
│   │   ├── main.py              # FastAPI app + middleware
│   │   ├── routes/              # API route modules
│   │   │   ├── live.py          # Live matches endpoints
│   │   │   ├── matches.py       # Match history endpoints
│   │   │   ├── sports.py        # Sports/teams/leagues endpoints
│   │   │   └── stats.py         # Statistics endpoints
│   │   ├── dependencies.py      # Dependency injection (DB sessions)
│   │   └── schemas.py           # API schemas
│   └── config.py        # Settings (loads from .env)
├── tests/               # Comprehensive test suite (mirrors src/)
│   ├── browser/         # Browser automation tests
│   ├── collectors/      # Collector tests
│   ├── orchestrator/    # Orchestrator tests
│   ├── parsers/         # Parser tests
│   ├── storage/         # Repository tests
│   └── conftest.py      # Shared pytest fixtures
├── examples/            # Usage examples
│   ├── mock_data/       # Sample API responses for testing
│   ├── browser_usage.py
│   ├── collector_usage.py
│   └── orchestrator_usage.py
├── data/                # SQLite database storage
├── main.py              # Production entry point (orchestrator)
└── pyproject.toml       # Project config + dependencies
```

## Architecture Patterns

### 1. Browser Automation Strategy
- **No Direct API Calls**: Navigate pages like a real user, intercept network responses
- **Isolated Contexts**: Each sport gets its own browser context
- **Dual Interception**: HTTP responses (REST API) + WebSocket messages (live updates)

### 2. Collector Pattern
All collectors inherit from `BaseCollector`:
- `setup()` - Initialize browser page and interceptors
- `collect()` - Main data collection logic (abstract method)
- `cleanup()` - Resource cleanup
- Built-in retry logic with exponential backoff (5 retries max)
- Context manager support (`async with`)

### 3. Repository Pattern
Database operations use repository classes with field filtering:
- `TeamRepository`, `LeagueRepository`, `MatchRepository`, etc.
- All repos have `upsert()` methods (insert or update based on `sofascore_id`)
- **Field Filtering**: Repositories automatically filter out unknown fields from API responses
- Eager loading support via `load_relations` parameter
- Prevents `TypeError` when API returns unexpected fields

### 4. Rate Limiting
- Navigation delays: 2-5 seconds (randomized)
- Page refresh: Every 5 minutes
- Backfill mode: 10 seconds between requests

### 5. Orchestrator Pattern
Coordinates multiple collectors:
- **Lifecycle Management**: Start/stop collectors across sports
- **Data Flow**: Interceptors → Parsers → Handlers → Repositories → Database
- **Auto-initialization**: Database + Browser Manager setup
- **Graceful Shutdown**: Cleanup all resources on exit
- **Status Monitoring**: Real-time collector status tracking

### 6. REST API Layer
FastAPI-based REST API for accessing collected data:
- **CORS-enabled** for cross-origin requests
- **OpenAPI docs** at `/docs` (Swagger UI) and `/redoc`
- **Health check** endpoint at `/health`
- **Structured routes**: `/live`, `/matches`, `/sports`, `/stats`

## Conventions

### Naming
- **Files/Modules**: `snake_case` (e.g., `live_tracker.py`)
- **Classes**: `PascalCase` (e.g., `LiveTracker`, `BaseCollector`)
- **Functions/Variables**: `snake_case` (e.g., `get_by_sofascore_id`)
- **Async Functions**: Prefixed with `async def` (all I/O operations are async)

### Type Hints
- Modern Python 3.14 syntax: `str | None` instead of `Optional[str]`
- Return types always specified
- Pydantic models for data validation

### Error Handling
- Use built-in logging module (`logging.getLogger(__name__)`)
- Collectors have automatic retry with exponential backoff (5 retries max)
- Graceful degradation - log errors but continue running
- API endpoints return proper HTTP status codes

### Testing
- Test files mirror `src/` structure: `tests/parsers/test_api_response.py`
- Use pytest fixtures from `conftest.py`
- Async tests use `@pytest.mark.asyncio`
- Mock external dependencies (browser, network)
- Mock data in `examples/mock_data/` for realistic testing

### Database
- All tables have `id`, `created_at`, `updated_at`
- Foreign keys reference SofaScore IDs (`sofascore_id` field)
- Use `upsert()` pattern to avoid duplicates
- Enums for constrained fields (`Sport`, `MatchStatus`)
- **Repository field filtering** prevents errors from API schema changes

## Environment Variables

Create a `.env` file:

```env
# Browser
HEADLESS=true

# Database
DATABASE_URL=sqlite:///data/sofascore.db

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO

# Sports to track
SPORTS=football,tennis,basketball,handball,volleyball

# Rate limiting
NAVIGATION_DELAY_MIN=2
NAVIGATION_DELAY_MAX=5
PAGE_REFRESH_INTERVAL=300
BACKFILL_DELAY=10

# API (optional)
API_HOST=0.0.0.0
API_PORT=8000
```

## Quick Reference

### Key Files
- `src/config.py` - Central configuration (loads from `.env`)
- `src/collectors/base.py` - Base class for all collectors
- `src/orchestrator/coordinator.py` - Multi-collector orchestration
- `src/storage/repositories.py` - Database CRUD with field filtering
- `src/api/main.py` - FastAPI application entry point
- `src/browser/README.md` - Browser module documentation
- `examples/orchestrator_usage.py` - Orchestrator usage examples
- `main.py` - Production entry point (uses orchestrator)

### API Endpoints
Once the API server is running (`uvicorn src.api.main:app`):
- `GET /` - API info and links
- `GET /health` - Health check with database status
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /live` - Live matches (all sports or filtered)
- `GET /matches` - Match history with filters
- `GET /sports/{sport}` - Teams and leagues for a sport
- `GET /stats/{match_id}` - Match statistics and incidents

### Interceptor Patterns
HTTP patterns matched:
- `live` - Live events
- `scheduled` - Scheduled events for a date
- `event` - Event/match details
- `statistics` - Match statistics
- `incidents` - Goals, cards, substitutions
- `lineups`, `h2h`, `odds`, `team`, `league`

### WebSocket Modes
- **Generic Mode**: All messages via `on_message(handler)`
- **Live Score Mode**: Specialized handlers for `on_score_update()` and `on_incident()`

### Database Schema
Core entities:
- `Sport` (enum), `Team`, `League`, `Match`
- `MatchStatistic`, `Incident` (goals, cards, etc.)
- All linked via `sofascore_id` foreign keys

Recent schema updates:
- `League.unique_tournament_slug` - Added for complete tournament info

## Development Workflow

### Using the Orchestrator (Recommended)

1. **Start the orchestrator**: Use `create_coordinator()` or context manager
2. **Add collectors**: Use `add_live_tracker()` or `add_daily_collector()`
3. **Monitor status**: Call `get_status()` to see running collectors
4. **Graceful shutdown**: Orchestrator handles cleanup automatically

```python
coordinator = await create_coordinator()

try:
    # Add live trackers for all sports
    await coordinator.add_live_trackers_for_all_sports()

    # Optional: Collect upcoming matches
    await coordinator.collect_upcoming_matches('football', days_ahead=7)

    # Run until interrupted
    await coordinator.run_forever()

finally:
    await coordinator.cleanup()
```

See `examples/orchestrator_usage.py` for complete patterns.

### Running the API Server

```bash
# Development mode (auto-reload)
uv run uvicorn src.api.main:app --reload

# Production mode
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Access API docs
open http://localhost:8000/docs
```

### Manual Collector Development

1. **Create a new collector**: Inherit from `BaseCollector`, implement `collect()`
2. **Setup interceptors**: Use `create_interceptor()` and `create_ws_interceptor()`
3. **Handle data**: Register handlers with `.on(pattern, handler)`
4. **Store data**: Use repositories to upsert parsed data
5. **Test**: Write async tests using pytest fixtures

See `examples/collector_usage.py` for manual collector patterns.

## Testing Strategy

The project has comprehensive test coverage (~4,883 lines of test code):

- **Browser Tests**: Browser manager, interceptors, WebSocket handling
- **Collector Tests**: Base collector, live tracker, daily events
- **Parser Tests**: API response parsing, WebSocket message parsing
- **Storage Tests**: Repository operations, field filtering, upsert logic
- **Orchestrator Tests**: Coordinator, handlers, lifecycle management

Run specific test suites:
```bash
uv run pytest tests/storage/     # Repository tests
uv run pytest tests/parsers/     # Parser tests
uv run pytest tests/collectors/  # Collector tests
```

## Recent Improvements

### Field Filtering in Repositories
Repositories now automatically filter out unknown fields when creating database records. This prevents `TypeError` exceptions when SofaScore API adds new fields that aren't in our models.

Example: When API returns `category_slug`, `category_id`, or `flag` fields not defined in `League` model, they're silently filtered out instead of causing errors.

### Database Schema Updates
- Added `League.unique_tournament_slug` field to match API responses
- Database migration handled automatically via SQLAlchemy
