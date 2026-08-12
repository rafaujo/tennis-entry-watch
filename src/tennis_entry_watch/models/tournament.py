from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Surface(StrEnum):
    HARD = "Hard"
    CLAY = "Clay"
    GRASS = "Grass"
    CARPET = "Carpet"


class TournamentStatus(StrEnum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str
    country: str


class Tournament(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tournament_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str
    year: int = Field(ge=1968)
    start_date: date
    end_date: date | None = None
    category: str
    surface: Surface
    location: Location
    main_draw_size: int | None = Field(default=None, gt=0)
    qualifying_draw_size: int | None = Field(default=None, gt=0)
    entry_list_date: date | None = None
    entry_ranking_date: date | None = None
    status: TournamentStatus = TournamentStatus.UPCOMING

    @model_validator(mode="after")
    def dates_are_consistent(self) -> "Tournament":
        if self.start_date.year != self.year:
            raise ValueError("year must match start_date")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self

