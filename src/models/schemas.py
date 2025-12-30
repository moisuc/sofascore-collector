"""Pydantic models for data validation and API responses."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Sport(str, Enum):
    """Supported sports enumeration."""

    FOOTBALL = "football"
    TENNIS = "tennis"
    BASKETBALL = "basketball"
    HANDBALL = "handball"
    VOLLEYBALL = "volleyball"


class MatchStatus(str, Enum):
    """Match status enumeration."""

    SCHEDULED = "notstarted"
    LIVE = "inprogress"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    ABANDONED = "abandoned"


class TeamBase(BaseModel):
    """Base Team schema."""

    sofascore_id: int
    name: str
    slug: str
    short_name: str | None = None
    name_code: str | None = None
    sport: Sport
    country: str | None = None
    national: bool = False
    gender: str | None = None
    user_count: int = 0
    team_colors: dict | None = None


class Team(TeamBase):
    """Full Team schema with ID and timestamps."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamSummary(BaseModel):
    """Lightweight Team schema for nested responses."""

    id: int
    sofascore_id: int
    name: str
    short_name: str | None = None
    slug: str

    model_config = ConfigDict(from_attributes=True)


class LeagueBase(BaseModel):
    """Base League schema."""

    sofascore_id: int
    name: str
    slug: str
    sport: Sport
    country: str | None = None
    category_name: str | None = None
    unique_tournament_id: int | None = None
    unique_tournament_name: str | None = None
    priority: int = 0
    has_player_statistics: bool = False


class League(LeagueBase):
    """Full League schema with ID and timestamps."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeagueSummary(BaseModel):
    """Lightweight League schema for nested responses."""

    id: int
    sofascore_id: int
    name: str
    slug: str
    country: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchBase(BaseModel):
    """Base Match schema."""

    sofascore_id: int
    slug: str
    custom_id: str | None = None
    sport: Sport
    status: MatchStatus
    status_code: int
    home_score_current: int = 0
    away_score_current: int = 0
    home_score_period1: int | None = None
    away_score_period1: int | None = None
    home_score_period2: int | None = None
    away_score_period2: int | None = None
    home_score_overtime: int | None = None
    away_score_overtime: int | None = None
    home_score_penalties: int | None = None
    away_score_penalties: int | None = None
    start_timestamp: int
    start_time: datetime
    season_name: str | None = None
    season_year: str | None = None
    round: int | None = None
    winner_code: int = 0
    has_xg: bool = False
    has_highlights: bool = False
    has_player_statistics: bool = False
    has_heatmap: bool = False
    time_data: dict | None = None
    extra_data: dict | None = None


class Match(MatchBase):
    """Full Match schema with ID, timestamps, and relationships."""

    id: int
    home_team_id: int
    away_team_id: int
    league_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchWithRelations(Match):
    """Match schema with nested team and league data."""

    home_team: TeamSummary
    away_team: TeamSummary
    league: LeagueSummary | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchStatisticBase(BaseModel):
    """Base MatchStatistic schema."""

    stat_type: str
    home_value: str | None = None
    away_value: str | None = None
    home_value_numeric: float | None = None
    away_value_numeric: float | None = None
    period: str | None = None
    extra_data: dict | None = None


class MatchStatistic(MatchStatisticBase):
    """Full MatchStatistic schema with ID and timestamps."""

    id: int
    match_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentBase(BaseModel):
    """Base Incident schema."""

    sofascore_incident_id: int | None = None
    incident_type: str
    time: int
    added_time: int | None = None
    is_home: bool
    player_id: int | None = None
    player_name: str | None = None
    scoring_team: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    goal_description: str | None = None
    card_type: str | None = None
    player_in_id: int | None = None
    player_in_name: str | None = None
    player_out_id: int | None = None
    player_out_name: str | None = None
    extra_data: dict | None = None


class Incident(IncidentBase):
    """Full Incident schema with ID and timestamps."""

    id: int
    match_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchDetail(MatchWithRelations):
    """Complete match details with statistics and incidents."""

    statistics: list[MatchStatistic] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
