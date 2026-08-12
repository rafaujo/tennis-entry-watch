import argparse
from pathlib import Path

from tennis_entry_watch.collectors.winston_salem import WinstonSalem2026Collector


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect the official Winston-Salem 2026 entry list")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/entries/winston-salem-open-2026/current.json"),
    )
    args = parser.parse_args()
    entry_list = WinstonSalem2026Collector().collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(entry_list.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(f"validated {len(entry_list.entries)} entries -> {args.output}")


if __name__ == "__main__":
    main()
