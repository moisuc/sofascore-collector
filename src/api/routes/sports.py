"""Sport-specific endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.models.schemas import League, MatchWithRelations, Sport
from src.storage.repositories import LeagueRepository, MatchRepository

router = APIRouter()


@router.get("", response_model=list[str])
def get_sports() -> list[str]:
    """
    Get list of available sports.

    Returns:
        List of sport names
    """
    return [sport.value for sport in Sport]


@router.get("/{sport}/today", response_model=list[MatchWithRelations])
def get_today_matches(
    sport: Sport,
    db: Session = Depends(get_db),
) -> list[MatchWithRelations]:
    """
    Get today's matches for a specific sport.

    Args:
        sport: Sport to query
        db: Database session

    Returns:
        List of matches scheduled for today
    """
    repo = MatchRepository(db)
    today = date.today()
    matches = repo.get_by_date(
        target_date=today,
        sport=sport.value,
        load_relations=True,
    )
    return matches


@router.get("/{sport}/upcoming", response_model=list[MatchWithRelations])
def get_upcoming_matches(
    sport: Sport,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
) -> list[MatchWithRelations]:
    """
    Get upcoming scheduled matches for a specific sport.

    Args:
        sport: Sport to query
        limit: Maximum number of results
        db: Database session

    Returns:
        List of upcoming matches
    """
    repo = MatchRepository(db)
    matches = repo.get_upcoming(
        sport=sport.value,
        limit=limit,
        load_relations=True,
    )
    return matches


@router.get("/{sport}/finished", response_model=list[MatchWithRelations])
def get_finished_matches(
    sport: Sport,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
) -> list[MatchWithRelations]:
    """
    Get recent finished matches for a specific sport.

    Args:
        sport: Sport to query
        limit: Maximum number of results
        db: Database session

    Returns:
        List of finished matches (most recent first)
    """
    repo = MatchRepository(db)
    matches = repo.get_finished(
        sport=sport.value,
        limit=limit,
        load_relations=True,
    )
    return matches


@router.get("/{sport}/leagues", response_model=list[League])
def get_sport_leagues(
    sport: Sport,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: Session = Depends(get_db),
) -> list[League]:
    """
    Get leagues/tournaments for a specific sport.

    Args:
        sport: Sport to query
        limit: Maximum number of results
        offset: Results offset for pagination
        db: Database session

    Returns:
        List of leagues for the specified sport
    """
    repo = LeagueRepository(db)
    leagues = repo.get_all(
        sport=sport.value,
        limit=limit,
        offset=offset,
    )
    return leagues
