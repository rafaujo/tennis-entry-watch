import json
from datetime import datetime
from pathlib import Path

from tennis_entry_watch.models import (
    Entry,
    EntryList,
    EntryStatus,
    Location,
    Player,
    Source,
    SourceType,
    Surface,
    Tournament,
)
from tennis_entry_watch.normalize.players import stable_player_id


TOURNAMENTS = (
    {
        "id": "cancun-challenger-2026",
        "event": "Cancun",
        "name": "Europcar Cancun Country Club",
        "category": "Challenger 125",
        "city": "Cancun",
        "country": "Mexico",
        "surface": Surface.HARD,
        "start": "2026-08-17",
        "end": "2026-08-23",
        "draw": 28,
        "q_draw": 16,
        "q_slots": 4,
        "wc_slots": 3,
    },
    {
        "id": "quebec-city-challenger-2026",
        "event": "Quebec City",
        "name": "Quebec National Bank Challenger",
        "category": "Challenger 125",
        "city": "Quebec City",
        "country": "Canada",
        "surface": Surface.HARD,
        "start": "2026-08-17",
        "end": "2026-08-23",
        "draw": 28,
        "q_draw": 16,
        "q_slots": 4,
        "wc_slots": 3,
    },
    {
        "id": "kingston-1-challenger-2026",
        "event": "Kingston",
        "name": "Kingston 1",
        "category": "Challenger 75",
        "city": "Kingston",
        "country": "Jamaica",
        "surface": Surface.HARD,
        "start": "2026-08-17",
        "end": "2026-08-22",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "prague-challenger-2026",
        "event": "Prague",
        "name": "Advantage Cars Prague Open",
        "category": "Challenger 75",
        "city": "Prague",
        "country": "Czech Republic",
        "surface": Surface.CLAY,
        "start": "2026-08-17",
        "end": "2026-08-22",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "roehampton-1-challenger-2026",
        "event": "Roehampton",
        "name": "Roehampton 1",
        "category": "Challenger 50",
        "city": "Roehampton",
        "country": "Great Britain",
        "surface": Surface.HARD,
        "start": "2026-08-17",
        "end": "2026-08-22",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "sion-challenger-2026",
        "event": "Sion",
        "name": "Sion Challenger",
        "category": "Challenger 50",
        "city": "Sion",
        "country": "Switzerland",
        "surface": Surface.CLAY,
        "start": "2026-08-17",
        "end": "2026-08-22",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
)


def _entry(item: dict, status: EntryStatus, source: Source) -> Entry:
    return Entry(
        player=Player(
            player_id=stable_player_id(item["name"]),
            name=item["name"],
            nationality=item.get("nation") or None,
        ),
        status=status,
        current_rank=item.get("rank"),
        source=source,
    )


def entry_lists_from_live_snapshot(snapshot: dict) -> list[EntryList]:
    retrieved_at = datetime.fromisoformat(snapshot["retrieved_at"].replace("Z", "+00:00"))
    source = Source(
        url=snapshot["schedule_source"],
        retrieved_at=retrieved_at,
        source_type=SourceType.TRUSTED_SECONDARY,
        collector="live_tennis_schedule_snapshot",
    )
    schedules = snapshot.get("schedules", [])
    results = []
    for spec in TOURNAMENTS:
        main = [item for item in schedules if spec["event"] in item.get("events", [])]
        qualifying_label = f'Qual. {spec["event"]}'
        qualifying = [item for item in schedules if qualifying_label in item.get("events", [])]
        tournament = Tournament(
            tournament_id=spec["id"],
            name=spec["name"],
            year=2026,
            start_date=spec["start"],
            end_date=spec["end"],
            category=spec["category"],
            surface=spec["surface"],
            location=Location(city=spec["city"], country=spec["country"]),
            main_draw_size=spec["draw"],
            qualifying_draw_size=spec["q_draw"],
            main_draw_qualifier_slots=spec["q_slots"],
            main_draw_wildcard_slots=spec["wc_slots"],
            draw_published=False,
            qualifying_list_published=True,
        )
        results.append(
            EntryList(
                tournament=tournament,
                snapshot_at=retrieved_at,
                entries=[_entry(item, EntryStatus.DA, source) for item in main],
                qualifying_entries=[_entry(item, EntryStatus.QDA, source) for item in qualifying],
            )
        )
    return results


def load_live_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))
