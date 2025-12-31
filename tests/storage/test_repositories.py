"""Repository tests."""

from datetime import datetime

from src.storage.repositories import TeamRepository, MatchRepository, LeagueRepository
from src.models.schemas import Sport, MatchStatus


def test_upsert_team(test_db):
    """Test upserting a team (insert and update)."""
    repo = TeamRepository(test_db)

    team_data = {
        "sofascore_id": 1001,
        "name": "Real Madrid",
        "slug": "real-madrid",
        "short_name": "RMA",
        "sport": "football",
        "national": False,
    }

    # Insert
    team = repo.upsert(team_data)
    assert team.sofascore_id == 1001
    assert team.name == "Real Madrid"

    # Update
    team_data["name"] = "Real Madrid CF"
    updated_team = repo.upsert(team_data)
    assert updated_team.sofascore_id == 1001
    assert updated_team.name == "Real Madrid CF"
    assert updated_team.id == team.id  # Same record


def test_upsert_match_with_relationships(test_db):
    """Test upserting a match with team and league relationships."""
    team_repo = TeamRepository(test_db)
    league_repo = LeagueRepository(test_db)
    match_repo = MatchRepository(test_db)

    # Create teams
    home_team = team_repo.upsert({
        "sofascore_id": 1001,
        "name": "Real Madrid",
        "slug": "real-madrid",
        "sport": "football",
    })
    away_team = team_repo.upsert({
        "sofascore_id": 1002,
        "name": "Barcelona",
        "slug": "barcelona",
        "sport": "football",
    })

    # Create league
    league = league_repo.upsert({
        "sofascore_id": 2001,
        "name": "La Liga",
        "slug": "la-liga",
        "sport": "football",
        "country": "Spain",
    })

    # Create match
    match_data = {
        "sofascore_id": 3001,
        "slug": "real-madrid-barcelona",
        "sport": Sport.FOOTBALL,
        "status": MatchStatus.SCHEDULED,
        "status_code": 0,
        "home_team_id": home_team.id,
        "away_team_id": away_team.id,
        "league_id": league.id,
        "start_timestamp": 1735578456,
        "start_time": datetime(2024, 12, 30, 20, 0, 0),
    }

    match = match_repo.upsert(match_data)
    assert match.sofascore_id == 3001
    assert match.home_team_id == home_team.id
    assert match.away_team_id == away_team.id
    assert match.league_id == league.id
