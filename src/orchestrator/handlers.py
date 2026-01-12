"""Data handlers that bridge interceptors → parsers → database repositories."""

import logging
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.parsers.api_response import (
    parse_live_events,
    parse_scheduled_events,
    parse_featured_events,
    parse_inverse_events,
)
from src.parsers.ws_message import parse_score_update, parse_incident
from src.storage.database import get_session, MatchStatus
from src.storage.repositories import (
    TeamRepository,
    LeagueRepository,
    MatchRepository,
    IncidentRepository,
)
from src.storage.file_storage import FileStorageService
from src.config import settings

logger = logging.getLogger(__name__)


class DataHandler:
    """
    Handles data flow from interceptors through parsers to database.

    Provides handlers for:
    - Live events (HTTP)
    - Scheduled events (HTTP)
    - Score updates (WebSocket)
    - Incidents (WebSocket)
    """

    def __init__(self, session: Session | None = None):
        """
        Initialize data handler.

        Args:
            session: Optional SQLAlchemy session. If not provided, creates new session per operation.
        """
        self.session = session
        self._should_close_session = session is None

        # Initialize file storage if enabled
        if settings.file_storage_enabled:
            self.file_storage = FileStorageService(
                base_path=Path(settings.file_storage_base_path)
            )
        else:
            self.file_storage = None

    def _get_session(self) -> Session:
        """Get database session (create new if not provided in __init__)."""
        if self.session:
            return self.session
        return get_session()

    def _close_session_if_needed(self, session: Session | None) -> None:
        """Close session if we created it."""
        if self._should_close_session and session:
            session.close()

    async def handle_live_events(self, data: dict, match: re.Match) -> None:
        """
        Handle live events HTTP response.

        Parses live match data and stores to database.

        Args:
            data: JSON response data from /api/v1/sport/{sport}/events/live
            match: Regex match object containing URL groups
        """
        session = None
        try:
            sport = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"

            # Save raw response to file
            if self.file_storage:
                try:
                    date_str = datetime.now().strftime("%Y_%m_%d")
                    self.file_storage.save_response("live", sport, date_str, data)
                except Exception as e:
                    logger.error(f"Failed to save live response to file: {e}")

            # Parse events using existing parser
            parsed_events = parse_live_events(data)

            if not parsed_events:
                logger.debug(f"No live events to process for {sport}")
                return

            logger.info(f"Processing {len(parsed_events)} live events for {sport}")

            # Get database session
            session = self._get_session()

            # Initialize repositories
            team_repo = TeamRepository(session)
            league_repo = LeagueRepository(session)
            match_repo = MatchRepository(session)

            # Process each event
            processed_count = 0
            for event in parsed_events:
                try:
                    # Skip events with parsing errors
                    if "error" in event:
                        logger.warning(f"Skipping event with parse error: {event.get('error')}")
                        continue

                    # Upsert home team
                    if "home_team" in event:
                        home_team = team_repo.upsert(event["home_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing home team")
                        continue

                    # Upsert away team
                    if "away_team" in event:
                        away_team = team_repo.upsert(event["away_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing away team")
                        continue

                    # Upsert league/tournament
                    league = None
                    if "tournament" in event:
                        league = league_repo.upsert(event["tournament"])
                        session.flush()

                    # Prepare match data
                    match_data = {
                        "sofascore_id": event["sofascore_id"],
                        "slug": event.get("slug", f"match-{event['sofascore_id']}"),
                        "custom_id": event.get("custom_id"),
                        "sport": event.get("sport", sport),
                        "home_team_id": home_team.id,
                        "away_team_id": away_team.id,
                        "league_id": league.id if league else None,
                        "status": self._map_status_code(event.get("status_code", 0)),
                        "status_code": event.get("status_code", 0),
                        "home_score_current": event.get("home_score_current", 0),
                        "away_score_current": event.get("away_score_current", 0),
                        "start_timestamp": event["start_timestamp"],
                        "start_time": event["start_time"],
                        "season_name": event.get("season_name"),
                        "season_year": event.get("season_year"),
                        "round": event.get("round"),
                        "winner_code": event.get("winner_code", 0),
                        "has_xg": event.get("has_xg", False),
                        "has_highlights": event.get("has_highlights", False),
                        "has_player_statistics": event.get("has_player_statistics", False),
                        "has_heatmap": event.get("has_heatmap", False),
                        "time_data": event.get("time"),
                    }

                    # Add score details if available
                    if "home_score" in event:
                        match_data.update({
                            "home_score_period1": event["home_score"].get("period1"),
                            "home_score_period2": event["home_score"].get("period2"),
                            "home_score_overtime": event["home_score"].get("overtime"),
                            "home_score_penalties": event["home_score"].get("penalties"),
                        })

                    if "away_score" in event:
                        match_data.update({
                            "away_score_period1": event["away_score"].get("period1"),
                            "away_score_period2": event["away_score"].get("period2"),
                            "away_score_overtime": event["away_score"].get("overtime"),
                            "away_score_penalties": event["away_score"].get("penalties"),
                        })

                    # Upsert match
                    match_repo.upsert(match_data)
                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing live event {event.get('sofascore_id')}: {e}",
                        exc_info=True
                    )
                    # Continue processing other events
                    continue

            # Commit transaction
            session.commit()
            logger.info(f"Successfully processed {processed_count}/{len(parsed_events)} live events for {sport}")

        except Exception as e:
            logger.error(f"Error handling live events: {e}", exc_info=True)
            if session:
                session.rollback()
        finally:
            self._close_session_if_needed(session)

    async def handle_scheduled_events(self, data: dict, match: re.Match) -> None:
        """
        Handle scheduled events HTTP response.

        Parses scheduled match data and stores to database.

        Args:
            data: JSON response data from /api/v1/sport/{sport}/scheduled-events/{date}
            match: Regex match object containing URL groups (sport, date)
        """
        session = None
        try:
            sport = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"
            date_str = match.group(2) if match.lastindex and match.lastindex >= 2 else "unknown"

            # Save raw response to file
            if self.file_storage:
                try:
                    # Convert date format: 2025-01-12 -> 2025_01_12
                    date_str_formatted = date_str.replace("-", "_")
                    self.file_storage.save_response("scheduled", sport, date_str_formatted, data)
                except Exception as e:
                    logger.error(f"Failed to save scheduled response to file: {e}")

            # Parse events using existing parser
            parsed_events = parse_scheduled_events(data)

            if not parsed_events:
                logger.debug(f"No scheduled events to process for {sport} on {date_str}")
                return

            logger.info(f"Processing {len(parsed_events)} scheduled events for {sport} on {date_str}")

            # Get database session
            session = self._get_session()

            # Initialize repositories
            team_repo = TeamRepository(session)
            league_repo = LeagueRepository(session)
            match_repo = MatchRepository(session)

            # Process each event (same logic as live events)
            processed_count = 0
            for event in parsed_events:
                try:
                    # Skip events with parsing errors
                    if "error" in event:
                        logger.warning(f"Skipping event with parse error: {event.get('error')}")
                        continue

                    # Upsert home team
                    if "home_team" in event:
                        home_team = team_repo.upsert(event["home_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing home team")
                        continue

                    # Upsert away team
                    if "away_team" in event:
                        away_team = team_repo.upsert(event["away_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing away team")
                        continue

                    # Upsert league/tournament
                    league = None
                    if "tournament" in event:
                        league = league_repo.upsert(event["tournament"])
                        session.flush()

                    # Prepare match data
                    match_data = {
                        "sofascore_id": event["sofascore_id"],
                        "slug": event.get("slug", f"match-{event['sofascore_id']}"),
                        "custom_id": event.get("custom_id"),
                        "sport": event.get("sport", sport),
                        "home_team_id": home_team.id,
                        "away_team_id": away_team.id,
                        "league_id": league.id if league else None,
                        "status": self._map_status_code(event.get("status_code", 0)),
                        "status_code": event.get("status_code", 0),
                        "home_score_current": event.get("home_score_current", 0),
                        "away_score_current": event.get("away_score_current", 0),
                        "start_timestamp": event["start_timestamp"],
                        "start_time": event["start_time"],
                        "season_name": event.get("season_name"),
                        "season_year": event.get("season_year"),
                        "round": event.get("round"),
                        "winner_code": event.get("winner_code", 0),
                        "has_xg": event.get("has_xg", False),
                        "has_highlights": event.get("has_highlights", False),
                        "has_player_statistics": event.get("has_player_statistics", False),
                        "has_heatmap": event.get("has_heatmap", False),
                    }

                    # Add score details if available
                    if "home_score" in event:
                        match_data.update({
                            "home_score_period1": event["home_score"].get("period1"),
                            "home_score_period2": event["home_score"].get("period2"),
                            "home_score_overtime": event["home_score"].get("overtime"),
                            "home_score_penalties": event["home_score"].get("penalties"),
                        })

                    if "away_score" in event:
                        match_data.update({
                            "away_score_period1": event["away_score"].get("period1"),
                            "away_score_period2": event["away_score"].get("period2"),
                            "away_score_overtime": event["away_score"].get("overtime"),
                            "away_score_penalties": event["away_score"].get("penalties"),
                        })

                    # Upsert match
                    match_repo.upsert(match_data)
                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing scheduled event {event.get('sofascore_id')}: {e}",
                        exc_info=True
                    )
                    # Continue processing other events
                    continue

            # Commit transaction
            session.commit()
            logger.info(
                f"Successfully processed {processed_count}/{len(parsed_events)} "
                f"scheduled events for {sport} on {date_str}"
            )

        except Exception as e:
            logger.error(f"Error handling scheduled events: {e}", exc_info=True)
            if session:
                session.rollback()
        finally:
            self._close_session_if_needed(session)

    async def handle_featured_events(self, data: dict, match: re.Match) -> None:
        """
        Handle featured events HTTP response.

        Parses featured match data from odds endpoint and stores to database.

        Args:
            data: JSON response data from /api/v1/odds/{id}/featured-events/{sport}
            match: Regex match object containing URL groups
        """
        session = None
        try:
            sport = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"

            # Save raw response to file
            if self.file_storage:
                try:
                    date_str = datetime.now().strftime("%Y_%m_%d")
                    self.file_storage.save_response("featured", sport, date_str, data)
                except Exception as e:
                    logger.error(f"Failed to save featured response to file: {e}")

            # Parse events using parser
            parsed_events = parse_featured_events(data)

            if not parsed_events:
                logger.debug(f"No featured events to process for {sport}")
                return

            logger.info(f"Processing {len(parsed_events)} featured events for {sport}")

            # Get database session
            session = self._get_session()

            # Initialize repositories
            team_repo = TeamRepository(session)
            league_repo = LeagueRepository(session)
            match_repo = MatchRepository(session)

            # Process each event (same logic as live events)
            processed_count = 0
            for event in parsed_events:
                try:
                    # Skip events with parsing errors
                    if "error" in event:
                        logger.warning(f"Skipping event with parse error: {event.get('error')}")
                        continue

                    # Upsert home team
                    if "home_team" in event:
                        home_team = team_repo.upsert(event["home_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing home team")
                        continue

                    # Upsert away team
                    if "away_team" in event:
                        away_team = team_repo.upsert(event["away_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing away team")
                        continue

                    # Upsert league/tournament
                    league = None
                    if "tournament" in event:
                        league = league_repo.upsert(event["tournament"])
                        session.flush()

                    # Prepare match data
                    match_data = {
                        "sofascore_id": event["sofascore_id"],
                        "slug": event.get("slug", f"match-{event['sofascore_id']}"),
                        "custom_id": event.get("custom_id"),
                        "sport": event.get("sport", sport),
                        "home_team_id": home_team.id,
                        "away_team_id": away_team.id,
                        "league_id": league.id if league else None,
                        "status": self._map_status_code(event.get("status_code", 0)),
                        "status_code": event.get("status_code", 0),
                        "home_score_current": event.get("home_score_current", 0),
                        "away_score_current": event.get("away_score_current", 0),
                        "start_timestamp": event["start_timestamp"],
                        "start_time": event["start_time"],
                        "season_name": event.get("season_name"),
                        "season_year": event.get("season_year"),
                        "round": event.get("round"),
                        "winner_code": event.get("winner_code", 0),
                        "has_xg": event.get("has_xg", False),
                        "has_highlights": event.get("has_highlights", False),
                        "has_player_statistics": event.get("has_player_statistics", False),
                        "has_heatmap": event.get("has_heatmap", False),
                    }

                    # Add score details if available
                    if "home_score" in event:
                        match_data.update({
                            "home_score_period1": event["home_score"].get("period1"),
                            "home_score_period2": event["home_score"].get("period2"),
                            "home_score_overtime": event["home_score"].get("overtime"),
                            "home_score_penalties": event["home_score"].get("penalties"),
                        })

                    if "away_score" in event:
                        match_data.update({
                            "away_score_period1": event["away_score"].get("period1"),
                            "away_score_period2": event["away_score"].get("period2"),
                            "away_score_overtime": event["away_score"].get("overtime"),
                            "away_score_penalties": event["away_score"].get("penalties"),
                        })

                    # Upsert match
                    match_repo.upsert(match_data)
                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing featured event {event.get('sofascore_id')}: {e}",
                        exc_info=True
                    )
                    # Continue processing other events
                    continue

            # Commit transaction
            session.commit()
            logger.info(f"Successfully processed {processed_count}/{len(parsed_events)} featured events for {sport}")

        except Exception as e:
            logger.error(f"Error handling featured events: {e}", exc_info=True)
            if session:
                session.rollback()
        finally:
            self._close_session_if_needed(session)

    async def handle_inverse_events(self, data: dict, match: re.Match) -> None:
        """
        Handle inverse scheduled events HTTP response.

        Parses inverse scheduled match data and stores to database with is_inverse flag.

        Args:
            data: JSON response data from /api/v1/sport/{sport}/scheduled-events/{date}/inverse
            match: Regex match object containing URL groups (sport, date)
        """
        session = None
        try:
            sport = match.group(1) if match.lastindex and match.lastindex >= 1 else "unknown"
            date_str = match.group(2) if match.lastindex and match.lastindex >= 2 else "unknown"

            # Save raw response to file
            if self.file_storage:
                try:
                    # Convert date format: 2025-01-12 -> 2025_01_12
                    date_str_formatted = date_str.replace("-", "_")
                    self.file_storage.save_response("inverse", sport, date_str_formatted, data)
                except Exception as e:
                    logger.error(f"Failed to save inverse response to file: {e}")

            # Parse events using parser
            parsed_events = parse_inverse_events(data)

            if not parsed_events:
                logger.debug(f"No inverse events to process for {sport} on {date_str}")
                return

            logger.info(f"Processing {len(parsed_events)} inverse events for {sport} on {date_str}")

            # Get database session
            session = self._get_session()

            # Initialize repositories
            team_repo = TeamRepository(session)
            league_repo = LeagueRepository(session)
            match_repo = MatchRepository(session)

            # Process each event
            processed_count = 0
            for event in parsed_events:
                try:
                    # Skip events with parsing errors
                    if "error" in event:
                        logger.warning(f"Skipping event with parse error: {event.get('error')}")
                        continue

                    # Upsert home team
                    if "home_team" in event:
                        home_team = team_repo.upsert(event["home_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing home team")
                        continue

                    # Upsert away team
                    if "away_team" in event:
                        away_team = team_repo.upsert(event["away_team"])
                        session.flush()
                    else:
                        logger.warning(f"Event {event.get('sofascore_id')} missing away team")
                        continue

                    # Upsert league/tournament
                    league = None
                    if "tournament" in event:
                        league = league_repo.upsert(event["tournament"])
                        session.flush()

                    # Prepare match data with is_inverse=True
                    match_data = {
                        "sofascore_id": event["sofascore_id"],
                        "slug": event.get("slug", f"match-{event['sofascore_id']}"),
                        "custom_id": event.get("custom_id"),
                        "sport": event.get("sport", sport),
                        "home_team_id": home_team.id,
                        "away_team_id": away_team.id,
                        "league_id": league.id if league else None,
                        "status": self._map_status_code(event.get("status_code", 0)),
                        "status_code": event.get("status_code", 0),
                        "home_score_current": event.get("home_score_current", 0),
                        "away_score_current": event.get("away_score_current", 0),
                        "start_timestamp": event["start_timestamp"],
                        "start_time": event["start_time"],
                        "season_name": event.get("season_name"),
                        "season_year": event.get("season_year"),
                        "round": event.get("round"),
                        "winner_code": event.get("winner_code", 0),
                        "has_xg": event.get("has_xg", False),
                        "has_highlights": event.get("has_highlights", False),
                        "has_player_statistics": event.get("has_player_statistics", False),
                        "has_heatmap": event.get("has_heatmap", False),
                        "is_inverse": True,  # Mark as inverse event
                    }

                    # Add score details if available
                    if "home_score" in event:
                        match_data.update({
                            "home_score_period1": event["home_score"].get("period1"),
                            "home_score_period2": event["home_score"].get("period2"),
                            "home_score_overtime": event["home_score"].get("overtime"),
                            "home_score_penalties": event["home_score"].get("penalties"),
                        })

                    if "away_score" in event:
                        match_data.update({
                            "away_score_period1": event["away_score"].get("period1"),
                            "away_score_period2": event["away_score"].get("period2"),
                            "away_score_overtime": event["away_score"].get("overtime"),
                            "away_score_penalties": event["away_score"].get("penalties"),
                        })

                    # Upsert match
                    match_repo.upsert(match_data)
                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing inverse event {event.get('sofascore_id')}: {e}",
                        exc_info=True
                    )
                    # Continue processing other events
                    continue

            # Commit transaction
            session.commit()
            logger.info(
                f"Successfully processed {processed_count}/{len(parsed_events)} "
                f"inverse events for {sport} on {date_str}"
            )

        except Exception as e:
            logger.error(f"Error handling inverse events: {e}", exc_info=True)
            if session:
                session.rollback()
        finally:
            self._close_session_if_needed(session)

    async def handle_score_update(self, data: dict) -> None:
        """
        Handle WebSocket score update.

        Updates match score in database.

        Args:
            data: WebSocket message data (already parsed by ws_interceptor)
        """
        session = None
        try:
            # Parse score update
            parsed = parse_score_update(data)

            if "error" in parsed:
                logger.warning(f"Skipping score update with parse error: {parsed.get('error')}")
                return

            event_id = parsed.get("event_id")
            if not event_id:
                logger.warning("Score update missing event_id")
                return

            logger.debug(f"Processing score update for event {event_id}")

            # Get database session
            session = self._get_session()
            match_repo = MatchRepository(session)

            # Find match by sofascore_id
            match = match_repo.get_by_sofascore_id(event_id)

            if not match:
                logger.warning(f"Match not found for event_id {event_id}, skipping score update")
                return

            # Update scores
            if "home_score_current" in parsed:
                match.home_score_current = parsed["home_score_current"]

            if "away_score_current" in parsed:
                match.away_score_current = parsed["away_score_current"]

            # Update status if provided
            if "status_code" in parsed:
                match.status_code = parsed["status_code"]
                match.status = self._map_status_code(parsed["status_code"])

            # Update time data if provided
            if "time" in parsed:
                match.time_data = parsed["time"]

            # Commit changes
            session.commit()
            logger.debug(
                f"Updated score for match {event_id}: "
                f"{match.home_score_current}-{match.away_score_current}"
            )

        except Exception as e:
            logger.error(f"Error handling score update: {e}", exc_info=True)
            if session:
                session.rollback()
        finally:
            self._close_session_if_needed(session)

    async def handle_incident(self, data: dict) -> None:
        """
        Handle WebSocket incident (goal, card, substitution, etc.).

        Stores incident to database.

        Args:
            data: WebSocket message data (already parsed by ws_interceptor)
        """
        session = None
        try:
            # Parse incident
            parsed = parse_incident(data)

            if "error" in parsed:
                logger.warning(f"Skipping incident with parse error: {parsed.get('error')}")
                return

            event_id = parsed.get("event_id")
            incident_type = parsed.get("incident_type")

            if not event_id or not incident_type:
                logger.warning("Incident missing event_id or incident_type")
                return

            logger.info(f"Processing {incident_type} incident for event {event_id}")

            # Get database session
            session = self._get_session()
            match_repo = MatchRepository(session)
            incident_repo = IncidentRepository(session)

            # Find match
            match = match_repo.get_by_sofascore_id(event_id)

            if not match:
                logger.warning(f"Match not found for event_id {event_id}, skipping incident")
                return

            # Prepare incident data
            incident_data = {
                "match_id": match.id,
                "sofascore_incident_id": parsed.get("incident_id"),
                "incident_type": incident_type,
                "time": parsed.get("time", 0),
                "added_time": parsed.get("added_time"),
                "is_home": parsed.get("is_home", False),
                "player_id": parsed.get("player_id"),
                "player_name": parsed.get("player_name"),
            }

            # Add type-specific fields
            if incident_type == "goal":
                incident_data.update({
                    "scoring_team": parsed.get("scoring_team"),
                    "home_score": parsed.get("home_score"),
                    "away_score": parsed.get("away_score"),
                    "goal_description": parsed.get("goal_description"),
                })
            elif incident_type in ("card", "yellowCard", "redCard"):
                incident_data["card_type"] = parsed.get("card_type", "yellow")
            elif incident_type == "substitution":
                incident_data.update({
                    "player_in_id": parsed.get("player_in_id"),
                    "player_in_name": parsed.get("player_in", {}).get("name"),
                    "player_out_id": parsed.get("player_out_id"),
                    "player_out_name": parsed.get("player_out", {}).get("name"),
                })

            # Upsert incident
            incident_repo.upsert(incident_data)

            # Commit changes
            session.commit()
            logger.debug(f"Saved {incident_type} incident for match {event_id}")

        except Exception as e:
            logger.error(f"Error handling incident: {e}", exc_info=True)
            if session:
                session.rollback()
        finally:
            self._close_session_if_needed(session)

    @staticmethod
    def _map_status_code(status_code: int) -> MatchStatus:
        """
        Map SofaScore status code to MatchStatus enum.

        Args:
            status_code: SofaScore status code

        Returns:
            MatchStatus enum value
        """
        # Common status codes from SofaScore
        status_map = {
            0: MatchStatus.SCHEDULED,
            6: MatchStatus.LIVE,  # Not started
            7:MatchStatus.LIVE,
            17: MatchStatus.LIVE,  # 1st period
            31: MatchStatus.LIVE,  # 1st half
            41: MatchStatus.LIVE,  # 2nd half
            60: MatchStatus.LIVE,  # Halftime
            70: MatchStatus.LIVE,  # Extra time
            100: MatchStatus.FINISHED,
            110: MatchStatus.FINISHED,  # After ET
            120: MatchStatus.FINISHED,  # After penalties
            90: MatchStatus.POSTPONED,
            91: MatchStatus.CANCELLED,
            92: MatchStatus.INTERRUPTED,
            93: MatchStatus.ABANDONED,
        }

        return status_map.get(status_code, MatchStatus.SCHEDULED)


# Convenience function to create handler with shared session
def create_handler(session: Session | None = None) -> DataHandler:
    """
    Create a DataHandler instance.

    Args:
        session: Optional SQLAlchemy session to share across handlers

    Returns:
        DataHandler instance
    """
    return DataHandler(session)
