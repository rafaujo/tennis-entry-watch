import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from tennis_entry_watch.collectors.base import ParsingFailed, SourceUnavailable
from tennis_entry_watch.models import (
    CatalogEvent,
    CatalogSource,
    Location,
    SourceType,
    Surface,
    Tournament,
    TournamentCatalog,
)


WIKIPEDIA_TOUR_URL = "https://en.wikipedia.org/wiki/{year}_ATP_Tour"
WIKIPEDIA_CHALLENGER_URL = "https://en.wikipedia.org/wiki/{year}_ATP_Challenger_Tour"
ATP_TOUR_CALENDAR_URL = "https://www.atptour.com/en/tournaments"
ATP_CHALLENGER_CALENDAR_URL = "https://www.atptour.com/en/challenger-tour/calendar"
USER_AGENT = "TennisEntryWatch/0.1 (+https://github.com/rafaujo/tennis-entry-watch)"

MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        1,
    )
}
SHORT_MONTHS = {name[:3]: number for name, number in MONTHS.items()}
DATE_PATTERNS = (
    re.compile(
        r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})\b"
    ),
    re.compile(
        r"\b(\d{1,2})\s+(" + "|".join(SHORT_MONTHS) + r")\b"
    ),
)
CATEGORY_PATTERN = re.compile(
    r"Grand Slam|ATP Finals|ATP (?:1000|500|250)|Challenger (?:175|125|100|75|50)"
)
DRAW_PATTERN = re.compile(r"(?P<main>\d+)S(?:/(?P<qualifying>\d+)Q)?")
SURFACE_PATTERN = re.compile(r"Hard(?: \(i\))?|Clay|Grass|Carpet")


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    result = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not result:
        raise ParsingFailed(f"could not derive a tournament ID from {value!r}")
    return result


def _date_from_text(text: str, year: int) -> date | None:
    matches: list[tuple[int, date]] = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            if pattern is DATE_PATTERNS[0]:
                month, day = MONTHS[match.group(1)], int(match.group(2))
            else:
                month, day = SHORT_MONTHS[match.group(2)], int(match.group(1))
            matches.append((match.start(), date(year, month, day)))
    return min(matches, default=(0, None), key=lambda item: item[0])[1]


def _surface(text: str) -> Surface:
    match = SURFACE_PATTERN.search(text)
    if not match:
        raise ParsingFailed(f"surface not found in tournament row: {text[:120]}")
    value = match.group(0)
    if value.startswith("Hard"):
        return Surface.HARD
    return Surface(value)


def _qualifier_slots(category: str, main_draw: int) -> int | None:
    if category.startswith("Challenger"):
        return 4 if main_draw == 28 else 6 if main_draw == 32 else None
    return {28: 4, 32: 4, 48: 6, 56: 8, 64: 8, 96: 12, 128: 16}.get(main_draw)


def _wildcard_slots(category: str, main_draw: int) -> int | None:
    if category.startswith("Challenger"):
        return 3
    return 3 if main_draw <= 32 else 4 if main_draw < 128 else 8


def parse_calendar_page(page_html: str, year: int, source_url: str) -> list[CatalogEvent]:
    soup = BeautifulSoup(page_html, "html.parser")
    results: list[CatalogEvent] = []
    current_start: date | None = None
    calendar_rows = []
    for table in soup.select("table.wikitable"):
        first_row = table.find("tr")
        headers = [" ".join(cell.stripped_strings) for cell in first_row.find_all("th", recursive=False)] if first_row else []
        if len(headers) >= 2 and headers[0] in {"Week", "Week of"} and headers[1] == "Tournament":
            calendar_rows.extend(table.select("tr"))

    for row in calendar_rows:
        cells = row.find_all(["th", "td"], recursive=False)
        for cell in cells:
            parsed_date = _date_from_text(" ".join(cell.stripped_strings), year)
            if parsed_date:
                current_start = parsed_date
                break
        candidate = None
        for cell in cells:
            text = " ".join(cell.stripped_strings)
            if CATEGORY_PATTERN.search(text) and DRAW_PATTERN.search(text) and cell.find("a"):
                candidate = cell
                break
        if candidate is None:
            continue
        if current_start is None:
            continue

        text = " ".join(candidate.stripped_strings)
        category_matches = list(CATEGORY_PATTERN.finditer(text))
        category_match = category_matches[-1] if category_matches else None
        draw_match = DRAW_PATTERN.search(text)
        name_link = candidate.find("a")
        if not category_match or not draw_match or not name_link:
            continue

        name = " ".join(name_link.stripped_strings)
        location_text = text[: category_match.start()].strip()
        if location_text.startswith(name):
            location_text = location_text[len(name) :].strip()
        if "," not in location_text:
            continue
        city, country = (part.strip() for part in location_text.rsplit(",", 1))

        category = category_match.group(0)
        main_draw = int(draw_match.group("main"))
        qualifying_draw = (
            int(draw_match.group("qualifying")) if draw_match.group("qualifying") else None
        )
        duration = 13 if category == "Grand Slam" else 6
        tournament = Tournament(
            tournament_id=f"{_slug(name)}-{year}",
            name=name,
            year=year,
            start_date=current_start,
            end_date=current_start + timedelta(days=duration),
            category=category,
            surface=_surface(text),
            location=Location(city=city, country=country),
            main_draw_size=main_draw,
            qualifying_draw_size=qualifying_draw,
            main_draw_qualifier_slots=_qualifier_slots(category, main_draw),
            main_draw_wildcard_slots=_wildcard_slots(category, main_draw),
            draw_published=False,
            qualifying_list_published=False,
        )
        results.append(
            CatalogEvent(
                tournament=tournament,
                schedule_aliases=[city, name],
                source_url=source_url,
            )
        )

    if not results:
        raise ParsingFailed("no tournament calendar rows were found")
    return results


def _load_overrides(path: Path) -> dict:
    if not path.exists():
        return {"tracking_started_at": date.today().isoformat(), "events": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_overrides(events: list[CatalogEvent], overrides: dict) -> list[CatalogEvent]:
    by_key = {
        (item.get("source_name"), item.get("source_start_date")): item
        for item in overrides.get("events", [])
    }
    updated: list[CatalogEvent] = []
    used_ids: set[str] = set()
    for event in events:
        tournament = event.tournament
        override = by_key.get((tournament.name, tournament.start_date.isoformat()), {})
        tournament_data = tournament.model_dump(mode="json")
        for field in (
            "tournament_id", "name", "start_date", "end_date", "category", "surface",
            "main_draw_size", "qualifying_draw_size", "main_draw_qualifier_slots",
            "main_draw_wildcard_slots",
        ):
            if field in override:
                tournament_data[field] = override[field]
        if "city" in override:
            tournament_data["location"]["city"] = override["city"]
        if "country" in override:
            tournament_data["location"]["country"] = override["country"]
        tournament_data["year"] = int(str(tournament_data["start_date"])[:4])
        aliases = override.get("schedule_aliases", event.schedule_aliases)
        normalized = CatalogEvent(
            tournament=Tournament.model_validate(tournament_data),
            schedule_aliases=list(dict.fromkeys(aliases)),
            source_url=event.source_url,
            source_type=event.source_type,
        )
        identifier = normalized.tournament.tournament_id
        if identifier in used_ids:
            tournament_data = normalized.tournament.model_dump(mode="json")
            tournament_data["tournament_id"] = (
                f"{identifier}-{normalized.tournament.start_date:%m%d}"
            )
            normalized = normalized.model_copy(
                update={"tournament": Tournament.model_validate(tournament_data)}
            )
        used_ids.add(normalized.tournament.tournament_id)
        updated.append(normalized)
    return updated


class TournamentCatalogCollector:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def _get(self, url: str) -> str:
        try:
            response = self.session.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceUnavailable(f"could not retrieve {url}: {exc}") from exc
        response.encoding = "utf-8"
        return response.text

    def collect(
        self,
        year: int,
        overrides_path: Path,
        retrieved_at: datetime | None = None,
    ) -> TournamentCatalog:
        tour_url = WIKIPEDIA_TOUR_URL.format(year=year)
        challenger_url = WIKIPEDIA_CHALLENGER_URL.format(year=year)
        events = [
            *parse_calendar_page(self._get(tour_url), year, tour_url),
            *parse_calendar_page(self._get(challenger_url), year, challenger_url),
        ]
        overrides = _load_overrides(overrides_path)
        events = _apply_overrides(events, overrides)
        tour_count = sum(
            event.tournament.category == "Grand Slam"
            or event.tournament.category.startswith("ATP")
            for event in events
        )
        challenger_count = sum(
            event.tournament.category.startswith("Challenger") for event in events
        )
        if tour_count < 50 or challenger_count < 100:
            raise ParsingFailed(
                f"calendar is suspiciously small: {tour_count} tour, "
                f"{challenger_count} challenger events"
            )
        events.sort(key=lambda item: (item.tournament.start_date, item.tournament.name))
        return TournamentCatalog(
            year=year,
            retrieved_at=retrieved_at or datetime.now(timezone.utc),
            tracking_started_at=overrides["tracking_started_at"],
            sources=[
                CatalogSource(
                    url=tour_url,
                    source_type=SourceType.TRUSTED_SECONDARY,
                    label="Wikipedia ATP Tour annual calendar",
                ),
                CatalogSource(
                    url=challenger_url,
                    source_type=SourceType.TRUSTED_SECONDARY,
                    label="Wikipedia ATP Challenger Tour annual calendar",
                ),
                CatalogSource(
                    url=ATP_TOUR_CALENDAR_URL,
                    source_type=SourceType.ATP_OFFICIAL,
                    label="ATP official tour calendar verification",
                ),
                CatalogSource(
                    url=ATP_CHALLENGER_CALENDAR_URL,
                    source_type=SourceType.ATP_OFFICIAL,
                    label="ATP official Challenger calendar verification",
                ),
            ],
            events=events,
        )


def load_catalog(path: Path) -> TournamentCatalog:
    return TournamentCatalog.model_validate_json(path.read_text(encoding="utf-8-sig"))


def _semantic_payload(catalog: TournamentCatalog) -> dict:
    payload = catalog.model_dump(mode="json")
    payload.pop("retrieved_at", None)
    return payload


def write_catalog_if_changed(catalog: TournamentCatalog, output: Path) -> bool:
    if output.exists():
        previous = load_catalog(output)
        if previous.year != catalog.year:
            merged_events = {
                event.tournament.tournament_id: event
                for event in [*previous.events, *catalog.events]
            }
            merged_sources = {
                source.url: source for source in [*previous.sources, *catalog.sources]
            }
            catalog = catalog.model_copy(
                update={
                    "tracking_started_at": min(
                        previous.tracking_started_at, catalog.tracking_started_at
                    ),
                    "sources": list(merged_sources.values()),
                    "events": sorted(
                        merged_events.values(),
                        key=lambda item: (
                            item.tournament.start_date,
                            item.tournament.name,
                        ),
                    ),
                }
            )
        if _semantic_payload(previous) == _semantic_payload(catalog):
            return False
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return True
