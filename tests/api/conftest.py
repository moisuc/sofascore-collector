"""API test fixtures."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.api.dependencies import get_db
from src.storage.database import Base, Match, Team, League
from src.models.schemas import Sport, MatchStatus


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def client(test_db):
    """FastAPI TestClient with test database."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_teams(test_db):
    """Create sample teams in test database."""
    home_team = Team(
        sofascore_id=1001,
        name="Real Madrid",
        slug="real-madrid",
        short_name="RMA",
        sport=Sport.FOOTBALL,
        national=False,
    )
    away_team = Team(
        sofascore_id=1002,
        name="Barcelona",
        slug="barcelona",
        short_name="BAR",
        sport=Sport.FOOTBALL,
        national=False,
    )
    test_db.add(home_team)
    test_db.add(away_team)
    test_db.commit()

    return home_team, away_team


@pytest.fixture
def sample_league(test_db):
    """Create sample league in test database."""
    league = League(
        sofascore_id=2001,
        name="La Liga",
        slug="la-liga",
        sport=Sport.FOOTBALL,
        country="Spain",
    )
    test_db.add(league)
    test_db.commit()

    return league


@pytest.fixture
def sample_match(test_db, sample_teams, sample_league):
    """Create sample match in test database."""
    home_team, away_team = sample_teams

    match = Match(
        sofascore_id=3001,
        slug="real-madrid-barcelona",
        sport=Sport.FOOTBALL,
        status=MatchStatus.LIVE,
        status_code=7,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        league_id=sample_league.id,
        home_score_current=2,
        away_score_current=1,
        start_timestamp=1735578456,
        start_time=datetime(2024, 12, 30, 20, 0, 0),
    )
    test_db.add(match)
    test_db.commit()
    test_db.refresh(match)

    return match
