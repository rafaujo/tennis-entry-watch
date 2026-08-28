import json
from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.live_tennis_snapshot import entry_lists_from_live_snapshot
from tennis_entry_watch.models import (
    EntryList,
    EntryStatus,
    SourceType,
    TournamentCatalog,
)


PROJECTED_MAIN_ALTERNATE_COLLECTORS = {
    "live_tennis_schedule_snapshot",
    "qualifying_draw_main_alternate_projection",
}


def is_projected_main_alternate(entry) -> bool:
    return (
        entry.status == EntryStatus.ALT
        and entry.source.collector in PROJECTED_MAIN_ALTERNATE_COLLECTORS
    )


def snapshot_path(root: Path, tournament_id: str) -> Path:
    return root / tournament_id / "current.json"


def predraw_snapshot_path(root: Path, tournament_id: str) -> Path:
    return root / tournament_id / "predraw.json"


def load_entry_snapshots(root: Path) -> list[EntryList]:
    return [
        EntryList.model_validate_json(path.read_text(encoding="utf-8-sig"))
        for path in sorted(root.glob("*/current.json"))
    ]


def _semantic_payload(entry_list: EntryList) -> dict:
    payload = entry_list.model_dump(mode="json")
    payload.pop("snapshot_at", None)
    return payload


def _write_json(entry_list: EntryList, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(entry_list.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def _predraw_richness(entry_list: EntryList) -> tuple[int, int]:
    alternates = sum(
        entry.status in {EntryStatus.ALT, EntryStatus.QALT}
        for entry in [*entry_list.entries, *entry_list.qualifying_entries]
    )
    return alternates, len(entry_list.entries) + len(entry_list.qualifying_entries)


def _retain_predraw_snapshot(entry_list: EntryList, root: Path) -> None:
    if entry_list.tournament.draw_published:
        return
    destination = predraw_snapshot_path(
        root,
        entry_list.tournament.tournament_id,
    )
    if destination.exists():
        previous = EntryList.model_validate_json(
            destination.read_text(encoding="utf-8-sig")
        )
        if _semantic_payload(previous) == _semantic_payload(entry_list):
            return
        if _predraw_richness(entry_list) < _predraw_richness(previous):
            return
    _write_json(entry_list, destination)


def write_entry_snapshot(entry_list: EntryList, root: Path) -> bool:
    destination = snapshot_path(root, entry_list.tournament.tournament_id)
    previous = None
    if destination.exists():
        previous = EntryList.model_validate_json(destination.read_text(encoding="utf-8-sig"))
        if entry_list.tournament.draw_published and not previous.tournament.draw_published:
            _retain_predraw_snapshot(previous, root)
        if _semantic_payload(previous) == _semantic_payload(entry_list):
            return False
    _retain_predraw_snapshot(entry_list, root)
    _write_json(entry_list, destination)
    return True


def project_main_alternates_from_qualifying(entry_list: EntryList) -> EntryList:
    """Fallback projection when no pre-draw main alternate queue was retained."""
    if any(entry.status == EntryStatus.ALT for entry in entry_list.entries):
        return entry_list
    main_ids = {
        entry.player.player_id
        for entry in entry_list.entries
        if entry.status not in {EntryStatus.ALT, EntryStatus.OUT}
    }
    candidates = sorted(
        (
            entry
            for entry in entry_list.qualifying_entries
            if entry.player.player_id not in main_ids
            and entry.status != EntryStatus.OUT
        ),
        key=lambda entry: (
            entry.entry_rank or entry.current_rank or 99999,
            entry.player.name,
        ),
    )
    if not candidates:
        return entry_list
    projected = [
        entry.model_copy(
            update={
                "status": EntryStatus.ALT,
                "alternate_position": position,
                "seed": None,
                "previous_status": None,
                "source": entry.source.model_copy(
                    update={
                        "source_type": SourceType.TRUSTED_SECONDARY,
                        "collector": "qualifying_draw_main_alternate_projection",
                    }
                ),
            }
        )
        for position, entry in enumerate(candidates, 1)
    ]
    return entry_list.model_copy(
        update={"entries": [*entry_list.entries, *projected]}
    )


def merge_published_draw_history(
    published: EntryList,
    history: EntryList,
) -> EntryList:
    """Keep known entry metadata and pre-draw history beside an official draw."""
    has_verified_alternates = any(
        entry.status == EntryStatus.ALT
        and not is_projected_main_alternate(entry)
        for entry in published.entries
    )
    entries = [
        entry
        for entry in published.entries
        if not (
            has_verified_alternates
            and is_projected_main_alternate(entry)
        )
    ]
    published_positions = {
        entry.player.player_id: index
        for index, entry in enumerate(entries)
        if entry.status not in {EntryStatus.ALT, EntryStatus.OUT}
    }

    for previous in history.entries:
        index = published_positions.get(previous.player.player_id)
        if index is None:
            continue
        official = entries[index]
        updates = {}
        if official.entry_rank is None and previous.entry_rank is not None:
            updates["entry_rank"] = previous.entry_rank
        if previous.status == EntryStatus.PR and official.status == EntryStatus.DA:
            updates["status"] = EntryStatus.PR
        elif previous.status == EntryStatus.ALT and official.status != EntryStatus.WC:
            if previous.previous_status == EntryStatus.PR:
                updates["status"] = EntryStatus.PR
            if official.previous_status is None:
                updates["previous_status"] = EntryStatus.ALT
        if (
            previous.previous_status == EntryStatus.ALT
            and official.status != EntryStatus.WC
            and official.previous_status is None
        ):
            updates["previous_status"] = EntryStatus.ALT
        if updates:
            entries[index] = official.model_copy(update=updates)

    official_source = next((entry.source for entry in published.entries), None)
    accepted_statuses = {EntryStatus.DA, EntryStatus.PR, EntryStatus.SE}
    historical_acceptances = sum(
        entry.status in accepted_statuses for entry in history.entries
    )
    draw_looks_complete = len(published_positions) >= historical_acceptances
    entry_ids = {entry.player.player_id for entry in entries}
    entry_positions = {
        entry.player.player_id: index for index, entry in enumerate(entries)
    }
    for previous in history.entries:
        if previous.player.player_id in entry_ids:
            index = entry_positions[previous.player.player_id]
            if (
                previous.status == EntryStatus.ALT
                and not is_projected_main_alternate(previous)
                and is_projected_main_alternate(entries[index])
            ):
                entries[index] = previous
            continue
        if previous.status in {EntryStatus.ALT, EntryStatus.OUT}:
            entries.append(previous)
            entry_ids.add(previous.player.player_id)
            entry_positions[previous.player.player_id] = len(entries) - 1
            continue
        if previous.status in accepted_statuses and draw_looks_complete:
            entries.append(
                previous.model_copy(
                    update={
                        "status": EntryStatus.OUT,
                        "alternate_position": None,
                        "previous_status": previous.status,
                        "withdrawn_at": None,
                        "source": official_source or previous.source,
                    }
                )
            )
            entry_ids.add(previous.player.player_id)
            entry_positions[previous.player.player_id] = len(entries) - 1

    if any(
        entry.status == EntryStatus.ALT
        and not is_projected_main_alternate(entry)
        for entry in entries
    ):
        entries = [
            entry for entry in entries
            if not is_projected_main_alternate(entry)
        ]

    qualifying_entries = list(published.qualifying_entries)
    qualifying_ids = {entry.player.player_id for entry in qualifying_entries}
    qualifying_entries.extend(
        entry
        for entry in history.qualifying_entries
        if entry.status in {EntryStatus.QALT, EntryStatus.OUT}
        and entry.player.player_id not in qualifying_ids
    )

    return published.model_copy(
        update={
            "snapshot_at": max(published.snapshot_at, history.snapshot_at),
            "entries": entries,
            "qualifying_entries": qualifying_entries,
        }
    )


def retain_live_entry_snapshots(
    snapshot: dict,
    catalog: TournamentCatalog,
    output_root: Path,
    as_of: date | None = None,
) -> tuple[int, int]:
    """Persist non-empty schedule lists and never replace them with an empty refresh."""
    updated = retained = 0
    for current in entry_lists_from_live_snapshot(snapshot, catalog, as_of):
        destination = snapshot_path(output_root, current.tournament.tournament_id)
        if destination.exists():
            previous = EntryList.model_validate_json(
                destination.read_text(encoding="utf-8-sig")
            )
            if previous.tournament.draw_published:
                retained += 1
                continue
        has_entries = bool(current.entries or current.qualifying_entries)
        if not has_entries and destination.exists():
            previous = EntryList.model_validate_json(
                destination.read_text(encoding="utf-8-sig")
            )
            tournament = current.tournament.model_copy(
                update={
                    "draw_published": bool(
                        current.tournament.draw_published or previous.tournament.draw_published
                    ),
                    "draw_url": current.tournament.draw_url or previous.tournament.draw_url,
                    "qualifying_list_published": bool(previous.qualifying_entries),
                }
            )
            current = previous.model_copy(update={"tournament": tournament})
            retained += 1
        elif not has_entries:
            continue
        if write_entry_snapshot(current, output_root):
            updated += 1
    return updated, retained
