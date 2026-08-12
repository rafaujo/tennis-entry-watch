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
        "start": "2026-08-18",
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
        "start": "2026-08-18",
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
    {
        "id": "kingston-2-challenger-2026",
        "event": "Kingston 2",
        "name": "Kingston 2",
        "category": "Challenger 75",
        "city": "Kingston",
        "country": "Jamaica",
        "surface": Surface.HARD,
        "start": "2026-08-24",
        "end": "2026-08-29",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "roehampton-2-challenger-2026",
        "event": "Roehampton 2",
        "name": "Roehampton 2",
        "category": "Challenger 50",
        "city": "Roehampton",
        "country": "Great Britain",
        "surface": Surface.HARD,
        "start": "2026-08-24",
        "end": "2026-08-29",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "augsburg-challenger-2026",
        "event": "Augsburg",
        "name": "Schwaben Open",
        "category": "Challenger 50",
        "city": "Augsburg",
        "country": "Germany",
        "surface": Surface.CLAY,
        "start": "2026-08-24",
        "end": "2026-08-29",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "zhangjiagang-challenger-2026",
        "event": "Zhangjiagang",
        "name": "International Challenger-Zhangjiagang",
        "category": "Challenger 75",
        "city": "Zhangjiagang",
        "country": "China",
        "surface": Surface.HARD,
        "start": "2026-08-31",
        "end": "2026-09-06",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "como-challenger-2026",
        "event": "Como",
        "name": "Como Lake Challenger",
        "category": "Challenger 75",
        "city": "Como",
        "country": "Italy",
        "surface": Surface.CLAY,
        "start": "2026-08-31",
        "end": "2026-09-06",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "porto-1-challenger-2026",
        "event": "Porto 1",
        "name": "CT PORTO CUP",
        "category": "Challenger 75",
        "city": "Porto",
        "country": "Portugal",
        "surface": Surface.CLAY,
        "start": "2026-08-31",
        "end": "2026-09-06",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "plovdiv-3-challenger-2026",
        "event": "Plovdiv 3",
        "name": "Plovdiv 3",
        "category": "Challenger 50",
        "city": "Plovdiv",
        "country": "Bulgaria",
        "surface": Surface.CLAY,
        "start": "2026-08-31",
        "end": "2026-09-06",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
    {
        "id": "manacor-challenger-2026",
        "event": "Manacor",
        "name": "Rafa Nadal Open by Movistar",
        "category": "Challenger 75",
        "city": "Manacor",
        "country": "Spain",
        "surface": Surface.HARD,
        "start": "2026-09-01",
        "end": "2026-09-06",
        "draw": 32,
        "q_draw": 24,
        "q_slots": 6,
        "wc_slots": 3,
    },
)


def _entry(
    item: dict,
    status: EntryStatus,
    source: Source,
    alternate_position: int | None = None,
) -> Entry:
    return Entry(
        player=Player(
            player_id=stable_player_id(item["name"]),
            name=item["name"],
            nationality=item.get("nation") or None,
        ),
        status=status,
        current_rank=item.get("rank"),
        alternate_position=alternate_position,
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
        qualifying = sorted(
            (item for item in schedules if qualifying_label in item.get("events", [])),
            key=lambda item: (item.get("rank") or 99999, item["name"]),
        )
        qualifying_acceptances = qualifying[:spec["q_draw"]]
        qualifying_alternates = qualifying[spec["q_draw"]:]
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
            qualifying_list_published=bool(qualifying),
        )
        results.append(
            EntryList(
                tournament=tournament,
                snapshot_at=retrieved_at,
                entries=[_entry(item, EntryStatus.DA, source) for item in main],
                qualifying_entries=[
                    *(_entry(item, EntryStatus.QDA, source) for item in qualifying_acceptances),
                    *(
                        _entry(item, EntryStatus.QALT, source, position)
                        for position, item in enumerate(qualifying_alternates, 1)
                    ),
                ],
            )
        )
    return results


def load_live_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))
