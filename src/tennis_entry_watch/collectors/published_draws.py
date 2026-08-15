import io
import json
import re
import unicodedata
from datetime import date, datetime, timezone
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
    for item in config.get("events", []):
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
    return updated, warnings
