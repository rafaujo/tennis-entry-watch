import argparse
from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.live_tennis_snapshot import load_live_snapshot
from tennis_entry_watch.collectors.published_draws import collect_configured_draws
from tennis_entry_watch.collectors.tournament_catalog import load_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill published tournament draws")
    parser.add_argument("--config", type=Path, default=Path("data/tournaments/draw_sources.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/tournaments/catalog.json"))
    parser.add_argument("--ranking", type=Path, default=Path("data/rankings/atp-live-current.json"))
    parser.add_argument("--output", type=Path, default=Path("data/entry-snapshots"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    updated, warnings = collect_configured_draws(
        args.config,
        load_catalog(args.catalog),
        load_live_snapshot(args.ranking),
        args.output,
        as_of=args.as_of,
    )
    print(f"published draws: {updated} updated")
    for warning in warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()
