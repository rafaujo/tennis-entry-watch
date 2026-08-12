from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .player import Player
from .tournament import Tournament


class EntryStatus(StrEnum):
    DA = "DA"
    PR = "PR"
    WC = "WC"
    Q = "Q"
    LL = "LL"
    SE = "SE"
    ALT = "ALT"
    OUT = "OUT"


class SourceType(StrEnum):
    ATP_OFFICIAL = "atp_official"
    TOURNAMENT_OFFICIAL = "tournament_official"
    TRUSTED_SECONDARY = "trusted_secondary"
    MANUAL = "manual"
    AI_EXTRACTED = "ai_extracted"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    retrieved_at: datetime
    source_type: SourceType
    collector: str


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player: Player
    status: EntryStatus
    entry_rank: int | None = Field(default=None, gt=0)
    current_rank: int | None = Field(default=None, gt=0)
    alternate_position: int | None = Field(default=None, gt=0)
    seed: int | None = Field(default=None, gt=0)
    projected_seed: int | None = Field(default=None, gt=0)
    previous_status: EntryStatus | None = None
    withdrawn_at: datetime | None = None
    source: Source

    @model_validator(mode="after")
    def status_fields_are_consistent(self) -> "Entry":
        if self.status == EntryStatus.ALT and self.alternate_position is None:
            raise ValueError("ALT entries require alternate_position")
        if self.status != EntryStatus.ALT and self.alternate_position is not None:
            raise ValueError("alternate_position is only valid for ALT entries")
        if self.status == EntryStatus.OUT and self.previous_status is None:
            raise ValueError("OUT entries require previous_status")
        if self.status != EntryStatus.OUT and self.withdrawn_at is not None:
            raise ValueError("withdrawn_at is only valid for OUT entries")
        return self


class EntryList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tournament: Tournament
    snapshot_at: datetime
    entries: list[Entry]

    @model_validator(mode="after")
    def entries_are_unique(self) -> "EntryList":
        player_ids = [entry.player.player_id for entry in self.entries]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("a player may appear only once in an entry list")
        alt_positions = [
            entry.alternate_position for entry in self.entries
            if entry.status == EntryStatus.ALT
        ]
        if len(alt_positions) != len(set(alt_positions)):
            raise ValueError("alternate positions must be unique")
        return self

