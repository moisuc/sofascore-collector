"""Repository pattern for database CRUD operations."""

import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from .database import Match, Team, League, MatchStatistic, Incident, Sport, MatchStatus

logger = logging.getLogger(__name__)


class TeamRepository:
    """Repository for Team CRUD operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def get_by_id(self, team_id: int) -> Optional[Team]:
        """Get team by internal ID."""
        return self.session.get(Team, team_id)

    def get_by_sofascore_id(self, sofascore_id: int) -> Optional[Team]:
        """Get team by SofaScore ID."""
        stmt = select(Team).where(Team.sofascore_id == sofascore_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_slug(self, slug: str, sport: str) -> Optional[Team]:
        """Get team by slug and sport."""
        stmt = select(Team).where(and_(Team.slug == slug, Team.sport == Sport(sport)))
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(self, team_data: dict) -> Team:
        """
        Insert or update team.

        Args:
            team_data: Dictionary with team data (must include sofascore_id)

        Returns:
            Team instance
        """
        sofascore_id = team_data.get("sofascore_id")
        if not sofascore_id:
            raise ValueError("sofascore_id is required for upsert")

        # Check if team exists
        team = self.get_by_sofascore_id(sofascore_id)

        if team:
            # Update existing team
            for key, value in team_data.items():
                if hasattr(team, key) and key not in ("id", "created_at"):
                    setattr(team, key, value)
            team.updated_at = datetime.utcnow()
            logger.debug(f"Updated team: {team.name} (sofascore_id={sofascore_id})")
        else:
            # Create new team - filter to only valid fields
            filtered_data = {
                key: value
                for key, value in team_data.items()
                if hasattr(Team, key) and key not in ("id", "created_at")
            }
            team = Team(**filtered_data)
            self.session.add(team)
            logger.debug(f"Created new team: {team.name} (sofascore_id={sofascore_id})")

        self.session.flush()
        return team

    def get_all(
        self, sport: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> list[Team]:
        """Get all teams with optional filtering."""
        stmt = select(Team)

        if sport:
            stmt = stmt.where(Team.sport == Sport(sport))

        stmt = stmt.limit(limit).offset(offset).order_by(Team.name)
        return list(self.session.execute(stmt).scalars().all())


class LeagueRepository:
    """Repository for League CRUD operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def get_by_id(self, league_id: int) -> Optional[League]:
        """Get league by internal ID."""
        return self.session.get(League, league_id)

    def get_by_sofascore_id(self, sofascore_id: int) -> Optional[League]:
        """Get league by SofaScore ID."""
        stmt = select(League).where(League.sofascore_id == sofascore_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(self, league_data: dict) -> League:
        """
        Insert or update league.

        Args:
            league_data: Dictionary with league data (must include sofascore_id)

        Returns:
            League instance
        """
        sofascore_id = league_data.get("sofascore_id")
        if not sofascore_id:
            raise ValueError("sofascore_id is required for upsert")

        # Check if league exists
        league = self.get_by_sofascore_id(sofascore_id)

        if league:
            # Update existing league
            for key, value in league_data.items():
                if hasattr(league, key) and key not in ("id", "created_at"):
                    setattr(league, key, value)
            league.updated_at = datetime.utcnow()
            logger.debug(f"Updated league: {league.name} (sofascore_id={sofascore_id})")
        else:
            # Create new league - filter to only valid fields
            filtered_data = {
                key: value
                for key, value in league_data.items()
                if hasattr(League, key) and key not in ("id", "created_at")
            }
            league = League(**filtered_data)
            self.session.add(league)
            logger.debug(
                f"Created new league: {league.name} (sofascore_id={sofascore_id})"
            )

        self.session.flush()
        return league

    def get_all(
        self, sport: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> list[League]:
        """Get all leagues with optional filtering."""
        stmt = select(League)

        if sport:
            stmt = stmt.where(League.sport == Sport(sport))

        stmt = stmt.limit(limit).offset(offset).order_by(League.name)
        return list(self.session.execute(stmt).scalars().all())


class MatchRepository:
    """Repository for Match CRUD operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def get_by_id(self, match_id: int, load_relations: bool = False) -> Optional[Match]:
        """
        Get match by internal ID.

        Args:
            match_id: Internal match ID
            load_relations: If True, eagerly load teams and league

        Returns:
            Match instance or None
        """
        stmt = select(Match).where(Match.id == match_id)

        if load_relations:
            stmt = stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_sofascore_id(
        self, sofascore_id: int, load_relations: bool = False
    ) -> Optional[Match]:
        """Get match by SofaScore ID."""
        stmt = select(Match).where(Match.sofascore_id == sofascore_id)

        if load_relations:
            stmt = stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(self, match_data: dict) -> Match:
        """
        Insert or update match.

        Args:
            match_data: Dictionary with match data (must include sofascore_id)

        Returns:
            Match instance
        """
        sofascore_id = match_data.get("sofascore_id")
        if not sofascore_id:
            raise ValueError("sofascore_id is required for upsert")

        # Check if match exists
        match = self.get_by_sofascore_id(sofascore_id)

        if match:
            # Update existing match
            for key, value in match_data.items():
                if hasattr(match, key) and key not in ("id", "created_at"):
                    setattr(match, key, value)
            match.updated_at = datetime.utcnow()
            logger.debug(f"Updated match: {match.slug} (sofascore_id={sofascore_id})")
        else:
            # Create new match - filter to only valid fields
            filtered_data = {
                key: value
                for key, value in match_data.items()
                if hasattr(Match, key) and key not in ("id", "created_at")
            }
            match = Match(**filtered_data)
            self.session.add(match)
            logger.debug(
                f"Created new match: {match.slug} (sofascore_id={sofascore_id})"
            )

        self.session.flush()
        return match

    def get_live(
        self, sport: Optional[str] = None, load_relations: bool = True
    ) -> list[Match]:
        """
        Get all live matches.

        Args:
            sport: Optional sport filter
            load_relations: If True, eagerly load teams and league

        Returns:
            List of live matches
        """
        stmt = select(Match).where(Match.status == MatchStatus.LIVE)

        if sport:
            stmt = stmt.where(Match.sport == Sport(sport))

        if load_relations:
            stmt = stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

        stmt = stmt.order_by(Match.start_time)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_date(
        self,
        target_date: date,
        sport: Optional[str] = None,
        status: Optional[str] = None,
        load_relations: bool = True,
    ) -> list[Match]:
        """
        Get matches for a specific date.

        Args:
            target_date: Date to query
            sport: Optional sport filter
            status: Optional status filter
            load_relations: If True, eagerly load teams and league

        Returns:
            List of matches
        """
        # Convert date to datetime range
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())

        stmt = select(Match).where(
            and_(Match.start_time >= start_dt, Match.start_time <= end_dt)
        )

        if sport:
            stmt = stmt.where(Match.sport == Sport(sport))

        if status:
            stmt = stmt.where(Match.status == MatchStatus(status))

        if load_relations:
            stmt = stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

        stmt = stmt.order_by(Match.start_time)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_team(
        self,
        team_id: int,
        sport: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Match]:
        """Get matches for a specific team."""
        stmt = select(Match).where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
        )

        if sport:
            stmt = stmt.where(Match.sport == Sport(sport))

        if status:
            stmt = stmt.where(Match.status == MatchStatus(status))

        stmt = (
            stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )
            .order_by(desc(Match.start_time))
            .limit(limit)
        )

        return list(self.session.execute(stmt).scalars().all())

    def get_upcoming(
        self,
        sport: Optional[str] = None,
        limit: int = 100,
        load_relations: bool = True,
    ) -> list[Match]:
        """Get upcoming scheduled matches."""
        now = datetime.utcnow()

        stmt = select(Match).where(
            and_(
                Match.status == MatchStatus.SCHEDULED,
                Match.start_time > now,
            )
        )

        if sport:
            stmt = stmt.where(Match.sport == Sport(sport))

        if load_relations:
            stmt = stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

        stmt = stmt.order_by(asc(Match.start_time)).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_finished(
        self,
        sport: Optional[str] = None,
        limit: int = 100,
        load_relations: bool = True,
    ) -> list[Match]:
        """Get recent finished matches."""
        stmt = select(Match).where(Match.status == MatchStatus.FINISHED)

        if sport:
            stmt = stmt.where(Match.sport == Sport(sport))

        if load_relations:
            stmt = stmt.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

        stmt = stmt.order_by(desc(Match.start_time)).limit(limit)
        return list(self.session.execute(stmt).scalars().all())


class MatchStatisticRepository:
    """Repository for MatchStatistic CRUD operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def create(self, statistic_data: dict) -> MatchStatistic:
        """Create new match statistic."""
        statistic = MatchStatistic(**statistic_data)
        self.session.add(statistic)
        self.session.flush()
        return statistic

    def get_by_match(self, match_id: int) -> list[MatchStatistic]:
        """Get all statistics for a match."""
        stmt = (
            select(MatchStatistic)
            .where(MatchStatistic.match_id == match_id)
            .order_by(MatchStatistic.stat_type)
        )
        return list(self.session.execute(stmt).scalars().all())

    def delete_by_match(self, match_id: int) -> int:
        """Delete all statistics for a match."""
        stmt = select(MatchStatistic).where(MatchStatistic.match_id == match_id)
        statistics = self.session.execute(stmt).scalars().all()
        count = len(statistics)

        for stat in statistics:
            self.session.delete(stat)

        return count


class IncidentRepository:
    """Repository for Incident CRUD operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def create(self, incident_data: dict) -> Incident:
        """Create new incident."""
        incident = Incident(**incident_data)
        self.session.add(incident)
        self.session.flush()
        return incident

    def get_by_match(self, match_id: int) -> list[Incident]:
        """Get all incidents for a match."""
        stmt = (
            select(Incident)
            .where(Incident.match_id == match_id)
            .order_by(Incident.time)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_sofascore_id(self, sofascore_incident_id: int) -> Optional[Incident]:
        """Get incident by SofaScore incident ID."""
        stmt = select(Incident).where(
            Incident.sofascore_incident_id == sofascore_incident_id
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(self, incident_data: dict) -> Incident:
        """
        Insert or update incident.

        Args:
            incident_data: Dictionary with incident data

        Returns:
            Incident instance
        """
        sofascore_incident_id = incident_data.get("sofascore_incident_id")

        # Try to find existing incident
        incident = None
        if sofascore_incident_id:
            incident = self.get_by_sofascore_id(sofascore_incident_id)

        if incident:
            # Update existing incident
            for key, value in incident_data.items():
                if hasattr(incident, key) and key not in ("id", "created_at"):
                    setattr(incident, key, value)
            incident.updated_at = datetime.utcnow()
            logger.debug(f"Updated incident: {incident.incident_type}")
        else:
            # Create new incident
            incident = Incident(**incident_data)
            self.session.add(incident)
            logger.debug(f"Created new incident: {incident.incident_type}")

        self.session.flush()
        return incident

    def delete_by_match(self, match_id: int) -> int:
        """Delete all incidents for a match."""
        stmt = select(Incident).where(Incident.match_id == match_id)
        incidents = self.session.execute(stmt).scalars().all()
        count = len(incidents)

        for incident in incidents:
            self.session.delete(incident)

        return count
