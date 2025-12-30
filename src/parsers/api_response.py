"""Parser for SofaScore API HTTP responses."""

import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


class APIResponseParser:
    """
    Parser for SofaScore API responses.

    Handles parsing of various API endpoints:
    - Scheduled events
    - Live events
    - Event details
    - Statistics
    - Incidents
    - Lineups
    """

    @staticmethod
    def parse_team(team_data: dict) -> dict[str, Any]:
        """
        Parse team data from API response.

        Args:
            team_data: Raw team data from API

        Returns:
            Parsed team dictionary with normalized fields
        """
        return {
            "sofascore_id": team_data.get("id"),
            "name": team_data.get("name"),
            "slug": team_data.get("slug"),
            "short_name": team_data.get("shortName"),
            "name_code": team_data.get("nameCode"),
            "national": team_data.get("national", False),
            "user_count": team_data.get("userCount", 0),
            "gender": team_data.get("gender"),
            "sport": team_data.get("sport", {}).get("slug"),
            "team_colors": team_data.get("teamColors", {}),
        }

    @staticmethod
    def parse_tournament(tournament_data: dict) -> dict[str, Any]:
        """
        Parse tournament/league data from API response.

        Args:
            tournament_data: Raw tournament data from API

        Returns:
            Parsed tournament dictionary
        """
        unique_tournament = tournament_data.get("uniqueTournament", {})
        category = tournament_data.get("category", {})

        return {
            "sofascore_id": tournament_data.get("id"),
            "name": tournament_data.get("name"),
            "slug": tournament_data.get("slug"),
            "priority": tournament_data.get("priority"),
            "unique_tournament_id": unique_tournament.get("id"),
            "unique_tournament_name": unique_tournament.get("name"),
            "unique_tournament_slug": unique_tournament.get("slug"),
            "category_name": category.get("name"),
            "category_slug": category.get("slug"),
            "category_id": category.get("id"),
            "country": category.get("name"),
            "flag": category.get("flag"),
            "sport": category.get("sport", {}).get("slug"),
            "has_player_statistics": unique_tournament.get(
                "hasEventPlayerStatistics", False
            ),
            "has_performance_graph": unique_tournament.get(
                "hasPerformanceGraphFeature", False
            ),
        }

    @staticmethod
    def parse_score(score_data: dict) -> dict[str, Any]:
        """
        Parse score data.

        Args:
            score_data: Raw score data from API

        Returns:
            Parsed score dictionary
        """
        return {
            "current": score_data.get("current", 0),
            "display": score_data.get("display", 0),
            "period1": score_data.get("period1", 0),
            "period2": score_data.get("period2", 0),
            "normaltime": score_data.get("normaltime", 0),
            "overtime": score_data.get("overtime"),
            "penalties": score_data.get("penalties"),
        }

    @staticmethod
    def parse_status(status_data: dict) -> dict[str, Any]:
        """
        Parse match status.

        Args:
            status_data: Raw status data from API

        Returns:
            Parsed status dictionary
        """
        return {
            "code": status_data.get("code"),
            "description": status_data.get("description"),
            "type": status_data.get("type"),
        }

    @staticmethod
    def parse_event(event_data: dict) -> dict[str, Any]:
        """
        Parse a single event/match from API response.

        Args:
            event_data: Raw event data from API

        Returns:
            Parsed event dictionary with all relevant fields
        """
        try:
            # Basic match info
            parsed = {
                "sofascore_id": event_data.get("id"),
                "slug": event_data.get("slug"),
                "custom_id": event_data.get("customId"),
                "start_timestamp": event_data.get("startTimestamp"),
                "start_time": datetime.fromtimestamp(
                    event_data.get("startTimestamp", 0)
                )
                if event_data.get("startTimestamp")
                else None,
            }

            # Status
            if "status" in event_data:
                parsed["status"] = APIResponseParser.parse_status(event_data["status"])
                parsed["status_code"] = event_data["status"].get("code")
                parsed["status_type"] = event_data["status"].get("type")

            # Teams
            if "homeTeam" in event_data:
                parsed["home_team"] = APIResponseParser.parse_team(
                    event_data["homeTeam"]
                )
                parsed["home_team_id"] = event_data["homeTeam"].get("id")
                parsed["home_team_name"] = event_data["homeTeam"].get("name")

            if "awayTeam" in event_data:
                parsed["away_team"] = APIResponseParser.parse_team(
                    event_data["awayTeam"]
                )
                parsed["away_team_id"] = event_data["awayTeam"].get("id")
                parsed["away_team_name"] = event_data["awayTeam"].get("name")

            # Scores
            if "homeScore" in event_data:
                parsed["home_score"] = APIResponseParser.parse_score(
                    event_data["homeScore"]
                )
                parsed["home_score_current"] = event_data["homeScore"].get("current", 0)

            if "awayScore" in event_data:
                parsed["away_score"] = APIResponseParser.parse_score(
                    event_data["awayScore"]
                )
                parsed["away_score_current"] = event_data["awayScore"].get("current", 0)

            # Tournament
            if "tournament" in event_data:
                parsed["tournament"] = APIResponseParser.parse_tournament(
                    event_data["tournament"]
                )
                parsed["tournament_id"] = event_data["tournament"].get("id")
                parsed["league_name"] = event_data["tournament"].get("name")

            # Season
            if "season" in event_data:
                parsed["season_name"] = event_data["season"].get("name")
                parsed["season_year"] = event_data["season"].get("year")
                parsed["season_id"] = event_data["season"].get("id")

            # Round info
            if "roundInfo" in event_data:
                parsed["round"] = event_data["roundInfo"].get("round")

            # Additional flags
            parsed["winner_code"] = event_data.get("winnerCode", 0)
            parsed["has_xg"] = event_data.get("hasXg", False)
            parsed["has_highlights"] = event_data.get("hasGlobalHighlights", False)
            parsed["has_player_statistics"] = event_data.get(
                "hasEventPlayerStatistics", False
            )
            parsed["has_heatmap"] = event_data.get("hasEventPlayerHeatMap", False)
            parsed["final_result_only"] = event_data.get("finalResultOnly", False)

            # Time info (for live matches)
            if "time" in event_data:
                time_data = event_data["time"]
                parsed["time"] = {
                    "injury_time_1": time_data.get("injuryTime1", 0),
                    "injury_time_2": time_data.get("injuryTime2", 0),
                    "current_period_start": time_data.get(
                        "currentPeriodStartTimestamp", 0
                    ),
                    "initial": time_data.get("initial", 0),
                    "max": time_data.get("max", 0),
                    "extra": time_data.get("extra", 0),
                }

            # Changes (for live updates)
            if "changes" in event_data:
                parsed["changes"] = event_data["changes"].get("changes", [])
                parsed["change_timestamp"] = event_data["changes"].get(
                    "changeTimestamp", 0
                )

            # Sport (extract from nested structure)
            sport_slug = None
            if "homeTeam" in event_data and "sport" in event_data["homeTeam"]:
                sport_slug = event_data["homeTeam"]["sport"].get("slug")
            elif "tournament" in event_data:
                sport_slug = (
                    event_data["tournament"]
                    .get("category", {})
                    .get("sport", {})
                    .get("slug")
                )

            parsed["sport"] = sport_slug

            return parsed

        except Exception as e:
            logger.error(f"Error parsing event: {e}", exc_info=True)
            return {"error": str(e), "raw_data": event_data}

    @classmethod
    def parse_events_list(cls, response_data: dict) -> list[dict[str, Any]]:
        """
        Parse a list of events from API response.

        Args:
            response_data: API response containing 'events' array

        Returns:
            List of parsed event dictionaries
        """
        events = response_data.get("events", [])
        parsed_events = []

        for event_data in events:
            parsed_event = cls.parse_event(event_data)
            parsed_events.append(parsed_event)

        logger.debug(f"Parsed {len(parsed_events)} events from API response")
        return parsed_events


# Convenience functions
def parse_scheduled_events(response_data: dict) -> list[dict[str, Any]]:
    """
    Parse scheduled events API response.

    Args:
        response_data: Response from /api/v1/sport/{sport}/scheduled-events/{date}

    Returns:
        List of parsed scheduled events
    """
    return APIResponseParser.parse_events_list(response_data)


def parse_live_events(response_data: dict) -> list[dict[str, Any]]:
    """
    Parse live events API response.

    Args:
        response_data: Response from /api/v1/sport/{sport}/events/live

    Returns:
        List of parsed live events
    """
    return APIResponseParser.parse_events_list(response_data)


def parse_event_detail(response_data: dict) -> dict[str, Any]:
    """
    Parse single event detail API response.

    Args:
        response_data: Response from /api/v1/event/{id}

    Returns:
        Parsed event dictionary
    """
    # Event detail response has 'event' key instead of 'events'
    event_data = response_data.get("event", response_data)
    return APIResponseParser.parse_event(event_data)
