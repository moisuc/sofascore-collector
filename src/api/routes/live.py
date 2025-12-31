"""Live matches endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.models.schemas import MatchWithRelations, Sport
from src.storage.database import Match
from src.storage.repositories import MatchRepository

router = APIRouter()


@router.get("", response_model=list[MatchWithRelations])
def get_all_live_matches(
    sport: Sport | None = Query(None, description="Filter by sport"),
    db: Session = Depends(get_db),
) -> list[Match]:
    """
    Get all live matches across all sports or filtered by sport.

    Args:
        sport: Optional sport filter
        db: Database session

    Returns:
        List of live matches with team and league details
    """
    repo = MatchRepository(db)
    matches = repo.get_live(sport=sport.value if sport else None, load_relations=True)
    return matches


@router.get("/{sport}", response_model=list[MatchWithRelations])
def get_live_matches_by_sport(
    sport: Sport,
    db: Session = Depends(get_db),
) -> list[Match]:
    """
    Get live matches for a specific sport.

    Args:
        sport: Sport to filter by
        db: Database session

    Returns:
        List of live matches for the specified sport
    """
    repo = MatchRepository(db)
    matches = repo.get_live(sport=sport.value, load_relations=True)
    return matches
