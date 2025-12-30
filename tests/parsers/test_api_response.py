"""Tests for API response parser."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from src.parsers.api_response import (
    APIResponseParser,
    parse_scheduled_events,
    parse_live_events,
    parse_event_detail,
)


@pytest.fixture
def mock_data_dir():
    """Get path to mock data directory."""
    return Path(__file__).parent.parent.parent / "examples" / "mock_data"


@pytest.fixture
def scheduled_events_data(mock_data_dir):
    """Load scheduled events mock data."""
    with open(mock_data_dir / "scheduled_events.json") as f:
        return json.load(f)


@pytest.fixture
def live_events_data(mock_data_dir):
    """Load live events mock data."""
    with open(mock_data_dir / "live_events.json") as f:
        return json.load(f)


class TestAPIResponseParser:
    """Tests for APIResponseParser class."""

    def test_parse_team(self):
        """Test team parsing."""
        team_data = {
            "id": 17,
            "name": "Manchester City",
            "slug": "manchester-city",
            "shortName": "Man City",
            "nameCode": "MCI",
            "national": False,
            "userCount": 2845123,
            "gender": "M",
            "sport": {"slug": "football", "id": 1},
            "teamColors": {"primary": "#6cabdd", "secondary": "#ffffff"},
        }

        parsed = APIResponseParser.parse_team(team_data)

        assert parsed["sofascore_id"] == 17
        assert parsed["name"] == "Manchester City"
        assert parsed["slug"] == "manchester-city"
        assert parsed["short_name"] == "Man City"
        assert parsed["name_code"] == "MCI"
        assert parsed["national"] is False
        assert parsed["sport"] == "football"
        assert parsed["team_colors"]["primary"] == "#6cabdd"

    def test_parse_tournament(self):
        """Test tournament parsing."""
        tournament_data = {
            "id": 1,
            "name": "Premier League",
            "slug": "premier-league",
            "priority": 1,
            "uniqueTournament": {
                "id": 17,
                "name": "Premier League",
                "slug": "premier-league",
                "hasEventPlayerStatistics": True,
            },
            "category": {
                "id": 1,
                "name": "England",
                "slug": "england",
                "flag": "england",
                "sport": {"slug": "football"},
            },
        }

        parsed = APIResponseParser.parse_tournament(tournament_data)

        assert parsed["sofascore_id"] == 1
        assert parsed["name"] == "Premier League"
        assert parsed["unique_tournament_id"] == 17
        assert parsed["country"] == "England"
        assert parsed["sport"] == "football"
        assert parsed["has_player_statistics"] is True

    def test_parse_score(self):
        """Test score parsing."""
        score_data = {
            "current": 2,
            "display": 2,
            "period1": 1,
            "period2": 1,
            "normaltime": 2,
        }

        parsed = APIResponseParser.parse_score(score_data)

        assert parsed["current"] == 2
        assert parsed["display"] == 2
        assert parsed["period1"] == 1
        assert parsed["period2"] == 1
        assert parsed["normaltime"] == 2

    def test_parse_status(self):
        """Test status parsing."""
        status_data = {"code": 6, "description": "1st half", "type": "inprogress"}

        parsed = APIResponseParser.parse_status(status_data)

        assert parsed["code"] == 6
        assert parsed["description"] == "1st half"
        assert parsed["type"] == "inprogress"

    def test_parse_event_scheduled(self, scheduled_events_data):
        """Test parsing scheduled event."""
        event_data = scheduled_events_data["events"][0]
        parsed = APIResponseParser.parse_event(event_data)

        # Basic fields - test that fields exist and have expected types
        assert "sofascore_id" in parsed
        assert isinstance(parsed["sofascore_id"], int)
        assert "slug" in parsed
        assert isinstance(parsed["slug"], str)
        assert parsed["sport"] == "football"

        # Teams
        assert "home_team_name" in parsed
        assert "away_team_name" in parsed
        assert "home_team_id" in parsed
        assert "away_team_id" in parsed
        assert isinstance(parsed["home_team_id"], int)
        assert isinstance(parsed["away_team_id"], int)

        # Status
        assert "status_type" in parsed
        assert "status_code" in parsed
        assert isinstance(parsed["status_code"], int)

        # Tournament
        assert "league_name" in parsed or "tournament" in parsed

        # Verify no parsing errors
        assert "error" not in parsed

    def test_parse_event_live(self, live_events_data):
        """Test parsing live event."""
        event_data = live_events_data["events"][0]
        parsed = APIResponseParser.parse_event(event_data)

        # Basic fields
        assert "sofascore_id" in parsed
        assert isinstance(parsed["sofascore_id"], int)
        assert parsed["sport"] == "football"

        # Scores - should exist for live events
        assert "home_score_current" in parsed
        assert "away_score_current" in parsed
        assert isinstance(parsed["home_score_current"], int)
        assert isinstance(parsed["away_score_current"], int)

        # Status
        assert "status_type" in parsed
        assert "status_code" in parsed

        # Verify no parsing errors
        assert "error" not in parsed

    def test_parse_scheduled_events(self, scheduled_events_data):
        """Test parse_scheduled_events convenience function."""
        parsed_list = parse_scheduled_events(scheduled_events_data)

        # Should have at least one event
        assert len(parsed_list) > 0

        # Check first event has required fields
        first_event = parsed_list[0]
        assert "sofascore_id" in first_event
        assert "home_team_name" in first_event
        assert "away_team_name" in first_event
        assert "sport" in first_event

    def test_parse_live_events(self, live_events_data):
        """Test parse_live_events convenience function."""
        parsed_list = parse_live_events(live_events_data)

        # Should have at least one event
        assert len(parsed_list) > 0

        # Check first event has required fields
        first_event = parsed_list[0]
        assert "sofascore_id" in first_event
        assert "status_type" in first_event
        assert "home_score_current" in first_event
        assert "away_score_current" in first_event

    def test_parse_event_detail(self):
        """Test parse_event_detail convenience function."""
        event_detail_response = {
            "event": {
                "id": 12345,
                "slug": "test-match",
                "homeTeam": {"id": 1, "name": "Team A", "sport": {"slug": "football"}},
                "awayTeam": {"id": 2, "name": "Team B", "sport": {"slug": "football"}},
                "homeScore": {"current": 1},
                "awayScore": {"current": 0},
                "status": {"code": 100, "type": "finished"},
                "startTimestamp": 1735574400,
            }
        }

        parsed = parse_event_detail(event_detail_response)

        assert parsed["sofascore_id"] == 12345
        assert parsed["home_team_name"] == "Team A"
        assert parsed["status_type"] == "finished"

    def test_parse_events_list_empty(self):
        """Test parsing empty events list."""
        empty_response = {"events": []}
        parsed_list = APIResponseParser.parse_events_list(empty_response)

        assert isinstance(parsed_list, list)
        assert len(parsed_list) == 0

    def test_parse_event_missing_fields(self):
        """Test parsing event with missing optional fields."""
        minimal_event = {
            "id": 123,
            "slug": "minimal-match",
            "startTimestamp": 1735574400,
        }

        parsed = APIResponseParser.parse_event(minimal_event)

        assert parsed["sofascore_id"] == 123
        assert parsed["slug"] == "minimal-match"
        assert "error" not in parsed
        # Optional fields should be missing or have default values
        assert "home_team_name" not in parsed
