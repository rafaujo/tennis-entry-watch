import io
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from tennis_entry_watch.collectors.entry_snapshots import snapshot_path, write_entry_snapshot
from tennis_entry_watch.models import (
    Entry,
    EntryList,
    EntryStatus,
    Player,
    Source,
    SourceType,
    TournamentCatalog,
)
from tennis_entry_watch.normalize.players import stable_player_id


USER_AGENT = "TennisEntryWatch/0.1 (+https://github.com/rafaujo/tennis-entry-watch)"
ATP_TOUR_CALENDAR_URL = "https://www.atptour.com/en/tournaments/"
ATP_DRAW_URL = "https://www.protennislive.com/posting/{year}/{atp_id}/{draw}.pdf"
ATP_DRAW_LOOKAHEAD_DAYS = 56
ATP_OVERVIEW_PATTERN = re.compile(
    r"/en/tournaments/(?P<slug>[^/?#]+)/(?P<atp_id>\d+)/overview",
    re.I,
)
MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)
OFFICIAL_DATE_PATTERNS = (
    re.compile(
        rf"\b(?P<day>\d{{1,2}})\s+(?P<month>{MONTH_PATTERN})\s*-\s*"
        rf"\d{{1,2}}\s+(?:{MONTH_PATTERN})\s*,?\s*(?P<year>\d{{4}})\b"
    ),
    re.compile(
        rf"\b(?P<day>\d{{1,2}})\s*-\s*\d{{1,2}}\s+"
        rf"(?P<month>{MONTH_PATTERN})\s*,?\s*(?P<year>\d{{4}})\b"
    ),
)
MONTH_NUMBER = {
    month: number
    for number, month in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        1,
    )
}
DRAW_STATUS = {
    "Q": EntryStatus.Q,
    "WC": EntryStatus.WC,
    "LL": EntryStatus.LL,
    "PR": EntryStatus.PR,
    "SE": EntryStatus.SE,
    "ALT": EntryStatus.DA,
}


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"[^a-z0-9]+", " ", value.encode("ascii", "ignore").decode().lower()).strip()


def _official_start_date(text: str) -> date | None:
    for pattern in OFFICIAL_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return date(
                int(match.group("year")),
                MONTH_NUMBER[match.group("month")],
                int(match.group("day")),
            )
    return None


def parse_atp_tournament_links(page_html: str) -> list[dict]:
    """Extract official tournament IDs and dates from the ATP calendar page."""
    soup = BeautifulSoup(page_html, "html.parser")
    by_atp_id: dict[str, dict] = {}
    for link in soup.select('a[href*="/en/tournaments/"]'):
        href = link.get("href", "")
        match = ATP_OVERVIEW_PATTERN.search(href)
        if not match:
            continue
        text = " ".join(link.stripped_strings)
        start_date = _official_start_date(text)
        if not text or start_date is None:
            continue
        atp_id = match.group("atp_id")
        candidate = {
            "atp_id": atp_id,
            "slug": match.group("slug"),
            "text": text,
            "start_date": start_date,
        }
        if atp_id not in by_atp_id or len(text) > len(by_atp_id[atp_id]["text"]):
            by_atp_id[atp_id] = candidate
    return list(by_atp_id.values())


def _official_match_score(event, official: dict) -> int:
    tournament = event.tournament
    if abs((tournament.start_date - official["start_date"]).days) > 3:
        return 0
    text = _fold(official["text"])
    slug = _fold(official["slug"])
    name = _fold(tournament.name)
    city = _fold(tournament.location.city)
    aliases = {_fold(alias) for alias in event.schedule_aliases if _fold(alias)}
    score = 0
    if name and (name in text or name == slug):
        score = max(score, 100 + len(name))
    if city and (city in text or city == slug):
        score = max(score, 80 + len(city))
    for alias in aliases:
        if alias in text or alias == slug:
            score = max(score, 60 + len(alias))
    return score


def discover_atp_draw_sources(
    page_html: str,
    catalog: TournamentCatalog,
    today: date | None = None,
    lookahead_days: int = ATP_DRAW_LOOKAHEAD_DAYS,
) -> list[dict]:
    """Build ProTennisLive PDF sources for current and upcoming ATP events."""
    official_events = parse_atp_tournament_links(page_html)
    current_day = today or date.today()
    latest_start = current_day + timedelta(days=lookahead_days)
    used_atp_ids: set[str] = set()
    results: list[dict] = []
    for event in catalog.events:
        tournament = event.tournament
        if not (
            tournament.category == "Grand Slam"
            or re.fullmatch(r"ATP (?:250|500|1000)", tournament.category)
        ):
            continue
        if tournament.end_date and tournament.end_date < current_day:
            continue
        if tournament.start_date > latest_start:
            continue
        candidates = sorted(
            (
                (_official_match_score(event, official), official)
                for official in official_events
                if official["atp_id"] not in used_atp_ids
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if not candidates or candidates[0][0] == 0:
            continue
        official = candidates[0][1]
        used_atp_ids.add(official["atp_id"])
        base = {
            "year": tournament.year,
            "atp_id": official["atp_id"],
        }
        results.append(
            {
                "tournament_id": tournament.tournament_id,
                "format": "protennislive_pdf",
                "main_url": ATP_DRAW_URL.format(draw="mds", **base),
                "qualifying_url": ATP_DRAW_URL.format(draw="qs", **base),
                "minimum_main_players": max(16, tournament.main_draw_size - 16),
            }
        )
    return results


class PlayerResolver:
    def __init__(self, live_snapshot: dict) -> None:
        records = [*live_snapshot.get("rankings", []), *live_snapshot.get("schedules", [])]
        self.records = {stable_player_id(item["name"]): item for item in records}

    def resolve(self, name: str, nationality: str | None = None) -> tuple[str, str | None, int | None]:
        cleaned = re.sub(r"\s*\(tennis\)\s*$", "", name, flags=re.I).strip()
        identifier = stable_player_id(cleaned)
        exact = self.records.get(identifier)
        if exact:
            return exact["name"], exact.get("nation") or nationality, exact.get("rank")

        tokens = _fold(cleaned).split()
        candidates = []
        if len(tokens) >= 2:
            first, last = tokens[0], tokens[-1]
            for item in self.records.values():
                candidate_folded = _fold(item["name"])
                candidate_tokens = candidate_folded.split()
                if not candidate_tokens or candidate_tokens[-1] != last:
                    continue
                if (
                    candidate_tokens[0].startswith(first)
                    or first.startswith(candidate_tokens[0])
                    or candidate_folded.endswith(_fold(cleaned))
                ):
                    candidates.append(item)
        if len(candidates) == 1:
            item = candidates[0]
            return item["name"], item.get("nation") or nationality, item.get("rank")
        return cleaned, nationality, None


def _source(url: str, source_type: SourceType, retrieved_at: datetime, collector: str) -> Source:
    return Source(url=url, retrieved_at=retrieved_at, source_type=source_type, collector=collector)


def parse_official_main_draw_wildcards(page_html: str) -> list[str]:
    """Extract announced main-draw wild cards from an official news article."""
    soup = BeautifulSoup(page_html, "html.parser")
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"])
    for heading in headings:
        heading_text = heading.get_text(" ", strip=True)
        if not re.search(r"\bmain draw wild cards?\b", heading_text, re.I):
            continue
        names: list[str] = []
        for element in heading.find_all_next(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]
        ):
            if element.name != "li":
                if names and re.search(
                    r"\b(?:main draw|qualifying tournament)?\s*wild cards?\b",
                    element.get_text(" ", strip=True),
                    re.I,
                ):
                    break
                continue
            candidate = element.get_text(" ", strip=True).split(",", 1)[0].strip()
            if not candidate or re.search(r"\bto be announced\b", candidate, re.I):
                continue
            if candidate not in names:
                names.append(candidate)
        if names:
            return names
    return []


def _entry(
    resolver: PlayerResolver,
    name: str,
    status: EntryStatus,
    source: Source,
    nationality: str | None = None,
    seed: int | None = None,
) -> Entry:
    resolved_name, nation, rank = resolver.resolve(name, nationality)
    return Entry(
        player=Player(player_id=stable_player_id(resolved_name), name=resolved_name, nationality=nation),
        status=status,
        current_rank=rank,
        seed=seed,
        source=source,
    )


def apply_main_draw_wildcards(
    entry_list: EntryList,
    wildcards: list[Entry],
    snapshot_at: datetime,
) -> EntryList:
    """Overlay an official wild-card announcement on the latest entry snapshot."""
    entries = list(entry_list.entries)
    positions = {entry.player.player_id: index for index, entry in enumerate(entries)}
    for wildcard in wildcards:
        index = positions.get(wildcard.player.player_id)
        if index is None:
            positions[wildcard.player.player_id] = len(entries)
            entries.append(wildcard)
            continue
        existing = entries[index]
        if existing.status == EntryStatus.OUT:
            continue
        previous_status = (
            existing.status
            if existing.status == EntryStatus.ALT
            else existing.previous_status
        )
        entries[index] = existing.model_copy(
            update={
                "status": EntryStatus.WC,
                "alternate_position": None,
                "previous_status": previous_status,
                "source": wildcard.source,
            }
        )
    return entry_list.model_copy(
        update={"snapshot_at": snapshot_at, "entries": entries}
    )


def _pdf_names(pdf_bytes: bytes, section_label: str) -> list[tuple[str, EntryStatus, str | None, int | None]]:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages)
    results: list[tuple[str, EntryStatus, str | None, int | None]] = []
    in_draw = False
    for line in text.splitlines():
        if section_label in line:
            in_draw = True
            continue
        if in_draw and re.search(r"Round of \d+|Qualifying Round 1", line):
            if results:
                in_draw = False
                continue
        if not in_draw:
            continue
        match = re.match(r"^\s*(\d{1,3})\s*(.*?)([A-Z]{3})\s*$", line)
        nation = None
        if not match:
            match = re.match(r"^\s*(\d{1,3})\s+(.+?)\s*$", line)
        if not match:
            continue
        rest = match.group(2).strip()
        if match.lastindex == 3:
            nation = match.group(3)
        if rest.casefold() == "bye":
            continue
        seed = None
        seeded = re.match(r"^(\d+)(?:/([A-Za-z]+))?\s+(.+)$", rest)
        status_token = None
        if seeded:
            seed = int(seeded.group(1))
            status_token = seeded.group(2)
            rest = seeded.group(3)
        prefixed = re.match(r"^(WC|Q|LL|PR|SE|Alt)\s+(.+)$", rest, re.I)
        if prefixed:
            status_token = prefixed.group(1)
            rest = prefixed.group(2)
        if "," in rest:
            surname, given = (part.strip(" …") for part in rest.split(",", 1))
            name = f"{given} {surname}".strip()
        else:
            name = rest.strip(" …")
        status = DRAW_STATUS.get((status_token or "").upper(), EntryStatus.DA)
        results.append((name, status, nation, seed))
    return results


def collect_protennislive_draw(
    main_url: str,
    qualifying_url: str | None,
    resolver: PlayerResolver,
    retrieved_at: datetime,
    session: requests.Session,
) -> tuple[list[Entry], list[Entry]]:
    main_response = session.get(main_url, headers={"User-Agent": USER_AGENT}, timeout=45)
    main_response.raise_for_status()
    main_source = _source(main_url, SourceType.ATP_OFFICIAL, retrieved_at, "protennislive_pdf_draw")
    main = [
        _entry(resolver, name, status, main_source, nation, seed)
        for name, status, nation, seed in _pdf_names(main_response.content, "Main Draw Singles")
    ]
    qualifying: list[Entry] = []
    if qualifying_url:
        q_response = session.get(qualifying_url, headers={"User-Agent": USER_AGENT}, timeout=45)
        q_response.raise_for_status()
        q_source = _source(qualifying_url, SourceType.ATP_OFFICIAL, retrieved_at, "protennislive_pdf_draw")
        qualifying = [
            _entry(resolver, name, EntryStatus.QDA, q_source, nation, seed)
            for name, _, nation, seed in _pdf_names(q_response.content, "Qualifying Singles")
        ]
    return main, qualifying


def _wiki_player_cell(td) -> tuple[str, str | None] | None:
    if not td.select_one("span.flagicon"):
        return None
    country_link = td.select_one("span.flagicon a[title]")
    player_link = next(
        (link for link in td.select("a[title]") if link is not country_link and link.get_text(" ", strip=True)),
        None,
    )
    if player_link:
        name = player_link.get("title") or player_link.get_text(" ", strip=True)
    else:
        clone = BeautifulSoup(str(td), "html.parser")
        for flag in clone.select("span.flagicon"):
            flag.decompose()
        name = clone.get_text(" ", strip=True)
    name = re.sub(r"^\d+(?:/\w+)?\s+", "", name).strip()
    if not name or re.fullmatch(r"\d+", name):
        return None
    return name, country_link.get("title") if country_link else None


def collect_wikipedia_draw(
    url: str,
    resolver: PlayerResolver,
    retrieved_at: datetime,
    session: requests.Session,
) -> list[Entry]:
    response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    source = _source(url, SourceType.TRUSTED_SECONDARY, retrieved_at, "wikipedia_published_draw")
    by_player: dict[str, Entry] = {}
    draw_tables = [table for table in soup.select("table") if table.get_text(" ", strip=True).startswith("First round")]
    for table in draw_tables:
        for td in table.select("td"):
            parsed = _wiki_player_cell(td)
            if not parsed:
                continue
            raw_name, _country = parsed
            previous = td.find_previous_sibling("td")
            marker = previous.get_text(" ", strip=True).upper() if previous else ""
            marker = marker.split("/")[-1]
            status = DRAW_STATUS.get(marker, EntryStatus.DA)
            entry = _entry(resolver, raw_name, status, source)
            existing = by_player.get(entry.player.player_id)
            if existing is None or (existing.status == EntryStatus.DA and status != EntryStatus.DA):
                by_player[entry.player.player_id] = entry
    return list(by_player.values())


def collect_configured_draws(
    config_path: Path,
    catalog: TournamentCatalog,
    live_snapshot: dict,
    output_root: Path,
    session: requests.Session | None = None,
) -> tuple[int, list[str]]:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    events = {event.tournament.tournament_id: event.tournament for event in catalog.events}
    resolver = PlayerResolver(live_snapshot)
    retrieved_at = datetime.now(timezone.utc)
    client = session or requests.Session()
    updated = 0
    warnings: list[str] = []
    discovered: list[dict] = []
    try:
        calendar_response = client.get(
            ATP_TOUR_CALENDAR_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=45,
        )
        calendar_response.raise_for_status()
        discovered = discover_atp_draw_sources(calendar_response.text, catalog)
        if not discovered:
            raise ValueError("no current or upcoming tournament IDs found")
    except Exception as exc:
        warnings.append(f"ATP draw-source discovery: {exc}")

    items_by_tournament = {item["tournament_id"]: item for item in discovered}
    items_by_tournament.update(
        {item["tournament_id"]: item for item in config.get("events", [])}
    )
    for item in items_by_tournament.values():
        tournament_id = item["tournament_id"]
        tournament = events.get(tournament_id)
        if tournament is None:
            warnings.append(f"{tournament_id}: not found in catalog")
            continue
        if tournament.end_date and tournament.end_date < date.today():
            continue
        try:
            if item["format"] == "protennislive_pdf":
                main, qualifying = collect_protennislive_draw(
                    item["main_url"], item.get("qualifying_url"), resolver, retrieved_at, client
                )
            elif item["format"] == "wikipedia_draw":
                main = collect_wikipedia_draw(item["main_url"], resolver, retrieved_at, client)
                qualifying = []
            else:
                raise ValueError(f"unsupported draw format {item['format']!r}")
            if len(main) < item.get("minimum_main_players", 16):
                raise ValueError(f"only {len(main)} main-draw players parsed")
            existing_path = snapshot_path(output_root, tournament_id)
            if not qualifying and existing_path.exists():
                existing = EntryList.model_validate_json(existing_path.read_text(encoding="utf-8-sig"))
                qualifying = existing.qualifying_entries
            tournament = tournament.model_copy(
                update={
                    "draw_published": True,
                    "draw_url": item["main_url"],
                    "qualifying_list_published": bool(qualifying),
                }
            )
            if write_entry_snapshot(
                EntryList(
                    tournament=tournament,
                    snapshot_at=retrieved_at,
                    entries=main,
                    qualifying_entries=qualifying,
                ),
                output_root,
            ):
                updated += 1
        except Exception as exc:
            warnings.append(f"{tournament_id}: {exc}")

    for item in config.get("events", []):
        wildcard_url = item.get("wildcard_url")
        if not wildcard_url:
            continue
        tournament_id = item["tournament_id"]
        try:
            response = client.get(
                wildcard_url,
                headers={"User-Agent": USER_AGENT},
                timeout=45,
            )
            response.raise_for_status()
            names = parse_official_main_draw_wildcards(response.text)
            minimum = item.get("minimum_main_wildcards", 1)
            if len(names) < minimum:
                raise ValueError(
                    f"only {len(names)} announced main-draw wild cards parsed"
                )
            existing_path = snapshot_path(output_root, tournament_id)
            if not existing_path.exists():
                raise ValueError("no entry snapshot available for wild-card overlay")
            existing = EntryList.model_validate_json(
                existing_path.read_text(encoding="utf-8-sig")
            )
            source = _source(
                wildcard_url,
                SourceType.TOURNAMENT_OFFICIAL,
                retrieved_at,
                "official_wildcard_announcement",
            )
            wildcards = [
                _entry(resolver, name, EntryStatus.WC, source)
                for name in names
            ]
            overlaid = apply_main_draw_wildcards(existing, wildcards, retrieved_at)
            if write_entry_snapshot(overlaid, output_root):
                updated += 1
        except Exception as exc:
            warnings.append(f"{tournament_id} wild cards: {exc}")
    return updated, warnings
