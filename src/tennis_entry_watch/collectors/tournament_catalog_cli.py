import argparse
from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.tournament_catalog import (
    TournamentCatalogCollector,
    write_catalog_if_changed,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and validate ATP tournament calendars")
    parser.add_argument("--year", type=int, default=date.today().year)
    parser.add_argument(
        "--overrides",
        type=Path,
        default=Path("data/tournaments/overrides.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/tournaments/catalog.json"),
    )
    args = parser.parse_args()
    catalog = TournamentCatalogCollector().collect(args.year, args.overrides)
    changed = write_catalog_if_changed(catalog, args.output)
    tour_count = sum(
        event.tournament.category == "Grand Slam"
        or event.tournament.category.startswith("ATP")
        for event in catalog.events
    )
    challenger_count = len(catalog.events) - tour_count
    print(
        f"{'updated' if changed else 'unchanged'}: {tour_count} tour, "
        f"{challenger_count} challenger events -> {args.output}"
    )


if __name__ == "__main__":
    main()
