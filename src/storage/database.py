"""SQLAlchemy database models for SofaScore data."""

from datetime import datetime, UTC
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Enum,
    JSON,
    TypeDecorator,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    Session,
)
from sqlalchemy.pool import StaticPool

from src.config import settings


class JSONType(TypeDecorator):
    """
    JSON type that automatically uses JSONB on PostgreSQL, JSON elsewhere.

    Provides optimal performance across different databases:
    - PostgreSQL: JSONB (binary, indexable, efficient queries)
    - SQLite/Others: JSON (standard TEXT storage)
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load the appropriate JSON type for the database dialect."""
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Sport(str, PyEnum):
    """Supported sports enumeration."""

    FOOTBALL = "football"
    TENNIS = "tennis"
    BASKETBALL = "basketball"
    HANDBALL = "handball"
    VOLLEYBALL = "volleyball"


class MatchStatus(str, PyEnum):
    """Match status enumeration."""

    SCHEDULED = "notstarted"
    LIVE = "inprogress"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    ABANDONED = "abandoned"


class Team(Base):
    """Team/Club model."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sofascore_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100))
    name_code: Mapped[Optional[str]] = mapped_column(String(10))
    sport: Mapped[Sport] = mapped_column(Enum(Sport), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    national: Mapped[bool] = mapped_column(Boolean, default=False)
    gender: Mapped[Optional[str]] = mapped_column(String(1))
    user_count: Mapped[int] = mapped_column(Integer, default=0)
    team_colors: Mapped[Optional[dict]] = mapped_column(JSONType)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    home_matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="home_team", foreign_keys="Match.home_team_id"
    )
    away_matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="away_team", foreign_keys="Match.away_team_id"
    )

    # Indexes
    __table_args__ = (
        Index("ix_teams_sofascore_id", "sofascore_id", unique=True),
        Index("ix_teams_sport", "sport"),
        Index("ix_teams_slug", "slug"),
    )

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name='{self.name}', sport='{self.sport}')>"


class League(Base):
    """League/Tournament/Competition model."""

    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sofascore_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    sport: Mapped[Sport] = mapped_column(Enum(Sport), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    category_name: Mapped[Optional[str]] = mapped_column(String(255))
    unique_tournament_id: Mapped[Optional[int]] = mapped_column(Integer)
    unique_tournament_name: Mapped[Optional[str]] = mapped_column(String(255))
    unique_tournament_slug: Mapped[Optional[str]] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    has_player_statistics: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    matches: Mapped[list["Match"]] = relationship("Match", back_populates="league")

    # Indexes
    __table_args__ = (
        Index("ix_leagues_sofascore_id", "sofascore_id", unique=True),
        Index("ix_leagues_sport", "sport"),
        Index("ix_leagues_slug", "slug"),
    )

    def __repr__(self) -> str:
        return f"<League(id={self.id}, name='{self.name}', sport='{self.sport}')>"


class Match(Base):
    """Match/Event model."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sofascore_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    custom_id: Mapped[Optional[str]] = mapped_column(String(50))
    sport: Mapped[Sport] = mapped_column(Enum(Sport), nullable=False)

    # Status
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus), nullable=False, default=MatchStatus.SCHEDULED
    )
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # Teams (Foreign Keys)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)

    # League (Foreign Key)
    league_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leagues.id"))

    # Scores
    home_score_current: Mapped[int] = mapped_column(Integer, default=0)
    away_score_current: Mapped[int] = mapped_column(Integer, default=0)
    home_score_period1: Mapped[Optional[int]] = mapped_column(Integer)
    away_score_period1: Mapped[Optional[int]] = mapped_column(Integer)
    home_score_period2: Mapped[Optional[int]] = mapped_column(Integer)
    away_score_period2: Mapped[Optional[int]] = mapped_column(Integer)
    home_score_overtime: Mapped[Optional[int]] = mapped_column(Integer)
    away_score_overtime: Mapped[Optional[int]] = mapped_column(Integer)
    home_score_penalties: Mapped[Optional[int]] = mapped_column(Integer)
    away_score_penalties: Mapped[Optional[int]] = mapped_column(Integer)

    # Match info
    start_timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    season_name: Mapped[Optional[str]] = mapped_column(String(50))
    season_year: Mapped[Optional[str]] = mapped_column(String(50))
    round: Mapped[Optional[int]] = mapped_column(Integer)
    winner_code: Mapped[int] = mapped_column(Integer, default=0)

    # Feature flags
    has_xg: Mapped[bool] = mapped_column(Boolean, default=False)
    has_highlights: Mapped[bool] = mapped_column(Boolean, default=False)
    has_player_statistics: Mapped[bool] = mapped_column(Boolean, default=False)
    has_heatmap: Mapped[bool] = mapped_column(Boolean, default=False)
    is_inverse: Mapped[bool] = mapped_column(Boolean, default=False)

    # Additional data (JSON for flexibility, JSONB on PostgreSQL)
    time_data: Mapped[Optional[dict]] = mapped_column(JSONType)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONType)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    home_team: Mapped["Team"] = relationship(
        "Team", back_populates="home_matches", foreign_keys=[home_team_id]
    )
    away_team: Mapped["Team"] = relationship(
        "Team", back_populates="away_matches", foreign_keys=[away_team_id]
    )
    league: Mapped[Optional["League"]] = relationship(
        "League", back_populates="matches"
    )
    statistics: Mapped[list["MatchStatistic"]] = relationship(
        "MatchStatistic", back_populates="match", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(
        "Incident", back_populates="match", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_matches_sofascore_id", "sofascore_id", unique=True),
        Index("ix_matches_sport_status", "sport", "status"),
        Index("ix_matches_sport_start_time", "sport", "start_time"),
        Index("ix_matches_status", "status"),
        Index("ix_matches_start_time", "start_time"),
        Index("ix_matches_home_team_id", "home_team_id"),
        Index("ix_matches_away_team_id", "away_team_id"),
        Index("ix_matches_league_id", "league_id"),
        Index("ix_matches_is_inverse", "is_inverse"),
    )

    def __repr__(self) -> str:
        return (
            f"<Match(id={self.id}, sport='{self.sport}', "
            f"status='{self.status}', home={self.home_team_id} vs away={self.away_team_id})>"
        )


class MatchStatistic(Base):
    """Match statistics model."""

    __tablename__ = "match_statistics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)

    # Statistic details
    stat_type: Mapped[str] = mapped_column(String(100), nullable=False)
    home_value: Mapped[Optional[str]] = mapped_column(String(50))
    away_value: Mapped[Optional[str]] = mapped_column(String(50))
    home_value_numeric: Mapped[Optional[float]] = mapped_column()
    away_value_numeric: Mapped[Optional[float]] = mapped_column()

    # Period (for period-specific stats)
    period: Mapped[Optional[str]] = mapped_column(String(50))

    # Additional data (JSONB on PostgreSQL)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONType)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    match: Mapped["Match"] = relationship("Match", back_populates="statistics")

    # Indexes
    __table_args__ = (
        Index("ix_match_statistics_match_id", "match_id"),
        Index("ix_match_statistics_stat_type", "stat_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<MatchStatistic(id={self.id}, match_id={self.match_id}, "
            f"type='{self.stat_type}')>"
        )


class Incident(Base):
    """Match incident model (goals, cards, substitutions, etc.)."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    sofascore_incident_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Incident details
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    time: Mapped[int] = mapped_column(Integer, nullable=False)
    added_time: Mapped[Optional[int]] = mapped_column(Integer)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Player info
    player_id: Mapped[Optional[int]] = mapped_column(Integer)
    player_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Goal-specific
    scoring_team: Mapped[Optional[str]] = mapped_column(String(10))
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    goal_description: Mapped[Optional[str]] = mapped_column(String(100))

    # Card-specific
    card_type: Mapped[Optional[str]] = mapped_column(String(20))

    # Substitution-specific
    player_in_id: Mapped[Optional[int]] = mapped_column(Integer)
    player_in_name: Mapped[Optional[str]] = mapped_column(String(255))
    player_out_id: Mapped[Optional[int]] = mapped_column(Integer)
    player_out_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Additional data (JSONB on PostgreSQL)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONType)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    match: Mapped["Match"] = relationship("Match", back_populates="incidents")

    # Indexes
    __table_args__ = (
        Index("ix_incidents_match_id", "match_id"),
        Index("ix_incidents_incident_type", "incident_type"),
        Index("ix_incidents_time", "time"),
    )

    def __repr__(self) -> str:
        return (
            f"<Incident(id={self.id}, match_id={self.match_id}, "
            f"type='{self.incident_type}', time={self.time})>"
        )


# Database utilities
_engine = None
_session_factory = None


def is_postgresql(db_url: str) -> bool:
    """Check if database URL is for PostgreSQL."""
    return db_url.startswith(("postgresql://", "postgresql+", "postgres://"))


def get_engine():
    """Get or create database engine with appropriate configuration."""
    global _engine
    if _engine is None:
        db_url = settings.database_url

        # Database-specific configuration
        if db_url.startswith("sqlite"):
            # SQLite: Single connection with StaticPool
            connect_args = {"check_same_thread": False}
            poolclass = StaticPool
            pool_kwargs = {}
        elif is_postgresql(db_url):
            # PostgreSQL: Connection pooling with QueuePool
            connect_args = {}
            poolclass = None  # Use default QueuePool
            pool_kwargs = {
                "pool_size": 5,  # Base connections
                "max_overflow": 10,  # Additional connections on demand
                "pool_pre_ping": True,  # Verify connections before use
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            }
        else:
            # Other databases: Use defaults
            connect_args = {}
            poolclass = None
            pool_kwargs = {}

        _engine = create_engine(
            db_url,
            connect_args=connect_args,
            poolclass=poolclass,
            echo=False,  # Set to True for SQL logging
            **pool_kwargs,
        )

    return _engine


def get_session() -> Session:
    """Get a new database session."""
    global _session_factory
    if _session_factory is None:
        from sqlalchemy.orm import sessionmaker

        _session_factory = sessionmaker(bind=get_engine())

    return _session_factory()


def init_db():
    """Initialize database (create all tables)."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("Database initialized successfully")
