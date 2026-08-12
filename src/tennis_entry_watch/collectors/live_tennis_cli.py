import argparse
from pathlib import Path

from tennis_entry_watch.collectors.live_tennis import (
    LiveTennisCollector,
    write_snapshot_if_changed,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and validate Live Tennis ATP rankings and schedules")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/rankings/atp-live-current.json"),
    )
    args = parser.parse_args()
    snapshot = LiveTennisCollector().collect()
    changed = write_snapshot_if_changed(snapshot, args.output)
    state = "updated" if changed else "unchanged"
    print(
        f"{state}: {len(snapshot.rankings)} rankings, "
        f"{len(snapshot.schedules)} schedules -> {args.output}"
    )


if __name__ == "__main__":
    main()
