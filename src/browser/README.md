# Browser Module

Module for browser automation and network interception using Playwright.

## Components

### BrowserManager ([manager.py](manager.py))

Manages Playwright browser instances with support for:
- Multiple isolated browser contexts (one per sport)
- Automatic page refresh to maintain connections
- Proper cleanup and resource management
- Async context manager support

**Example:**
```python
async with BrowserManager(headless=True) as browser:
    context = await browser.create_context("football")
    page = await browser.new_page("football")

    # Start periodic refresh
    await browser.refresh_page_periodically(page, interval=300)

    await page.goto('https://www.sofascore.com/football/livescore')
```

### ResponseInterceptor ([interceptor.py](interceptor.py))

Intercepts HTTP responses matching SofaScore API patterns:
- `scheduled` - Scheduled events for a date
- `live` - Live events
- `event` - Event details
- `statistics` - Match statistics
- `incidents` - Match incidents (goals, cards, etc.)
- `lineups` - Team lineups
- `h2h` - Head-to-head records
- `odds` - Betting odds
- `team` - Team details
- `league` - League/tournament details

**Example:**
```python
async def handle_live_matches(data: dict, match: re.Match) -> None:
    sport = match.group(1)
    events = data.get('events', [])
    print(f"Live matches for {sport}: {len(events)}")

interceptor = await create_interceptor(page)
interceptor.on('live', handle_live_matches)
```

### WebSocketInterceptor ([ws_interceptor.py](ws_interceptor.py))

Intercepts WebSocket messages for real-time updates:
- Generic message handling
- Specialized live score mode with score and incident handlers
- Automatic connection tracking

**Example:**
```python
async def handle_score_update(data: dict) -> None:
    print(f"Score update: {data}")

ws_interceptor = await create_ws_interceptor(page, live_score_mode=True)
ws_interceptor.on_score_update(handle_score_update)
```

## Key Principles

1. **No Direct API Calls** - We navigate pages like a real user and intercept responses
2. **Isolated Contexts** - Each sport gets its own browser context
3. **Async Throughout** - All operations are async for performance
4. **Error Resilience** - Graceful error handling with logging

## Usage Pattern

```python
from src.browser import BrowserManager, create_interceptor, create_ws_interceptor

async def main():
    async with BrowserManager(headless=True) as browser:
        # Create context and page
        page = await browser.new_page("football")

        # Setup interceptors
        http_interceptor = await create_interceptor(page)
        http_interceptor.on('live', my_http_handler)

        ws_interceptor = await create_ws_interceptor(page)
        ws_interceptor.on_message(my_ws_handler)

        # Navigate and collect
        await page.goto('https://www.sofascore.com/football/livescore')

        # Keep running
        await asyncio.sleep(3600)  # 1 hour
```

See [examples/browser_usage.py](../../examples/browser_usage.py) for complete examples.
