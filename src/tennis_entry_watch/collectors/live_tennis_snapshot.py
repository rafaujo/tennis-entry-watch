import json
from datetime import date, datetime, timedelta
from pathlib import Path

from tennis_entry_watch.models import (
    CatalogEvent,
    Entry,
    EntryList,
    EntryStatus,
    Player,
    Source,
    SourceType,
    Tournament,
    TournamentCatalog,
    TournamentStatus,
)
from tennis_entry_watch.normalize.players import stable_player_id


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


def tournament_status(tournament: Tournament, as_of: date) -> TournamentStatus:
    if tournament.end_date and tournament.end_date < as_of:
        return TournamentStatus.COMPLETE
    if tournament.start_date <= as_of <= (tournament.end_date or tournament.start_date):
        return TournamentStatus.ACTIVE
    return TournamentStatus.UPCOMING


def _scheduled_for(item: dict, aliases: list[str], qualifying: bool = False) -> bool:
    labels = {
        f"Qual. {alias}" if qualifying else alias
        for alias in aliases
    }
    return bool(labels.intersection(item.get("events", [])))


def entry_list_from_catalog_event(
    snapshot: dict,
    catalog_event: CatalogEvent,
    as_of: date,
) -> EntryList:
    retrieved_at = datetime.fromisoformat(snapshot["retrieved_at"].replace("Z", "+00:00"))
    source = Source(
        url=snapshot["schedule_source"],
        retrieved_at=retrieved_at,
        source_type=SourceType.TRUSTED_SECONDARY,
        collector="live_tennis_schedule_snapshot",
    )
    schedules = snapshot.get("schedules", [])
    aliases = catalog_event.schedule_aliases
    main = [item for item in schedules if _scheduled_for(item, aliases)]
    qualifying = sorted(
        (item for item in schedules if _scheduled_for(item, aliases, qualifying=True)),
        key=lambda item: (item.get("rank") or 99999, item["name"]),
    )
    tournament = catalog_event.tournament.model_copy(
        update={
            "status": tournament_status(catalog_event.tournament, as_of),
            "qualifying_list_published": bool(qualifying),
        }
    )
    q_draw = tournament.qualifying_draw_size or len(qualifying)
    qualifying_acceptances = qualifying[:q_draw]
    qualifying_alternates = qualifying[q_draw:]
    return EntryList(
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


def entry_lists_from_live_snapshot(
    snapshot: dict,
    catalog: TournamentCatalog | None = None,
    as_of: date | None = None,
) -> list[EntryList]:
    if catalog is None:
        default_path = Path("data/tournaments/catalog.json")
        if not default_path.exists():
            return []
        catalog = TournamentCatalog.model_validate_json(
            default_path.read_text(encoding="utf-8-sig")
        )
    reference_date = as_of or date.today()
    current_week = reference_date - timedelta(days=reference_date.weekday())
    window_end = current_week + timedelta(weeks=6, days=-1)
    return [
        entry_list_from_catalog_event(snapshot, event, reference_date)
        for event in catalog.events
        if (event.tournament.end_date or event.tournament.start_date)
        >= catalog.tracking_started_at
        and (
            tournament_status(event.tournament, reference_date) == TournamentStatus.ACTIVE
            or event.tournament.start_date <= window_end
        )
    ]


def load_live_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))
