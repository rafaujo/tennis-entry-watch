import argparse
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from tennis_entry_watch.collectors.entry_snapshots import load_entry_snapshots
from tennis_entry_watch.collectors.live_tennis_snapshot import tournament_status
from tennis_entry_watch.collectors.tournament_catalog import load_catalog
from tennis_entry_watch.models import EntryList, EntryStatus, TournamentCatalog, TournamentStatus


MAIN_DRAW_STATUSES = {
    EntryStatus.DA,
    EntryStatus.PR,
    EntryStatus.WC,
    EntryStatus.Q,
    EntryStatus.LL,
    EntryStatus.SE,
}


@dataclass
class QualityResult:
    markdown: str
    errors: list[str]


def _load_merged_entries(data_root: Path, snapshot_root: Path) -> dict[str, EntryList]:
    retained = load_entry_snapshots(snapshot_root) if snapshot_root.exists() else []
    verified = load_entry_snapshots(data_root) if data_root.exists() else []
    merged = {item.tournament.tournament_id: item for item in retained}
    for item in verified:
        tournament_id = item.tournament.tournament_id
        published = merged.get(tournament_id)
        if published is None or not published.tournament.draw_published:
            merged[tournament_id] = item
    return merged


def validate_quality(
    catalog: TournamentCatalog,
    entry_lists: dict[str, EntryList],
    as_of: date | None = None,
) -> QualityResult:
    reference_date = as_of or date.today()
    current_week = reference_date - timedelta(days=reference_date.weekday())
    window_end = current_week + timedelta(weeks=6, days=-1)
    errors: list[str] = []
    rows = []

    for catalog_event in catalog.events:
        tournament = catalog_event.tournament
        status = tournament_status(tournament, reference_date)
        if status == TournamentStatus.COMPLETE or tournament.start_date > window_end:
            continue
        entry_list = entry_lists.get(tournament.tournament_id)
        main_count = 0
        qualifying_count = 0
        source = "not found"
        if entry_list:
            main_count = sum(entry.status in MAIN_DRAW_STATUSES for entry in entry_list.entries)
            qualifying_count = sum(
                entry.status in {EntryStatus.QDA, EntryStatus.WC}
                for entry in entry_list.qualifying_entries
            )
            sources = {
                entry.source.source_type.value
                for entry in [*entry_list.entries, *entry_list.qualifying_entries]
            }
            source = ", ".join(sorted(sources)) or "empty snapshot"

        if tournament.main_draw_size and main_count > tournament.main_draw_size:
            errors.append(
                f"{tournament.name}: {main_count} main-draw players exceeds "
                f"the configured size {tournament.main_draw_size}"
            )
        if tournament.qualifying_draw_size and qualifying_count > tournament.qualifying_draw_size:
            errors.append(
                f"{tournament.name}: {qualifying_count} qualifying acceptances exceeds "
                f"the configured size {tournament.qualifying_draw_size}"
            )
        if status == TournamentStatus.ACTIVE and tournament.draw_published and main_count == 0:
            errors.append(f"{tournament.name}: published active draw has no players")

        rows.append(
            f"| {tournament.name} | {status.value} | {main_count} | "
            f"{qualifying_count} | {source} |"
        )

    heading = "## Tennis data quality\n\n"
    summary = (
        "✅ No blocking data-quality errors."
        if not errors
        else "❌ Blocking errors:\n" + "\n".join(f"- {error}" for error in errors)
    )
    table = (
        "\n\n| Tournament | Phase | Main | Qualifying | Source |\n"
        "|---|---:|---:|---:|---|\n"
        + "\n".join(rows)
    )
    return QualityResult(markdown=heading + summary + table + "\n", errors=errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and summarize current tennis data")
    parser.add_argument("--catalog", type=Path, default=Path("data/tournaments/catalog.json"))
    parser.add_argument("--data-root", type=Path, default=Path("data/entries"))
    parser.add_argument("--snapshot-root", type=Path, default=Path("data/entry-snapshots"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    result = validate_quality(
        load_catalog(args.catalog),
        _load_merged_entries(args.data_root, args.snapshot_root),
        args.as_of,
    )
    print(result.markdown)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(result.markdown)
    if result.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
