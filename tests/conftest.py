from pathlib import Path

import pytest

from tennis_entry_watch.models import EntryList


ROOT = Path(__file__).parents[1]


@pytest.fixture
def previous() -> EntryList:
    return EntryList.model_validate_json((ROOT / "data/entries/sample-open-2026/previous.json").read_text())


@pytest.fixture
def current() -> EntryList:
    return EntryList.model_validate_json((ROOT / "data/entries/sample-open-2026/current.json").read_text())

