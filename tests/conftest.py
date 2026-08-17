from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from tennis_entry_watch.models import (
    CatalogEvent,
    EntryList,
    Location,
    Surface,
    Tournament,
    TournamentCatalog,
)


ROOT = Path(__file__).parents[1]


@pytest.fixture
def previous() -> EntryList:
    return EntryList.model_validate_json((ROOT / "data/entries/sample-open-2026/previous.json").read_text())


@pytest.fixture
def current() -> EntryList:
    return EntryList.model_validate_json((ROOT / "data/entries/sample-open-2026/current.json").read_text())


@pytest.fixture
def synthetic_catalog() -> TournamentCatalog:
    tournament = Tournament(
        tournament_id="fixture-open-2026",
        name="Fixture Open",
        year=2026,
        start_date=date(2026, 8, 18),
        end_date=date(2026, 8, 23),
        category="Challenger 75",
        surface=Surface.HARD,
        location=Location(city="Testville", country="Testland"),
        main_draw_size=28,
        qualifying_draw_size=4,
        main_draw_qualifier_slots=4,
        main_draw_wildcard_slots=3,
        draw_published=False,
        qualifying_list_published=False,
    )
    return TournamentCatalog(
        year=2026,
        retrieved_at=datetime(2026, 8, 15, 12, tzinfo=timezone.utc),
        tracking_started_at=date(2026, 8, 12),
        sources=[],
        events=[
            CatalogEvent(
                tournament=tournament,
                schedule_aliases=["Fixture Open"],
                source_url="https://example.test/calendar",
            )
        ],
    )


@pytest.fixture
def synthetic_live_snapshot() -> dict:
    return {
        "retrieved_at": "2026-08-15T12:00:00Z",
        "schedule_source": "https://example.test/schedules",
        "rankings": [],
        "schedules": [
            {"name": "Main Player One", "nation": "USA", "rank": 101, "events": ["Fixture Open"]},
            {"name": "Main Player Two", "nation": "BRA", "rank": 202, "events": ["Fixture Open"]},
            *[
                {
                    "name": f"Qualifying Player {index}",
                    "nation": "FRA",
                    "rank": 300 + index,
                    "events": ["Qual. Fixture Open"],
                }
                for index in range(1, 7)
            ],
        ],
    }

