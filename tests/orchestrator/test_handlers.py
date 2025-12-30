"""Tests for DataHandler."""

import pytest
import re
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from src.orchestrator.handlers import DataHandler, create_handler
from src.storage.database import MatchStatus


@pytest.mark.asyncio
class TestDataHandler:
    """Test cases for DataHandler."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        session.flush = MagicMock()
        session.close = MagicMock()
        return session

    @pytest.fixture
    def handler(self, mock_session):
        """Create a DataHandler with mock session."""
        return DataHandler(session=mock_session)

    def test_create_handler(self):
        """Test create_handler convenience function."""
        handler = create_handler()
        assert handler is not None
        assert handler.session is None

    def test_create_handler_with_session(self, mock_session):
        """Test create_handler with provided session."""
        handler = create_handler(session=mock_session)
        assert handler.session == mock_session

    async def test_handle_live_events_empty(self, handler, mock_session):
        """Test handling empty live events response."""
        data = {"events": []}
        match = re.match(r"/api/v1/sport/(football)/events/live", "/api/v1/sport/football/events/live")

        with patch("src.orchestrator.handlers.parse_live_events", return_value=[]):
            await handler.handle_live_events(data, match)

        # Should not commit if no events
        mock_session.commit.assert_not_called()

    async def test_handle_live_events_with_data(self, handler, mock_session):
        """Test handling live events with actual data."""
        data = {"events": [{"id": 123}]}
        match = re.match(r"/api/v1/sport/(football)/events/live", "/api/v1/sport/football/events/live")

        parsed_event = {
            "sofascore_id": 123,
            "slug": "match-123",
            "sport": "football",
            "start_timestamp": 1234567890,
            "start_time": datetime.fromtimestamp(1234567890),
            "status_code": 100,
            "home_team": {
                "sofascore_id": 1,
                "name": "Team A",
                "slug": "team-a",
                "sport": "football",
            },
            "away_team": {
                "sofascore_id": 2,
                "name": "Team B",
                "slug": "team-b",
                "sport": "football",
            },
            "tournament": {
                "sofascore_id": 10,
                "name": "League",
                "slug": "league",
                "sport": "football",
            },
            "home_score_current": 2,
            "away_score_current": 1,
        }

        with patch("src.orchestrator.handlers.parse_live_events", return_value=[parsed_event]), \
             patch("src.orchestrator.handlers.TeamRepository") as mock_team_repo, \
             patch("src.orchestrator.handlers.LeagueRepository") as mock_league_repo, \
             patch("src.orchestrator.handlers.MatchRepository") as mock_match_repo:

            # Setup mock repositories
            mock_team = MagicMock()
            mock_team.id = 1
            mock_away_team = MagicMock()
            mock_away_team.id = 2
            mock_league = MagicMock()
            mock_league.id = 10

            mock_team_repo.return_value.upsert.side_effect = [mock_team, mock_away_team]
            mock_league_repo.return_value.upsert.return_value = mock_league
            mock_match_repo.return_value.upsert.return_value = MagicMock()

            await handler.handle_live_events(data, match)

            # Verify commit was called
            mock_session.commit.assert_called_once()

            # Verify repositories were used
            assert mock_team_repo.return_value.upsert.call_count == 2
            mock_league_repo.return_value.upsert.assert_called_once()
            mock_match_repo.return_value.upsert.assert_called_once()

    async def test_handle_live_events_with_error(self, handler, mock_session):
        """Test handling live events with parsing error."""
        data = {"events": [{"id": 123}]}
        match = re.match(r"/api/v1/sport/(football)/events/live", "/api/v1/sport/football/events/live")

        parsed_event = {
            "error": "Parse error",
            "sofascore_id": 123,
        }

        with patch("src.orchestrator.handlers.parse_live_events", return_value=[parsed_event]):
            await handler.handle_live_events(data, match)

        # Should not process events with errors
        mock_session.commit.assert_not_called()

    async def test_handle_scheduled_events(self, handler, mock_session):
        """Test handling scheduled events."""
        data = {"events": [{"id": 456}]}
        match = re.match(
            r"/api/v1/sport/(football)/scheduled-events/(2024-12-30)",
            "/api/v1/sport/football/scheduled-events/2024-12-30"
        )

        parsed_event = {
            "sofascore_id": 456,
            "slug": "match-456",
            "sport": "football",
            "start_timestamp": 1234567890,
            "start_time": datetime.fromtimestamp(1234567890),
            "status_code": 0,
            "home_team": {
                "sofascore_id": 3,
                "name": "Team C",
                "slug": "team-c",
                "sport": "football",
            },
            "away_team": {
                "sofascore_id": 4,
                "name": "Team D",
                "slug": "team-d",
                "sport": "football",
            },
            "home_score_current": 0,
            "away_score_current": 0,
        }

        with patch("src.orchestrator.handlers.parse_scheduled_events", return_value=[parsed_event]), \
             patch("src.orchestrator.handlers.TeamRepository") as mock_team_repo, \
             patch("src.orchestrator.handlers.LeagueRepository"), \
             patch("src.orchestrator.handlers.MatchRepository") as mock_match_repo:

            mock_team = MagicMock()
            mock_team.id = 3
            mock_away_team = MagicMock()
            mock_away_team.id = 4

            mock_team_repo.return_value.upsert.side_effect = [mock_team, mock_away_team]
            mock_match_repo.return_value.upsert.return_value = MagicMock()

            await handler.handle_scheduled_events(data, match)

            mock_session.commit.assert_called_once()

    async def test_handle_score_update(self, handler, mock_session):
        """Test handling WebSocket score update."""
        data = {
            "type": "scoreUpdate",
            "data": {
                "eventId": 123,
                "homeScore": {"current": 3},
                "awayScore": {"current": 2},
            }
        }

        parsed = {
            "event_id": 123,
            "home_score_current": 3,
            "away_score_current": 2,
            "status_code": 100,
        }

        with patch("src.orchestrator.handlers.parse_score_update", return_value=parsed), \
             patch("src.orchestrator.handlers.MatchRepository") as mock_match_repo:

            mock_match = MagicMock()
            mock_match.home_score_current = 2
            mock_match.away_score_current = 1
            mock_match_repo.return_value.get_by_sofascore_id.return_value = mock_match

            await handler.handle_score_update(data)

            # Verify match was updated
            assert mock_match.home_score_current == 3
            assert mock_match.away_score_current == 2
            mock_session.commit.assert_called_once()

    async def test_handle_score_update_match_not_found(self, handler, mock_session):
        """Test handling score update when match not found."""
        data = {
            "type": "scoreUpdate",
            "data": {"eventId": 999}
        }

        parsed = {
            "event_id": 999,
            "home_score_current": 1,
            "away_score_current": 1,
        }

        with patch("src.orchestrator.handlers.parse_score_update", return_value=parsed), \
             patch("src.orchestrator.handlers.MatchRepository") as mock_match_repo:

            mock_match_repo.return_value.get_by_sofascore_id.return_value = None

            await handler.handle_score_update(data)

            # Should not commit if match not found
            mock_session.commit.assert_not_called()

    async def test_handle_incident(self, handler, mock_session):
        """Test handling WebSocket incident."""
        data = {
            "type": "incident",
            "data": {
                "eventId": 123,
                "incident": {
                    "id": 1001,
                    "type": "goal",
                    "time": 45,
                },
            }
        }

        parsed = {
            "event_id": 123,
            "incident_id": 1001,
            "incident_type": "goal",
            "time": 45,
            "is_home": True,
            "player_id": 50,
            "player_name": "John Doe",
        }

        with patch("src.orchestrator.handlers.parse_incident", return_value=parsed), \
             patch("src.orchestrator.handlers.MatchRepository") as mock_match_repo, \
             patch("src.orchestrator.handlers.IncidentRepository") as mock_incident_repo:

            mock_match = MagicMock()
            mock_match.id = 123
            mock_match_repo.return_value.get_by_sofascore_id.return_value = mock_match
            mock_incident_repo.return_value.upsert.return_value = MagicMock()

            await handler.handle_incident(data)

            mock_incident_repo.return_value.upsert.assert_called_once()
            mock_session.commit.assert_called_once()

    async def test_handle_incident_match_not_found(self, handler, mock_session):
        """Test handling incident when match not found."""
        data = {
            "type": "incident",
            "data": {
                "eventId": 999,
                "incident": {"type": "goal"},
            }
        }

        parsed = {
            "event_id": 999,
            "incident_type": "goal",
        }

        with patch("src.orchestrator.handlers.parse_incident", return_value=parsed), \
             patch("src.orchestrator.handlers.MatchRepository") as mock_match_repo:

            mock_match_repo.return_value.get_by_sofascore_id.return_value = None

            await handler.handle_incident(data)

            # Should not commit if match not found
            mock_session.commit.assert_not_called()

    def test_map_status_code(self):
        """Test status code mapping."""
        handler = DataHandler()

        assert handler._map_status_code(0) == MatchStatus.SCHEDULED
        assert handler._map_status_code(6) == MatchStatus.SCHEDULED
        assert handler._map_status_code(17) == MatchStatus.LIVE
        assert handler._map_status_code(31) == MatchStatus.LIVE
        assert handler._map_status_code(100) == MatchStatus.FINISHED
        assert handler._map_status_code(90) == MatchStatus.POSTPONED
        assert handler._map_status_code(91) == MatchStatus.CANCELLED
        assert handler._map_status_code(999) == MatchStatus.SCHEDULED  # Unknown defaults to scheduled

    async def test_session_management_without_provided_session(self):
        """Test that handler creates and closes session when not provided."""
        handler = DataHandler(session=None)

        with patch("src.orchestrator.handlers.get_session") as mock_get_session, \
             patch("src.orchestrator.handlers.parse_live_events", return_value=[]):

            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            data = {"events": []}
            match = re.match(r"/api/v1/sport/(football)/events/live", "/api/v1/sport/football/events/live")

            await handler.handle_live_events(data, match)

            # Session should be created and closed
            mock_get_session.assert_called_once()
            mock_session.close.assert_called_once()

    async def test_error_handling_rollback(self, mock_session):
        """Test that errors trigger rollback."""
        handler = DataHandler(session=mock_session)

        data = {"events": [{"id": 123}]}
        match = re.match(r"/api/v1/sport/(football)/events/live", "/api/v1/sport/football/events/live")

        # Make parse_live_events raise an exception
        with patch("src.orchestrator.handlers.parse_live_events", side_effect=Exception("Test error")):
            await handler.handle_live_events(data, match)

            # Should rollback on error
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()
