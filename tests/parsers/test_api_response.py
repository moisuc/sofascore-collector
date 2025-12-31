"""API response parser tests."""

import json
from pathlib import Path

from src.parsers.api_response import parse_live_events, parse_scheduled_events


def test_parse_live_events():
    """Test parsing live events from mock data."""
    mock_file = Path("examples/mock_data/live_events.json")
    with open(mock_file) as f:
        data = json.load(f)

    events = parse_live_events(data)

    assert isinstance(events, list)
    assert len(events) > 0
    assert "sofascore_id" in events[0]
    assert "home_team" in events[0]
    assert "away_team" in events[0]


def test_parse_scheduled_events():
    """Test parsing scheduled events from mock data."""
    mock_file = Path("examples/mock_data/scheduled_events.json")
    with open(mock_file) as f:
        data = json.load(f)

    events = parse_scheduled_events(data)

    assert isinstance(events, list)
    assert len(events) > 0
    assert "sofascore_id" in events[0]
    assert "tournament" in events[0]
