from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .entry import SourceType
from .tournament import Tournament


class CatalogSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    source_type: SourceType
    label: str


class CatalogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tournament: Tournament
    schedule_aliases: list[str] = Field(default_factory=list)
    source_url: str
    source_type: SourceType = SourceType.TRUSTED_SECONDARY

    @model_validator(mode="after")
    def aliases_are_unique(self) -> "CatalogEvent":
        folded = [alias.casefold() for alias in self.schedule_aliases]
        if len(folded) != len(set(folded)):
            raise ValueError("schedule aliases must be unique")
        return self


class TournamentCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1968)
    retrieved_at: datetime
    tracking_started_at: date
    sources: list[CatalogSource]
    events: list[CatalogEvent]

    @model_validator(mode="after")
    def events_are_unique(self) -> "TournamentCatalog":
        ids = [event.tournament.tournament_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog tournament IDs must be unique")
        return self
