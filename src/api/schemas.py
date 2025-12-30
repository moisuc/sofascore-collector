"""API-specific request/response schemas for filters, pagination, etc."""

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from src.models.schemas import MatchStatus, Sport


# Generic type for pagination
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    items: list[T] = Field(..., description="List of items")

    @property
    def total_pages(self) -> int:
        """Calculate total pages."""
        return (self.total + self.page_size - 1) // self.page_size


class MatchFilters(BaseModel):
    """Query parameters for filtering matches."""

    sport: Sport | None = Field(None, description="Filter by sport")
    status: MatchStatus | None = Field(None, description="Filter by match status")
    date_from: date | None = Field(None, description="Filter matches from this date")
    date_to: date | None = Field(None, description="Filter matches until this date")
    team_id: int | None = Field(None, description="Filter by team ID (home or away)")
    league_id: int | None = Field(None, description="Filter by league ID")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")


class LiveFilters(BaseModel):
    """Query parameters for filtering live matches."""

    sport: Sport | None = Field(None, description="Filter by sport")


class SportMatchFilters(BaseModel):
    """Query parameters for sport-specific match filtering."""

    date_from: date | None = Field(None, description="Filter from date")
    date_to: date | None = Field(None, description="Filter until date")
    league_id: int | None = Field(None, description="Filter by league")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")


class DatabaseSummary(BaseModel):
    """Database statistics summary."""

    total_teams: int
    total_leagues: int
    total_matches: int
    total_statistics: int
    total_incidents: int
    matches_by_status: dict[str, int]
    matches_by_sport: dict[str, int]
    last_updated: datetime | None = None
    last_updated_by_sport: dict[str, datetime | None] = {}


class HealthResponse(BaseModel):
    """API health check response."""

    status: str = "healthy"
    timestamp: datetime
    database_connected: bool
