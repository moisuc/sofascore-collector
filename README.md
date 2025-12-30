# SofaScore Collector

Live sports data collection system that captures SofaScore.com traffic via browser automation with REST API access.

## Features

- **Browser-Based Collection**: No direct API calls - navigates like a real user and intercepts network responses
- **Live Match Tracking**: Real-time scores, incidents, and statistics via WebSocket interception
- **Multi-Sport Support**: Football, tennis, basketball, handball, volleyball
- **SQLite Storage**: Structured data storage with SQLAlchemy ORM
- **REST API**: FastAPI-based API for accessing collected data
- **Comprehensive Testing**: 4,883 lines of test coverage

## Quick Start

### Installation

```bash
# Install dependencies
uv sync

# Install browser binaries
playwright install
```

### Configuration

Create a `.env` file:

```env
DATABASE_URL=sqlite:///data/sofascore.db
HEADLESS=true
SPORTS=football,tennis,basketball
LOG_LEVEL=INFO
```

### Running the Collector

```bash
# Start the orchestrator (collects live data)
uv run python main.py

# Start the REST API server
uv run uvicorn src.api.main:app --reload
```

Access API documentation at `http://localhost:8000/docs`

## Usage Example

```python
from src.orchestrator.coordinator import create_coordinator

# Create orchestrator
coordinator = await create_coordinator()

try:
    # Add live trackers for all configured sports
    await coordinator.add_live_trackers_for_all_sports()

    # Run until interrupted
    await coordinator.run_forever()
finally:
    await coordinator.cleanup()
```

## API Endpoints

- `GET /live` - Live matches across all sports
- `GET /matches` - Match history with filters
- `GET /sports/{sport}` - Teams and leagues
- `GET /stats/{match_id}` - Match statistics and incidents

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  Browser    │────▶│ Interceptors │────▶│ Parsers  │
│ (Playwright)│     │ HTTP/WS      │     │          │
└─────────────┘     └──────────────┘     └──────────┘
                                               │
                                               ▼
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  REST API   │◀────│  Database    │◀────│ Handlers │
│  (FastAPI)  │     │  (SQLite)    │     │          │
└─────────────┘     └──────────────┘     └──────────┘
```

## Development

```bash
# Run tests
uv run pytest

# Run specific test module
uv run pytest tests/parsers/

# Lint code
uv run ruff check .

# Format code
uv run ruff format .
```

## Project Structure

- `src/browser/` - Playwright automation + network interceptors
- `src/collectors/` - Data collection strategies
- `src/parsers/` - Response parsing logic
- `src/storage/` - Database models and repositories
- `src/orchestrator/` - Multi-collector coordination
- `src/api/` - FastAPI REST API
- `tests/` - Comprehensive test suite
- `examples/` - Usage examples with mock data

## Requirements

- Python 3.14+
- Playwright (for browser automation)
- SQLite (built-in)
- Redis (optional, for caching)

## How It Works

1. **Browser Automation**: Uses Playwright to navigate SofaScore.com like a real user
2. **Traffic Interception**: Captures HTTP responses and WebSocket messages
3. **Data Parsing**: Extracts structured data from intercepted traffic
4. **Storage**: Saves to SQLite with automatic deduplication
5. **API Access**: Exposes collected data via FastAPI endpoints

## License

MIT

## Contributing

Contributions welcome! Please check out the [project documentation](CLAUDE.md) for architecture details and conventions.
