import pytest
from pydantic import ValidationError

from tennis_entry_watch.models import EntryList


def test_sample_snapshots_validate(previous, current):
    assert len(previous.entries) == 4
    assert len(current.entries) == 5


def test_duplicate_player_is_rejected(current):
    data = current.model_dump()
    data["entries"].append(data["entries"][0])
    with pytest.raises(ValidationError, match="only once"):
        EntryList.model_validate(data)


def test_duplicate_alternate_position_is_rejected(current):
    data = current.model_dump()
    duplicate = data["entries"][-1]
    duplicate["status"] = "ALT"
    duplicate["alternate_position"] = 1
    with pytest.raises(ValidationError, match="alternate positions"):
        EntryList.model_validate(data)


def test_invalid_rank_is_rejected(current):
    data = current.model_dump()
    data["entries"][0]["entry_rank"] = 0
    with pytest.raises(ValidationError):
        EntryList.model_validate(data)


def test_alt_requires_position(current):
    data = current.model_dump()
    data["entries"][3]["alternate_position"] = None
    with pytest.raises(ValidationError, match="require alternate_position"):
        EntryList.model_validate(data)

