from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    nationality: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    atp_id: str | None = None
    birth_date: date | None = None

