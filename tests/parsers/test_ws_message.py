"""WebSocket message parser tests."""

import json
from pathlib import Path

from src.parsers.ws_message import WebSocketMessageParser


def test_parse_score_update():
    """Test parsing WebSocket score update from mock data."""
    mock_file = Path("examples/mock_data/ws_score_update.json")
    with open(mock_file) as f:
        message = json.load(f)

    result = WebSocketMessageParser.parse_score_update(message)

    assert result["event_id"] == 11867890
    assert result["home_score"]["current"] == 3
    assert result["away_score"]["current"] == 1
    assert result["status"]["type"] == "inprogress"


def test_parse_incident():
    """Test parsing WebSocket incident from mock data."""
    mock_file = Path("examples/mock_data/ws_incident.json")
    with open(mock_file) as f:
        message = json.load(f)

    result = WebSocketMessageParser.parse_incident(message)

    assert result["event_id"] == 11867890
    assert result["incident_id"] == 987654321
    assert result["incident_type"] == "goal"
    assert result["player_name"] == "Vinícius Júnior"
    assert result["is_home"] is True
