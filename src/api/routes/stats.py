"""Statistics and database summary endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.schemas import DatabaseSummary
from src.models.schemas import Incident, MatchStatistic
from src.storage.database import (
    Incident as IncidentModel,
    League,
    Match,
    MatchStatistic as MatchStatisticModel,
    Team,
)
from src.storage.repositories import IncidentRepository, MatchRepository, MatchStatisticRepository

router = APIRouter()


@router.get("/match/{match_id}/statistics", response_model=list[MatchStatistic])
def get_match_statistics(
    match_id: int,
    db: Session = Depends(get_db),
) -> list[MatchStatistic]:
    """
    Get all statistics for a specific match.

    Args:
        match_id: SofaScore match ID
        db: Database session

    Returns:
        List of match statistics

    Raises:
        HTTPException: 404 if match not found
    """
    # Verify match exists using SofaScore ID
    match_repo = MatchRepository(db)
    match = match_repo.get_by_sofascore_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match with SofaScore ID {match_id} not found")

    stats_repo = MatchStatisticRepository(db)
    statistics = stats_repo.get_by_match(match.id)
    return statistics


@router.get("/match/{match_id}/incidents", response_model=list[Incident])
def get_match_incidents(
    match_id: int,
    db: Session = Depends(get_db),
) -> list[Incident]:
    """
    Get all incidents (goals, cards, substitutions) for a specific match.

    Args:
        match_id: SofaScore match ID
        db: Database session

    Returns:
        List of match incidents ordered by time

    Raises:
        HTTPException: 404 if match not found
    """
    # Verify match exists using SofaScore ID
    match_repo = MatchRepository(db)
    match = match_repo.get_by_sofascore_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match with SofaScore ID {match_id} not found")

    incident_repo = IncidentRepository(db)
    incidents = incident_repo.get_by_match(match.id)
    return incidents


@router.get("/summary", response_model=DatabaseSummary)
def get_database_summary(db: Session = Depends(get_db)) -> DatabaseSummary:
    """
    Get database statistics summary.

    Returns counts of all entities and breakdown by status/sport.

    Args:
        db: Database session

    Returns:
        Database summary with counts and breakdowns
    """
    # Count totals
    total_teams = db.scalar(select(func.count()).select_from(Team))
    total_leagues = db.scalar(select(func.count()).select_from(League))
    total_matches = db.scalar(select(func.count()).select_from(Match))
    total_statistics = db.scalar(select(func.count()).select_from(MatchStatisticModel))
    total_incidents = db.scalar(select(func.count()).select_from(IncidentModel))

    # Count matches by status
    matches_by_status = {}
    status_counts = db.execute(
        select(Match.status, func.count()).group_by(Match.status)
    ).all()
    for status, count in status_counts:
        matches_by_status[status.value] = count

    # Count matches by sport
    matches_by_sport = {}
    sport_counts = db.execute(select(Match.sport, func.count()).group_by(Match.sport)).all()
    for sport, count in sport_counts:
        matches_by_sport[sport.value] = count

    # Get last update timestamp (most recent match update)
    last_updated = db.scalar(select(func.max(Match.updated_at)))

    # Get last update timestamp per sport
    last_updated_by_sport = {}
    sport_updates = db.execute(
        select(Match.sport, func.max(Match.updated_at)).group_by(Match.sport)
    ).all()
    for sport, updated_at in sport_updates:
        last_updated_by_sport[sport.value] = updated_at

    return DatabaseSummary(
        total_teams=total_teams or 0,
        total_leagues=total_leagues or 0,
        total_matches=total_matches or 0,
        total_statistics=total_statistics or 0,
        total_incidents=total_incidents or 0,
        matches_by_status=matches_by_status,
        matches_by_sport=matches_by_sport,
        last_updated=last_updated,
        last_updated_by_sport=last_updated_by_sport,
    )
