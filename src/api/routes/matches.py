"""Match endpoints with filtering and details."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from src.api.dependencies import get_db
from src.models.schemas import MatchDetail, MatchStatus, MatchWithRelations, Sport
from src.storage.database import Match

router = APIRouter()


@router.get("", response_model=list[MatchWithRelations])
def get_matches(
    sport: Sport | None = Query(None, description="Filter by sport"),
    status: MatchStatus | None = Query(None, description="Filter by match status"),
    date_from: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    team_id: int | None = Query(None, description="Filter by team ID (home or away)"),
    league_id: int | None = Query(None, description="Filter by league ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: Session = Depends(get_db),
) -> list[MatchWithRelations]:
    """
    Get matches with flexible filtering.

    Supports filtering by:
    - sport
    - status (live, scheduled, finished, etc.)
    - date range
    - team (home or away)
    - league

    Returns:
        List of matches with team and league details
    """
    # Build query
    stmt = select(Match).options(
        joinedload(Match.home_team),
        joinedload(Match.away_team),
        joinedload(Match.league),
    )

    # Apply filters
    filters = []

    if sport:
        filters.append(Match.sport == sport)

    if status:
        filters.append(Match.status == status)

    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            filters.append(Match.start_time >= date_from_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format")

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            filters.append(Match.start_time <= date_to_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format")

    if team_id:
        filters.append(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))

    if league_id:
        filters.append(Match.league_id == league_id)

    if filters:
        stmt = stmt.where(and_(*filters))

    # Order and limit
    stmt = stmt.order_by(Match.start_time.desc()).limit(limit).offset(offset)

    # Execute
    matches = list(db.execute(stmt).scalars().all())
    return matches


@router.get("/{match_id}", response_model=MatchDetail)
def get_match_details(
    match_id: int,
    db: Session = Depends(get_db),
) -> MatchDetail:
    """
    Get detailed match information including statistics and incidents.

    Args:
        match_id: Internal match ID
        db: Database session

    Returns:
        Complete match details with stats and incidents

    Raises:
        HTTPException: 404 if match not found
    """
    # Load match with all relations
    stmt = (
        select(Match)
        .where(Match.id == match_id)
        .options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.league),
            joinedload(Match.statistics),
            joinedload(Match.incidents),
        )
    )

    match = db.execute(stmt).scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail=f"Match with id {match_id} not found")

    return match
