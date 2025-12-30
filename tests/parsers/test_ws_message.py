"""Tests for WebSocket message parser."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from src.parsers.ws_message import (
    WebSocketMessageParser,
    parse_ws_message,
    parse_score_update,
    parse_incident,
)


@pytest.fixture
def mock_data_dir():
    """Get path to mock data directory."""
    return Path(__file__).parent.parent.parent / "examples" / "mock_data"


@pytest.fixture
def ws_score_update_data(mock_data_dir):
    """Load WebSocket score update mock data."""
    with open(mock_data_dir / "ws_score_update.json") as f:
        return json.load(f)


@pytest.fixture
def ws_incident_data(mock_data_dir):
    """Load WebSocket incident mock data."""
    with open(mock_data_dir / "ws_incident.json") as f:
        return json.load(f)


class TestWebSocketMessageParser:
    """Tests for WebSocketMessageParser class."""

    def test_parse_score_data(self):
        """Test score data parsing."""
        score_data = {
            "current": 3,
            "display": 3,
            "period1": 2,
            "period2": 1,
            "normaltime": 3,
        }

        parsed = WebSocketMessageParser.parse_score_data(score_data)

        assert parsed["current"] == 3
        assert parsed["display"] == 3
        assert parsed["period1"] == 2
        assert parsed["period2"] == 1
        assert parsed["normaltime"] == 3

    def test_parse_status_data(self):
        """Test status data parsing."""
        status_data = {"code": 7, "description": "2nd half", "type": "inprogress"}

        parsed = WebSocketMessageParser.parse_status_data(status_data)

        assert parsed["code"] == 7
        assert parsed["description"] == "2nd half"
        assert parsed["type"] == "inprogress"

    def test_parse_time_data(self):
        """Test time data parsing."""
        time_data = {
            "currentPeriodStartTimestamp": 1735577100,
            "initial": 2700,
            "max": 5400,
            "extra": 0,
        }

        parsed = WebSocketMessageParser.parse_time_data(time_data)

        assert parsed["current_period_start"] == 1735577100
        assert parsed["initial"] == 2700
        assert parsed["max"] == 5400
        assert parsed["extra"] == 0

    def test_parse_score_update(self, ws_score_update_data):
        """Test parsing score update WebSocket message."""
        parsed = WebSocketMessageParser.parse_score_update(ws_score_update_data)

        # Basic fields
        assert parsed["message_type"] == "scoreChange"
        assert parsed["event_id"] == 11867890
        assert parsed["timestamp"] == 1735578456

        # Scores
        assert parsed["home_score_current"] == 3
        assert parsed["away_score_current"] == 1
        assert parsed["home_score"]["period1"] == 2
        assert parsed["home_score"]["period2"] == 1

        # Status
        assert parsed["status_code"] == 7
        assert parsed["status_type"] == "inprogress"

        # Time
        assert "time" in parsed
        assert parsed["time"]["initial"] == 2700

        # Timestamp
        assert "received_at" in parsed
        assert isinstance(parsed["received_at"], datetime)

    def test_parse_player(self):
        """Test player parsing."""
        player_data = {
            "id": 854499,
            "name": "Vinícius Júnior",
            "slug": "vinicius-junior",
            "shortName": "Vinícius Jr.",
            "position": "F",
        }

        parsed = WebSocketMessageParser.parse_player(player_data)

        assert parsed["sofascore_id"] == 854499
        assert parsed["name"] == "Vinícius Júnior"
        assert parsed["short_name"] == "Vinícius Jr."
        assert parsed["position"] == "F"

    def test_parse_incident_goal(self, ws_incident_data):
        """Test parsing goal incident WebSocket message."""
        parsed = WebSocketMessageParser.parse_incident(ws_incident_data)

        # Basic fields
        assert parsed["message_type"] == "incident"
        assert parsed["event_id"] == 11867890
        assert parsed["timestamp"] == 1735578456

        # Incident details
        assert parsed["incident_id"] == 987654321
        assert parsed["incident_type"] == "goal"
        assert parsed["time"] == 67
        assert parsed["is_home"] is True

        # Player
        assert parsed["player_name"] == "Vinícius Júnior"
        assert parsed["player_id"] == 854499

        # Goal-specific
        assert parsed["scoring_team"] == "home"
        assert parsed["home_score"] == 3
        assert parsed["away_score"] == 1
        assert parsed["goal_description"] == "Regular goal"
        assert parsed["incident_class"] == "regular"

        # Timestamp
        assert "received_at" in parsed

    def test_parse_message_score_update(self, ws_score_update_data):
        """Test parse_message routing for score update."""
        parsed = WebSocketMessageParser.parse_message(ws_score_update_data)

        assert parsed["message_type"] == "scoreChange"
        assert parsed["event_id"] == 11867890
        assert "home_score" in parsed
        assert "away_score" in parsed

    def test_parse_message_incident(self, ws_incident_data):
        """Test parse_message routing for incident."""
        parsed = WebSocketMessageParser.parse_message(ws_incident_data)

        assert parsed["message_type"] == "incident"
        assert parsed["incident_type"] == "goal"
        assert "player_name" in parsed

    def test_parse_message_unknown_type(self):
        """Test parse_message with unknown message type."""
        unknown_message = {
            "type": "unknownType",
            "data": {"someField": "someValue"},
            "timestamp": 1735578456,
        }

        parsed = WebSocketMessageParser.parse_message(unknown_message)

        assert parsed["message_type"] == "unknownType"
        assert "data" in parsed
        assert "raw_message" in parsed

    def test_is_score_update(self, ws_score_update_data):
        """Test is_score_update helper."""
        assert WebSocketMessageParser.is_score_update(ws_score_update_data) is True

        non_score_message = {"type": "incident"}
        assert WebSocketMessageParser.is_score_update(non_score_message) is False

    def test_is_incident(self, ws_incident_data):
        """Test is_incident helper."""
        assert WebSocketMessageParser.is_incident(ws_incident_data) is True

        non_incident_message = {"type": "scoreChange"}
        assert WebSocketMessageParser.is_incident(non_incident_message) is False

    def test_is_status_change(self):
        """Test is_status_change helper."""
        status_message = {"type": "statusChange"}
        assert WebSocketMessageParser.is_status_change(status_message) is True

        non_status_message = {"type": "incident"}
        assert WebSocketMessageParser.is_status_change(non_status_message) is False

    def test_convenience_function_parse_ws_message(self, ws_score_update_data):
        """Test parse_ws_message convenience function."""
        parsed = parse_ws_message(ws_score_update_data)

        assert parsed["message_type"] == "scoreChange"
        assert "event_id" in parsed

    def test_convenience_function_parse_score_update(self, ws_score_update_data):
        """Test parse_score_update convenience function."""
        parsed = parse_score_update(ws_score_update_data)

        assert parsed["message_type"] == "scoreChange"
        assert parsed["home_score_current"] == 3

    def test_convenience_function_parse_incident(self, ws_incident_data):
        """Test parse_incident convenience function."""
        parsed = parse_incident(ws_incident_data)

        assert parsed["incident_type"] == "goal"
        assert parsed["player_name"] == "Vinícius Júnior"

    def test_parse_incident_substitution(self):
        """Test parsing substitution incident."""
        substitution_message = {
            "type": "incident",
            "data": {
                "eventId": 12345,
                "incident": {
                    "id": 111222,
                    "type": "substitution",
                    "time": 75,
                    "isHome": True,
                    "playerIn": {
                        "id": 100,
                        "name": "Player In",
                        "shortName": "P. In",
                    },
                    "playerOut": {
                        "id": 200,
                        "name": "Player Out",
                        "shortName": "P. Out",
                    },
                },
            },
            "timestamp": 1735578456,
        }

        parsed = parse_incident(substitution_message)

        assert parsed["incident_type"] == "substitution"
        assert parsed["player_in_id"] == 100
        assert parsed["player_out_id"] == 200
        assert parsed["player_in"]["name"] == "Player In"
        assert parsed["player_out"]["name"] == "Player Out"

    def test_parse_incident_card(self):
        """Test parsing card incident."""
        card_message = {
            "type": "incident",
            "data": {
                "eventId": 12345,
                "incident": {
                    "id": 333444,
                    "type": "yellowCard",
                    "time": 45,
                    "addedTime": 2,
                    "isHome": False,
                    "player": {"id": 300, "name": "Bad Player", "shortName": "B. Player"},
                    "incidentClass": "yellow",
                    "reason": "Foul",
                },
            },
            "timestamp": 1735578456,
        }

        parsed = parse_incident(card_message)

        assert parsed["incident_type"] == "yellowCard"
        assert parsed["card_type"] == "yellow"
        assert parsed["reason"] == "Foul"
        assert parsed["added_time"] == 2
        assert parsed["player_name"] == "Bad Player"
