# CLAUDE.md - SofaScore Collector

## Project Overview

Un sistem de colectare date sportive de pe SofaScore folosind Playwright pentru interceptarea request-urilor și WebSocket-urilor. Datele sunt stocate în SQLite și expuse prin FastAPI.

**Abordare cheie**: Nu facem request-uri directe la API. Navigăm pe pagini ca un user real și interceptăm răspunsurile pe care pagina le primește singură. Aceasta previne blocking-ul.

## Tech Stack

- **Python 3.11+**
- **UV** - Package manager (NU pip)
- **Playwright** - Browser automation + interception
- **FastAPI** - API endpoints
- **SQLAlchemy 2.0** - ORM (async-ready)
- **SQLite** - Storage (poate fi migrat la PostgreSQL)
- **Redis** - Cache pentru live data (opțional)
- **Pydantic v2** - Validare și serialization

## Project Structure
```
sofascore-collector/
├── pyproject.toml          # Dependencies și config
├── uv.lock                  # Lock file (auto-generat)
├── CLAUDE.md               # Acest fișier
├── Makefile                # Comenzi convenience
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point collector
│   ├── config.py           # Settings cu pydantic-settings
│   ├── browser/
│   │   ├── __init__.py
│   │   ├── manager.py      # Browser pool management
│   │   ├── interceptor.py  # HTTP response interceptor
│   │   └── ws_interceptor.py  # WebSocket interceptor
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract base collector
│   │   ├── live_tracker.py # Stă pe pagina live
│   │   └── daily_events.py # Navighează pe zile
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── api_response.py # Parse API JSON
│   │   └── ws_message.py   # Parse WS messages
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py     # SQLAlchemy models
│   │   └── repositories.py # CRUD operations
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── coordinator.py  # Coordonează collectors
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI app
│   │   ├── dependencies.py # DB session injection
│   │   ├── schemas.py      # Pydantic response models
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── matches.py
│   │       ├── live.py
│   │       ├── sports.py
│   │       └── stats.py
│   └── models/
│       ├── __init__.py
│       └── schemas.py      # Shared Pydantic models
├── data/
│   └── sofascore.db        # SQLite database
└── tests/
    └── ...
```

## Commands
```bash
# Install dependencies
uv sync
uv run playwright install chromium

# Run collector (interceptează date de pe SofaScore)
uv run python -m src.main

# Run API server
uv run uvicorn src.api.main:app --reload --port 8000

# Run both (în terminale separate)
make collector  # Terminal 1
make api        # Terminal 2

# Tests
uv run pytest -v

# Lint & format
uv run ruff check src/
uv run ruff format src/
```

## Architecture Principles

### 1. Playwright Interception (NU direct API calls)
```python
# ✅ CORECT - Interceptăm ce face pagina
page.on('response', handle_response)
await page.goto('https://www.sofascore.com/football/livescore')

# ❌ GREȘIT - Request direct la API
httpx.get('https://api.sofascore.com/api/v1/...')
```

### 2. Patterns de Interes pentru Interceptare
```python
PATTERNS = {
    'scheduled': r'/api/v1/sport/(\w+)/scheduled-events/(\d{4}-\d{2}-\d{2})',
    'live': r'/api/v1/sport/(\w+)/events/live',
}
```

### 3. Sports Supported

- `football`
- `tennis`
- `basketball`
- `handball`
- `volleyball`

### 4. Match Status Flow
```
SCHEDULED → LIVE → FINISHED
                → POSTPONED
                → CANCELLED
```

## Database Schema

### Core Tables

- **matches** - Meciuri (sofascore_id, sport, teams, score, status, start_time)
- **teams** - Echipe (sofascore_id, name, sport, country)
- **leagues** - Competiții (sofascore_id, name, sport, country)
- **match_statistics** - Statistici post-meci
- **incidents** - Evenimente (goluri, cartonașe, etc.)

### Key Indexes
```sql
CREATE INDEX ix_matches_sport_status ON matches(sport, status);
CREATE INDEX ix_matches_sport_date ON matches(sport, start_time);
CREATE UNIQUE INDEX ix_matches_sofascore_id ON matches(sofascore_id);
```

## API Endpoints

| Method | Endpoint | Descriere |
|--------|----------|-----------|
| GET | `/live` | Toate meciurile live |
| GET | `/live/{sport}` | Live per sport |
| GET | `/matches` | Meciuri cu filtre (sport, status, date, team) |
| GET | `/matches/{id}` | Detalii meci |
| GET | `/sports` | Lista sporturi |
| GET | `/sports/{sport}/today` | Meciuri de azi |
| GET | `/sports/{sport}/upcoming` | Meciuri viitoare |
| GET | `/sports/{sport}/finished` | Meciuri terminate |
| GET | `/sports/{sport}/leagues` | Ligi per sport |
| GET | `/stats/match/{id}` | Statistici meci |
| GET | `/stats/summary` | Sumar DB |

## Coding Conventions

### Python Style

- **Ruff** pentru linting și formatting
- Line length: 100
- Type hints obligatorii pentru funcții publice
- Docstrings pentru clase și funcții complexe

### Async/Await

- Tot codul Playwright este async
- Folosim `asyncio.gather()` pentru paralelism
- `asyncio.Queue()` pentru comunicare între componente

### Pydantic Models
```python
# Response models în src/api/schemas.py
class MatchList(BaseModel):
    id: int
    sofascore_id: int
    sport: SportEnum
    # ...
    
    class Config:
        from_attributes = True  # Pentru SQLAlchemy
```

### Repository Pattern
```python
# Fiecare entitate are repository în src/storage/repositories.py
class MatchRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def upsert_match(self, data: dict) -> Match: ...
    def get_live(self, sport: str = None) -> list[Match]: ...
```

## Important Implementation Notes

### Browser Manager

- Rulează headless în producție
- Un browser context per sport pentru izolare
- Refresh periodic (5 min) pentru a menține conexiunea

### WebSocket Handling

- Pagina deschide WS automat
- Interceptăm cu `page.on('websocket', handler)`
- Ascultăm `framereceived` pentru updates

### Error Handling

- Retry cu exponential backoff pentru network errors
- Graceful degradation dacă un sport fail-uiește
- Logging comprehensiv

### Rate Limiting (Self-Imposed)

- Delay între navigări: 2-5 secunde
- Refresh pages: la 5 minute
- Backfill historic: 10 secunde între requests

## Environment Variables
```bash
# .env
HEADLESS=true
DATABASE_URL=sqlite:///data/sofascore.db
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
```

## Testing
```python
# tests/test_interceptor.py
@pytest.mark.asyncio
async def test_api_interceptor_captures_matches():
    # ...
```

## Deployment Notes

- Playwright necesită browsere instalate (`playwright install chromium`)
- În Docker, trebuie dependențe sistem pentru Chromium
- SQLite funcționează pentru volum mic/mediu
- Pentru scale, migrează la PostgreSQL + connection pooling

## Common Tasks

### Adaugă un sport nou

1. Adaugă în `Sport` enum (`storage/database.py`)
2. Adaugă URL în `LivePageCollector.LIVE_URLS`
3. Adaugă în `SPORTS` list din `config.py`

### Adaugă un endpoint nou

1. Creează route în `src/api/routes/`
2. Adaugă response schema în `src/api/schemas.py`
3. Include router în `src/api/main.py`

### Adaugă statistică nouă

1. Identifică pattern-ul API din DevTools
2. Adaugă în `PATTERNS` dict
3. Creează parser în `src/parsers/`
4. Adaugă model dacă e nevoie

## Troubleshooting

### Browser crashes
```python
# Mărește timeout-ul
await page.goto(url, timeout=60000)
```

### Missing data

- Verifică că pagina s-a încărcat complet (`wait_until='networkidle'`)
- Scroll pentru lazy-loaded content
- Verifică pattern-urile de interceptare

### Database locked (SQLite)

- Folosește un singur writer
- Sau migrează la PostgreSQL