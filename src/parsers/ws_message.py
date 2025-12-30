"""Parser for SofaScore WebSocket messages."""

import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSocketMessageParser:
    """
    Parser for SofaScore WebSocket real-time messages.

    Handles parsing of various WebSocket message types:
    - Score updates (scoreChange, scoreUpdate)
    - Incidents (goal, card, substitution, etc.)
    - Status changes
    - Time updates
    """

    # Message type mappings
    SCORE_UPDATE_TYPES = {"scoreChange", "scoreUpdate", "score"}
    INCIDENT_TYPES = {"incident", "incidentChange", "newIncident"}
    STATUS_TYPES = {"statusChange", "status"}

    @staticmethod
    def parse_score_data(score_data: dict) -> dict[str, Any]:
        """
        Parse score data from WebSocket message.

        Args:
            score_data: Score data object

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
    def parse_status_data(status_data: dict) -> dict[str, Any]:
        """
        Parse status data from WebSocket message.

        Args:
            status_data: Status data object

        Returns:
            Parsed status dictionary
        """
        return {
            "code": status_data.get("code"),
            "description": status_data.get("description"),
            "type": status_data.get("type"),
        }

    @staticmethod
    def parse_time_data(time_data: dict) -> dict[str, Any]:
        """
        Parse time data from WebSocket message.

        Args:
            time_data: Time data object

        Returns:
            Parsed time dictionary
        """
        return {
            "current_period_start": time_data.get("currentPeriodStartTimestamp", 0),
            "initial": time_data.get("initial", 0),
            "max": time_data.get("max", 0),
            "extra": time_data.get("extra", 0),
            "injury_time": time_data.get("injuryTime", 0),
        }

    @classmethod
    def parse_score_update(cls, message: dict) -> dict[str, Any]:
        """
        Parse a score update WebSocket message.

        Args:
            message: Raw WebSocket message

        Returns:
            Parsed score update dictionary
        """
        try:
            message_type = message.get("type", "")
            data = message.get("data", {})

            parsed = {
                "message_type": message_type,
                "event_id": data.get("eventId"),
                "timestamp": message.get("timestamp", 0),
                "received_at": datetime.now(),
            }

            # Parse scores
            if "homeScore" in data:
                parsed["home_score"] = cls.parse_score_data(data["homeScore"])
                parsed["home_score_current"] = data["homeScore"].get("current", 0)

            if "awayScore" in data:
                parsed["away_score"] = cls.parse_score_data(data["awayScore"])
                parsed["away_score_current"] = data["awayScore"].get("current", 0)

            # Parse status
            if "status" in data:
                parsed["status"] = cls.parse_status_data(data["status"])
                parsed["status_code"] = data["status"].get("code")
                parsed["status_type"] = data["status"].get("type")

            # Parse time
            if "time" in data:
                parsed["time"] = cls.parse_time_data(data["time"])

            return parsed

        except Exception as e:
            logger.error(f"Error parsing score update: {e}", exc_info=True)
            return {"error": str(e), "raw_message": message}

    @staticmethod
    def parse_player(player_data: dict) -> dict[str, Any]:
        """
        Parse player data from incident.

        Args:
            player_data: Player data object

        Returns:
            Parsed player dictionary
        """
        return {
            "sofascore_id": player_data.get("id"),
            "name": player_data.get("name"),
            "slug": player_data.get("slug"),
            "short_name": player_data.get("shortName"),
            "position": player_data.get("position"),
        }

    @classmethod
    def parse_incident(cls, message: dict) -> dict[str, Any]:
        """
        Parse an incident WebSocket message (goal, card, substitution, etc.).

        Args:
            message: Raw WebSocket message

        Returns:
            Parsed incident dictionary
        """
        try:
            message_type = message.get("type", "")
            data = message.get("data", {})
            incident = data.get("incident", {})

            parsed = {
                "message_type": message_type,
                "event_id": data.get("eventId"),
                "timestamp": message.get("timestamp", 0),
                "received_at": datetime.now(),
                "incident_id": incident.get("id"),
                "incident_type": incident.get("type"),
                "time": incident.get("time"),
                "added_time": incident.get("addedTime"),
                "is_home": incident.get("isHome", False),
            }

            # Parse player (if present)
            if "player" in incident:
                parsed["player"] = cls.parse_player(incident["player"])
                parsed["player_id"] = incident["player"].get("id")
                parsed["player_name"] = incident["player"].get("name")

            # Parse assist player (if present - for goals)
            if "assist1" in incident:
                parsed["assist_player"] = cls.parse_player(incident["assist1"])
                parsed["assist_player_id"] = incident["assist1"].get("id")

            # Goal-specific fields
            if incident.get("type") == "goal":
                parsed["scoring_team"] = incident.get("scoringTeam")
                parsed["home_score"] = incident.get("homeScore")
                parsed["away_score"] = incident.get("awayScore")
                parsed["goal_description"] = incident.get("goalDescription")
                parsed["incident_class"] = incident.get("incidentClass")

            # Card-specific fields
            if incident.get("type") in ("card", "yellowCard", "redCard"):
                parsed["card_type"] = incident.get("incidentClass", "yellow")
                parsed["reason"] = incident.get("reason")

            # Substitution-specific fields
            if incident.get("type") == "substitution":
                if "playerIn" in incident:
                    parsed["player_in"] = cls.parse_player(incident["playerIn"])
                    parsed["player_in_id"] = incident["playerIn"].get("id")

                if "playerOut" in incident:
                    parsed["player_out"] = cls.parse_player(incident["playerOut"])
                    parsed["player_out_id"] = incident["playerOut"].get("id")

            return parsed

        except Exception as e:
            logger.error(f"Error parsing incident: {e}", exc_info=True)
            return {"error": str(e), "raw_message": message}

    @classmethod
    def parse_message(cls, message: dict) -> dict[str, Any]:
        """
        Parse any WebSocket message and route to appropriate parser.

        Args:
            message: Raw WebSocket message

        Returns:
            Parsed message dictionary
        """
        try:
            message_type = message.get("type", "")

            # Route to specific parser based on type
            if message_type in cls.SCORE_UPDATE_TYPES:
                return cls.parse_score_update(message)
            elif message_type in cls.INCIDENT_TYPES:
                return cls.parse_incident(message)
            elif message_type in cls.STATUS_TYPES:
                # Status changes can be handled like score updates
                return cls.parse_score_update(message)
            else:
                # Unknown message type - return with basic parsing
                logger.debug(f"Unknown WebSocket message type: {message_type}")
                return {
                    "message_type": message_type,
                    "timestamp": message.get("timestamp", 0),
                    "received_at": datetime.now(),
                    "data": message.get("data", {}),
                    "raw_message": message,
                }

        except Exception as e:
            logger.error(f"Error parsing WebSocket message: {e}", exc_info=True)
            return {"error": str(e), "raw_message": message}

    @staticmethod
    def is_score_update(message: dict) -> bool:
        """
        Check if message is a score update.

        Args:
            message: WebSocket message

        Returns:
            True if message is a score update
        """
        return message.get("type", "") in WebSocketMessageParser.SCORE_UPDATE_TYPES

    @staticmethod
    def is_incident(message: dict) -> bool:
        """
        Check if message is an incident.

        Args:
            message: WebSocket message

        Returns:
            True if message is an incident
        """
        return message.get("type", "") in WebSocketMessageParser.INCIDENT_TYPES

    @staticmethod
    def is_status_change(message: dict) -> bool:
        """
        Check if message is a status change.

        Args:
            message: WebSocket message

        Returns:
            True if message is a status change
        """
        return message.get("type", "") in WebSocketMessageParser.STATUS_TYPES


# Convenience functions
def parse_ws_message(message: dict) -> dict[str, Any]:
    """
    Parse any WebSocket message.

    Args:
        message: Raw WebSocket message

    Returns:
        Parsed message dictionary
    """
    return WebSocketMessageParser.parse_message(message)


def parse_score_update(message: dict) -> dict[str, Any]:
    """
    Parse a score update WebSocket message.

    Args:
        message: WebSocket message with score update

    Returns:
        Parsed score update dictionary
    """
    return WebSocketMessageParser.parse_score_update(message)


def parse_incident(message: dict) -> dict[str, Any]:
    """
    Parse an incident WebSocket message.

    Args:
        message: WebSocket message with incident data

    Returns:
        Parsed incident dictionary
    """
    return WebSocketMessageParser.parse_incident(message)
