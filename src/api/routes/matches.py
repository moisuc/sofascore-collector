"""Match endpoints with filtering and details."""

from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from src.api.dependencies import get_db
from src.models.schemas import MatchDetail, MatchStatus, MatchWithRelations, Sport
from src.storage.database import Match, League
from src.storage.repositories import MatchRepository

router = APIRouter()


@router.get("", response_model=list[MatchWithRelations])
def get_matches(
    sport: Sport | None = Query(None, description="Filter by sport"),
    status: MatchStatus | None = Query(None, description="Filter by match status"),
    date_from: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    team_id: int | None = Query(None, description="Filter by team ID (home or away)"),
    league_id: int | None = Query(None, description="Filter by league ID"),
    limit: int = Query(50, ge=1, le=5000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: Session = Depends(get_db),
) -> list[Match]:
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
) -> Match | None:
    """
    Get detailed match information including statistics and incidents.

    Args:
        match_id: SofaScore match ID
        db: Database session

    Returns:
        Complete match details with stats and incidents

    Raises:
        HTTPException: 404 if match not found
    """
    # Load match with all relations using repository
    repo = MatchRepository(db)
    match = repo.get_by_sofascore_id(match_id, load_details=True)

    if not match:
        raise HTTPException(status_code=404, detail=f"Match with SofaScore ID {match_id} not found")

    return match


@router.get("/by-date/grouped")
def get_matches_by_date_grouped(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    sport: Sport | None = Query(None, description="Filter by sport"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get matches for a specific date, grouped by league.

    Args:
        date: Date in YYYY-MM-DD format
        sport: Optional sport filter
        db: Database session

    Returns:
        Dictionary with leagues as keys, each containing list of matches

    Raises:
        HTTPException: 400 if date format is invalid
    """
    try:
        target_date = datetime.fromisoformat(date)
        date_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Build query
    stmt = select(Match).options(
        joinedload(Match.home_team),
        joinedload(Match.away_team),
        joinedload(Match.league),
    )

    # Apply filters
    filters = [
        Match.start_time >= date_start,
        Match.start_time < date_end,
    ]

    if sport:
        filters.append(Match.sport == sport)

    stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(Match.start_time.asc())

    # Execute query
    matches = list(db.execute(stmt).scalars().all())

    # Group matches by league
    grouped = defaultdict(list)
    for match in matches:
        league_key = match.league.name if match.league else "Unknown League"
        grouped[league_key].append({
            "sofascore_id": match.sofascore_id,
            "slug": match.slug,
            "sport": match.sport.value,
            "status": match.status.value,
            "home_team": {
                "sofascore_id": match.home_team.sofascore_id,
                "name": match.home_team.name,
                "short_name": match.home_team.short_name,
            },
            "away_team": {
                "sofascore_id": match.away_team.sofascore_id,
                "name": match.away_team.name,
                "short_name": match.away_team.short_name,
            },
            "home_score": match.home_score_current,
            "away_score": match.away_score_current,
            "start_time": match.start_time.isoformat(),
            "league": {
                "sofascore_id": match.league.sofascore_id,
                "name": match.league.name,
            } if match.league else None,
        })

    return dict(grouped)
