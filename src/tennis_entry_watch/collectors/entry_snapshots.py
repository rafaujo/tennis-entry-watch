import json
from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.live_tennis_snapshot import entry_lists_from_live_snapshot
from tennis_entry_watch.models import EntryList, TournamentCatalog


def snapshot_path(root: Path, tournament_id: str) -> Path:
    return root / tournament_id / "current.json"


def load_entry_snapshots(root: Path) -> list[EntryList]:
    return [
        EntryList.model_validate_json(path.read_text(encoding="utf-8-sig"))
        for path in sorted(root.glob("*/current.json"))
    ]


def _semantic_payload(entry_list: EntryList) -> dict:
    payload = entry_list.model_dump(mode="json")
    payload.pop("snapshot_at", None)
    return payload


def write_entry_snapshot(entry_list: EntryList, root: Path) -> bool:
    destination = snapshot_path(root, entry_list.tournament.tournament_id)
    if destination.exists():
        previous = EntryList.model_validate_json(destination.read_text(encoding="utf-8-sig"))
        if _semantic_payload(previous) == _semantic_payload(entry_list):
            return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(entry_list.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return True


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
        has_entries = bool(current.entries or current.qualifying_entries)
        if not has_entries and destination.exists():
            previous = EntryList.model_validate_json(destination.read_text(encoding="utf-8-sig"))
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
