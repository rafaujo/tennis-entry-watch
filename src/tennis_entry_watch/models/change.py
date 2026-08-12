from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from .entry import Source


class ChangeType(StrEnum):
    PLAYER_ADDED = "PLAYER_ADDED"
    PLAYER_REMOVED = "PLAYER_REMOVED"
    PLAYER_WITHDRAWN = "PLAYER_WITHDRAWN"
    ALT_POSITION_CHANGED = "ALT_POSITION_CHANGED"
    ALT_TO_MAIN_DRAW = "ALT_TO_MAIN_DRAW"
    STATUS_CHANGED = "STATUS_CHANGED"
    ENTRY_RANK_CHANGED = "ENTRY_RANK_CHANGED"


class EntryChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tournament_id: str
    player_id: str
    player_name: str
    change_type: ChangeType
    old_value: Any = None
    new_value: Any = None
    detected_at: datetime
    source: Source

