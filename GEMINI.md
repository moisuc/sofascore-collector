# GEMINI.md

## Project Overview

This project is a sports data collection system named "SofaScore Collector". It utilizes browser automation (Playwright) to navigate SofaScore.com, intercepting network traffic (both HTTP and WebSockets) to capture live sports data. The collected data is then parsed and stored in a SQLite database using SQLAlchemy.

The project provides a REST API built with FastAPI to expose the collected data. The API offers endpoints for accessing live matches, match history, sports information, and detailed statistics.

The application is designed to be configurable, allowing users to specify which sports to track, whether to run the browser in headless mode, and other operational parameters through a `.env` file.

## Key Technologies

*   **Backend:** Python
*   **Frameworks:** FastAPI, SQLAlchemy, Playwright
*   **Database:** SQLite
*   **Testing:** pytest
*   **Linting/Formatting:** ruff

## Building and Running

### Installation

1.  **Install dependencies:**
    ```bash
    uv sync
    ```
2.  **Install browser binaries:**
    ```bash
    playwright install
    ```

### Configuration

Create a `.env` file in the project root with the following content:

```env
DATABASE_URL=sqlite:///data/sofascore.db
HEADLESS=true
SPORTS=football,tennis,basketball
LOG_LEVEL=INFO
```

### Running the Application

1.  **Start the data collector:**
    ```bash
    uv run python main.py
    ```
    This will start the orchestrator which collects live data.

2.  **Start the REST API server:**
    ```bash
    uv run uvicorn src.api.main:app --reload
    ```
    The API documentation will be available at `http://localhost:8000/docs`.

## Development Conventions

### Testing

The project uses `pytest` for testing.

*   **Run all tests:**
    ```bash
    uv run pytest
    ```
*   **Run tests for a specific module:**
    ```bash
    uv run pytest tests/parsers/
    ```

### Linting and Formatting

The project uses `ruff` for linting and code formatting.

*   **Check for linting errors:**
    ```bash
    uv run ruff check .
    ```
*   **Format the code:**
    ```bash
    uv run ruff format .
    ```
