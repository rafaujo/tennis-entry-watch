from datetime import date, datetime, timezone
import re

from bs4 import BeautifulSoup
import requests

from tennis_entry_watch.collectors.base import (
    EntryListNotPublished,
    ParsingFailed,
    SourceUnavailable,
)
from tennis_entry_watch.models import (
    Entry,
    EntryList,
    EntryStatus,
    Location,
    Player,
    Source,
    SourceType,
    Surface,
    Tournament,
)
from tennis_entry_watch.normalize import stable_player_id


class WinstonSalem2026Collector:
    """Collector for one official, dated tournament entry-list announcement."""

    url = "https://www.winstonsalemopen.com/en/media/news/2026-player-announcement"
    collector_name = "winston_salem_2026_official_announcement"
    user_agent = "TennisEntryWatch/0.1 (public-data research; conservative polling)"

    _heading = "Winston-Salem, NC, U.S.A. – Main Draw Player List"
    _player_pattern = re.compile(
        r"^\s*\d+\.\s+(?P<name>.+?)\s+\((?P<nation>[A-Z]{3})\)\s*[–—-]\s*(?P<rank>\d+)\s*$",
        re.MULTILINE,
    )

    def collect(self, retrieved_at: datetime | None = None) -> EntryList:
        retrieved_at = retrieved_at or datetime.now(timezone.utc)
        try:
            response = requests.get(
                self.url,
                headers={"User-Agent": self.user_agent},
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceUnavailable(f"could not retrieve official announcement: {exc}") from exc
        return self.parse(response.text, retrieved_at=retrieved_at)

    def parse(self, page_html: str, retrieved_at: datetime) -> EntryList:
        text = BeautifulSoup(page_html, "html.parser").get_text("\n", strip=True)
        if self._heading not in text:
            raise EntryListNotPublished("main draw player-list heading was not found")

        ranking_match = re.search(
            r"Main Draw Player List \(Rankings as of (?P<date>\d{1,2}/\d{1,2}/\d{4})\)",
            text,
        )
        if not ranking_match:
            raise ParsingFailed("ranking date was not found")
        ranking_date = datetime.strptime(ranking_match.group("date"), "%m/%d/%Y").date()

        section = text[text.index(self._heading):]
        end_marker = "The initial list contains"
        if end_marker not in section:
            raise ParsingFailed("entry-list end marker was not found")
        section, summary = section.split(end_marker, 1)
        expected_match = re.match(r"\s*(\d+) direct entries", summary)
        if not expected_match:
            raise ParsingFailed("declared direct-entry count was not found")
        expected_count = int(expected_match.group(1))

        source = Source(
            url=self.url,
            retrieved_at=retrieved_at,
            source_type=SourceType.TOURNAMENT_OFFICIAL,
            collector=self.collector_name,
        )
        entries = [
            Entry(
                player=Player(
                    player_id=stable_player_id(match.group("name")),
                    name=match.group("name"),
                    nationality=match.group("nation"),
                ),
                status=EntryStatus.DA,
                entry_rank=int(match.group("rank")),
                source=source,
            )
            for match in self._player_pattern.finditer(section)
        ]
        if len(entries) != expected_count:
            raise ParsingFailed(
                f"parsed {len(entries)} direct entries; source declares {expected_count}"
            )

        tournament = Tournament(
            tournament_id="winston-salem-open-2026",
            name="Winston-Salem Open",
            year=2026,
            start_date=date(2026, 8, 23),
            end_date=date(2026, 8, 29),
            category="ATP 250",
            surface=Surface.HARD,
            location=Location(city="Winston-Salem", country="USA"),
            main_draw_size=48,
            qualifying_draw_size=16,
            entry_list_date=date(2026, 7, 28),
            entry_ranking_date=ranking_date,
        )
        return EntryList(
            tournament=tournament,
            snapshot_at=retrieved_at,
            entries=entries,
        )
