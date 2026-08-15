import argparse
from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.entry_snapshots import retain_live_entry_snapshots
from tennis_entry_watch.collectors.live_tennis_snapshot import load_live_snapshot
from tennis_entry_watch.collectors.tournament_catalog import load_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Retain the last non-empty tournament entry snapshots")
    parser.add_argument("--ranking", type=Path, default=Path("data/rankings/atp-live-current.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/tournaments/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("data/entry-snapshots"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    updated, retained = retain_live_entry_snapshots(
        load_live_snapshot(args.ranking), load_catalog(args.catalog), args.output, args.as_of
    )
    print(f"entry snapshots: {updated} updated, {retained} retained after empty refresh")


if __name__ == "__main__":
    main()
