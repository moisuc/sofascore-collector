"""Tests for repository operations."""

import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.database import Base, Sport, MatchStatus
from src.storage.repositories import (
    TeamRepository,
    LeagueRepository,
    MatchRepository,
    MatchStatisticRepository,
    IncidentRepository,
)


@pytest.fixture
def engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session for testing."""
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()
    yield session
    session.close()


@pytest.fixture
def team_repo(session):
    """Create TeamRepository instance."""
    return TeamRepository(session)


@pytest.fixture
def league_repo(session):
    """Create LeagueRepository instance."""
    return LeagueRepository(session)


@pytest.fixture
def match_repo(session):
    """Create MatchRepository instance."""
    return MatchRepository(session)


@pytest.fixture
def statistic_repo(session):
    """Create MatchStatisticRepository instance."""
    return MatchStatisticRepository(session)


@pytest.fixture
def incident_repo(session):
    """Create IncidentRepository instance."""
    return IncidentRepository(session)


@pytest.fixture
def sample_team_data():
    """Sample team data for testing."""
    return {
        "sofascore_id": 17,
        "name": "Manchester City",
        "slug": "manchester-city",
        "short_name": "Man City",
        "name_code": "MCI",
        "sport": Sport.FOOTBALL,
        "country": "England",
        "national": False,
        "gender": "M",
        "user_count": 2845123,
        "team_colors": {"primary": "#6cabdd", "secondary": "#ffffff"},
    }


@pytest.fixture
def sample_league_data():
    """Sample league data for testing."""
    return {
        "sofascore_id": 17,
        "name": "Premier League",
        "slug": "premier-league",
        "sport": Sport.FOOTBALL,
        "country": "England",
        "category_name": "England",
        "unique_tournament_id": 17,
        "unique_tournament_name": "Premier League",
        "priority": 1,
        "has_player_statistics": True,
    }


class TestTeamRepository:
    """Tests for TeamRepository."""

    def test_upsert_create_new_team(self, team_repo, sample_team_data, session):
        """Test creating a new team."""
        team = team_repo.upsert(sample_team_data)

        assert team.id is not None
        assert team.sofascore_id == 17
        assert team.name == "Manchester City"
        assert team.sport == Sport.FOOTBALL

        session.commit()

        # Verify team was saved
        saved_team = team_repo.get_by_sofascore_id(17)
        assert saved_team is not None
        assert saved_team.name == "Manchester City"

    def test_upsert_update_existing_team(self, team_repo, sample_team_data, session):
        """Test updating an existing team."""
        # Create initial team
        team1 = team_repo.upsert(sample_team_data)
        session.commit()
        original_id = team1.id

        # Update team
        updated_data = sample_team_data.copy()
        updated_data["name"] = "Manchester City FC"
        updated_data["user_count"] = 3000000

        team2 = team_repo.upsert(updated_data)
        session.commit()

        # Should be same team (same ID)
        assert team2.id == original_id
        assert team2.name == "Manchester City FC"
        assert team2.user_count == 3000000

    def test_get_by_sofascore_id(self, team_repo, sample_team_data, session):
        """Test getting team by SofaScore ID."""
        team_repo.upsert(sample_team_data)
        session.commit()

        team = team_repo.get_by_sofascore_id(17)
        assert team is not None
        assert team.sofascore_id == 17

    def test_get_by_slug(self, team_repo, sample_team_data, session):
        """Test getting team by slug."""
        team_repo.upsert(sample_team_data)
        session.commit()

        team = team_repo.get_by_slug("manchester-city", "football")
        assert team is not None
        assert team.slug == "manchester-city"

    def test_get_all_with_sport_filter(self, team_repo, sample_team_data, session):
        """Test getting all teams with sport filter."""
        # Create football team
        team_repo.upsert(sample_team_data)

        # Create tennis team
        tennis_team_data = {
            "sofascore_id": 100,
            "name": "Roger Federer",
            "slug": "roger-federer",
            "sport": Sport.TENNIS,
            "national": False,
        }
        team_repo.upsert(tennis_team_data)
        session.commit()

        # Get only football teams
        football_teams = team_repo.get_all(sport="football")
        assert len(football_teams) == 1
        assert football_teams[0].sport == Sport.FOOTBALL

    def test_upsert_with_extra_fields(self, team_repo, sample_team_data, session):
        """Test that extra fields are filtered out when creating teams."""
        # Add extra fields that don't exist on Team model
        team_data_with_extras = sample_team_data.copy()
        team_data_with_extras["unknown_field"] = "should be ignored"
        team_data_with_extras["another_extra"] = 12345

        # Should not raise an error
        team = team_repo.upsert(team_data_with_extras)
        session.commit()

        assert team.id is not None
        assert team.sofascore_id == 17
        assert team.name == "Manchester City"
        # Extra fields should not be on the model
        assert not hasattr(team, "unknown_field")
        assert not hasattr(team, "another_extra")


class TestLeagueRepository:
    """Tests for LeagueRepository."""

    def test_upsert_create_new_league(self, league_repo, sample_league_data, session):
        """Test creating a new league."""
        league = league_repo.upsert(sample_league_data)

        assert league.id is not None
        assert league.sofascore_id == 17
        assert league.name == "Premier League"
        assert league.sport == Sport.FOOTBALL

        session.commit()

    def test_upsert_update_existing_league(
        self, league_repo, sample_league_data, session
    ):
        """Test updating an existing league."""
        # Create initial league
        league1 = league_repo.upsert(sample_league_data)
        session.commit()
        original_id = league1.id

        # Update league
        updated_data = sample_league_data.copy()
        updated_data["priority"] = 2

        league2 = league_repo.upsert(updated_data)
        session.commit()

        assert league2.id == original_id
        assert league2.priority == 2

    def test_upsert_with_unique_tournament_slug(
        self, league_repo, sample_league_data, session
    ):
        """Test creating league with unique_tournament_slug field."""
        league_data = sample_league_data.copy()
        league_data["unique_tournament_id"] = 100
        league_data["unique_tournament_name"] = "Premier League"
        league_data["unique_tournament_slug"] = "premier-league"

        league = league_repo.upsert(league_data)
        session.commit()

        assert league.unique_tournament_id == 100
        assert league.unique_tournament_name == "Premier League"
        assert league.unique_tournament_slug == "premier-league"

    def test_upsert_with_extra_fields(self, league_repo, sample_league_data, session):
        """Test that extra fields are filtered out when creating leagues."""
        # Add extra fields that don't exist on League model (simulating API response)
        league_data_with_extras = sample_league_data.copy()
        league_data_with_extras["category_slug"] = "england"
        league_data_with_extras["category_id"] = 1
        league_data_with_extras["flag"] = "gb"
        league_data_with_extras["unknown_field"] = "ignored"

        # Should not raise an error
        league = league_repo.upsert(league_data_with_extras)
        session.commit()

        assert league.id is not None
        assert league.sofascore_id == 17
        # Extra fields should not be on the model
        assert not hasattr(league, "category_slug")
        assert not hasattr(league, "category_id")
        assert not hasattr(league, "flag")


class TestMatchRepository:
    """Tests for MatchRepository."""

    @pytest.fixture
    def sample_match_data(self, team_repo, league_repo, sample_team_data, session):
        """Create sample match data with teams and league."""
        # Create home team
        home_team = team_repo.upsert(sample_team_data)

        # Create away team
        away_team_data = {
            "sofascore_id": 35,
            "name": "Manchester United",
            "slug": "manchester-united",
            "sport": Sport.FOOTBALL,
            "national": False,
        }
        away_team = team_repo.upsert(away_team_data)

        # Create league
        league_data = {
            "sofascore_id": 17,
            "name": "Premier League",
            "slug": "premier-league",
            "sport": Sport.FOOTBALL,
        }
        league = league_repo.upsert(league_data)

        session.commit()

        return {
            "sofascore_id": 11867542,
            "slug": "manchester-city-manchester-united",
            "sport": Sport.FOOTBALL,
            "status": MatchStatus.SCHEDULED,
            "status_code": 0,
            "home_team_id": home_team.id,
            "away_team_id": away_team.id,
            "league_id": league.id,
            "home_score_current": 0,
            "away_score_current": 0,
            "start_timestamp": 1735574400,
            "start_time": datetime.fromtimestamp(1735574400),
            "season_name": "24/25",
            "round": 19,
        }

    def test_upsert_create_new_match(self, match_repo, sample_match_data, session):
        """Test creating a new match."""
        match = match_repo.upsert(sample_match_data)

        assert match.id is not None
        assert match.sofascore_id == 11867542
        assert match.sport == Sport.FOOTBALL
        assert match.status == MatchStatus.SCHEDULED

        session.commit()

    def test_upsert_update_existing_match(
        self, match_repo, sample_match_data, session
    ):
        """Test updating an existing match."""
        # Create initial match
        match1 = match_repo.upsert(sample_match_data)
        session.commit()
        original_id = match1.id

        # Update match (change status and scores)
        updated_data = sample_match_data.copy()
        updated_data["status"] = MatchStatus.LIVE
        updated_data["status_code"] = 6
        updated_data["home_score_current"] = 2
        updated_data["away_score_current"] = 1

        match2 = match_repo.upsert(updated_data)
        session.commit()

        assert match2.id == original_id
        assert match2.status == MatchStatus.LIVE
        assert match2.home_score_current == 2
        assert match2.away_score_current == 1

    def test_get_live(self, match_repo, sample_match_data, session):
        """Test getting live matches."""
        # Create scheduled match
        match_repo.upsert(sample_match_data)

        # Create live match
        live_match_data = sample_match_data.copy()
        live_match_data["sofascore_id"] = 11867543
        live_match_data["status"] = MatchStatus.LIVE
        live_match_data["status_code"] = 6
        match_repo.upsert(live_match_data)

        session.commit()

        # Get live matches
        live_matches = match_repo.get_live()
        assert len(live_matches) == 1
        assert live_matches[0].status == MatchStatus.LIVE

    def test_get_by_date(self, match_repo, sample_match_data, session):
        """Test getting matches by date."""
        # Create match for today
        today = date.today()
        sample_match_data["start_time"] = datetime.combine(today, datetime.min.time())
        match_repo.upsert(sample_match_data)

        # Create match for tomorrow
        tomorrow = today + timedelta(days=1)
        tomorrow_match_data = sample_match_data.copy()
        tomorrow_match_data["sofascore_id"] = 11867543
        tomorrow_match_data["start_time"] = datetime.combine(
            tomorrow, datetime.min.time()
        )
        match_repo.upsert(tomorrow_match_data)

        session.commit()

        # Get today's matches
        today_matches = match_repo.get_by_date(today)
        assert len(today_matches) == 1

        # Get tomorrow's matches
        tomorrow_matches = match_repo.get_by_date(tomorrow)
        assert len(tomorrow_matches) == 1

    def test_get_upcoming(self, match_repo, sample_match_data, session):
        """Test getting upcoming matches."""
        # Create future match
        future_time = datetime.utcnow() + timedelta(days=1)
        sample_match_data["start_time"] = future_time
        sample_match_data["status"] = MatchStatus.SCHEDULED
        match_repo.upsert(sample_match_data)

        session.commit()

        upcoming_matches = match_repo.get_upcoming(sport="football")
        assert len(upcoming_matches) >= 1


class TestMatchStatisticRepository:
    """Tests for MatchStatisticRepository."""

    @pytest.fixture
    def sample_match_id(self, match_repo, team_repo, league_repo, session):
        """Create a sample match and return its ID."""
        # Create teams
        home_team = team_repo.upsert(
            {
                "sofascore_id": 17,
                "name": "Team A",
                "slug": "team-a",
                "sport": Sport.FOOTBALL,
                "national": False,
            }
        )
        away_team = team_repo.upsert(
            {
                "sofascore_id": 35,
                "name": "Team B",
                "slug": "team-b",
                "sport": Sport.FOOTBALL,
                "national": False,
            }
        )

        # Create match
        match = match_repo.upsert(
            {
                "sofascore_id": 123,
                "slug": "team-a-team-b",
                "sport": Sport.FOOTBALL,
                "status": MatchStatus.FINISHED,
                "status_code": 100,
                "home_team_id": home_team.id,
                "away_team_id": away_team.id,
                "home_score_current": 2,
                "away_score_current": 1,
                "start_timestamp": 1735574400,
                "start_time": datetime.fromtimestamp(1735574400),
            }
        )

        session.commit()
        return match.id

    def test_create_statistic(self, statistic_repo, sample_match_id, session):
        """Test creating a match statistic."""
        stat_data = {
            "match_id": sample_match_id,
            "stat_type": "possession",
            "home_value": "60%",
            "away_value": "40%",
            "home_value_numeric": 60.0,
            "away_value_numeric": 40.0,
        }

        stat = statistic_repo.create(stat_data)
        session.commit()

        assert stat.id is not None
        assert stat.stat_type == "possession"
        assert stat.home_value_numeric == 60.0

    def test_get_by_match(self, statistic_repo, sample_match_id, session):
        """Test getting statistics by match."""
        # Create multiple statistics
        stat_types = ["possession", "shots", "corners"]
        for stat_type in stat_types:
            statistic_repo.create(
                {
                    "match_id": sample_match_id,
                    "stat_type": stat_type,
                    "home_value": "10",
                    "away_value": "8",
                }
            )
        session.commit()

        stats = statistic_repo.get_by_match(sample_match_id)
        assert len(stats) == 3


class TestIncidentRepository:
    """Tests for IncidentRepository."""

    @pytest.fixture
    def sample_match_id(self, match_repo, team_repo, session):
        """Create a sample match and return its ID."""
        # Create teams
        home_team = team_repo.upsert(
            {
                "sofascore_id": 17,
                "name": "Team A",
                "slug": "team-a",
                "sport": Sport.FOOTBALL,
                "national": False,
            }
        )
        away_team = team_repo.upsert(
            {
                "sofascore_id": 35,
                "name": "Team B",
                "slug": "team-b",
                "sport": Sport.FOOTBALL,
                "national": False,
            }
        )

        # Create match
        match = match_repo.upsert(
            {
                "sofascore_id": 123,
                "slug": "team-a-team-b",
                "sport": Sport.FOOTBALL,
                "status": MatchStatus.LIVE,
                "status_code": 6,
                "home_team_id": home_team.id,
                "away_team_id": away_team.id,
                "home_score_current": 1,
                "away_score_current": 0,
                "start_timestamp": 1735574400,
                "start_time": datetime.fromtimestamp(1735574400),
            }
        )

        session.commit()
        return match.id

    def test_create_incident(self, incident_repo, sample_match_id, session):
        """Test creating an incident."""
        incident_data = {
            "match_id": sample_match_id,
            "sofascore_incident_id": 987654,
            "incident_type": "goal",
            "time": 23,
            "is_home": True,
            "player_name": "John Doe",
            "scoring_team": "home",
            "home_score": 1,
            "away_score": 0,
        }

        incident = incident_repo.create(incident_data)
        session.commit()

        assert incident.id is not None
        assert incident.incident_type == "goal"
        assert incident.time == 23

    def test_get_by_match(self, incident_repo, sample_match_id, session):
        """Test getting incidents by match."""
        # Create multiple incidents
        for time in [10, 23, 45]:
            incident_repo.create(
                {
                    "match_id": sample_match_id,
                    "incident_type": "goal",
                    "time": time,
                    "is_home": True,
                }
            )
        session.commit()

        incidents = incident_repo.get_by_match(sample_match_id)
        assert len(incidents) == 3
        # Should be ordered by time
        assert incidents[0].time == 10
        assert incidents[1].time == 23
        assert incidents[2].time == 45
