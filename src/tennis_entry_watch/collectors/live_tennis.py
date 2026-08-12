import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tennis_entry_watch.collectors.base import ParsingFailed, SourceUnavailable
from tennis_entry_watch.normalize.players import stable_player_id


RANKING_URL = "https://live-tennis.eu/en/atp-live-ranking"
SCHEDULE_URL = "https://live-tennis.eu/en/atp-schedule"
USER_AGENT = "TennisEntryWatch/0.1 (+https://github.com/rafaujo/tennis-entry-watch)"


class RankingRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2)
    nation: str = Field(pattern=r"^[A-Z]{3}$")
    points: int = Field(ge=0)
    rank: int = Field(gt=0)


class ScheduleRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2)
    nation: str = Field(pattern=r"^[A-Z]{3}$")
    rank: int = Field(gt=0)
    events: list[str]


class LiveTennisSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieved_at: datetime
    ranking_source: str
    schedule_source: str
    rankings: list[RankingRow] = Field(min_length=900, max_length=1200)
    schedules: list[ScheduleRow] = Field(min_length=900, max_length=1200)

    @model_validator(mode="after")
    def tables_are_consistent(self) -> "LiveTennisSnapshot":
        for label, rows in (("ranking", self.rankings), ("schedule", self.schedules)):
            ranks = [row.rank for row in rows]
            if ranks[0] != 1 or ranks != sorted(ranks):
                raise ValueError(f"{label} ranks must begin at 1 and be non-decreasing")
            player_ids = [stable_player_id(row.name) for row in rows]
            if len(player_ids) != len(set(player_ids)):
                raise ValueError(f"{label} player names must be unique after normalization")

        ranking_ids = {stable_player_id(row.name) for row in self.rankings}
        schedule_ids = {stable_player_id(row.name) for row in self.schedules}
        overlap = len(ranking_ids & schedule_ids) / max(len(ranking_ids), len(schedule_ids))
        if overlap < 0.95:
            raise ValueError(f"ranking/schedule player overlap is suspiciously low: {overlap:.1%}")
        return self


def _player_rows(page_html: str) -> list:
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.select_one("table#u868")
    body = table.find("tbody", recursive=False) if table else None
    if body is None:
        raise ParsingFailed("player table was not found")
    rows = [
        row
        for row in body.find_all("tr", recursive=False)
        if row.select_one("td.rk") and row.select_one("td.pn")
    ]
    if not rows:
        raise ParsingFailed("player table contains no ranking rows")
    return rows


def _identity_cells(row):
    name_cell = row.select_one("td.pn")
    age_cell = name_cell.find_next_sibling("td") if name_cell else None
    nation_cell = age_cell.find_next_sibling("td") if age_cell else None
    if name_cell is None or nation_cell is None:
        raise ParsingFailed("player identity cells are incomplete")
    return name_cell, nation_cell


def parse_rankings(page_html: str) -> list[RankingRow]:
    results = []
    for row in _player_rows(page_html):
        name_cell, nation_cell = _identity_cells(row)
        points_cell = nation_cell.find_next_sibling("td")
        if points_cell is None:
            raise ParsingFailed("ranking points cell is missing")
        points_text = re.sub(r"[^0-9]", "", points_cell.get_text(strip=True))
        if not points_text:
            raise ParsingFailed("ranking points are not numeric")
        results.append(
            RankingRow(
                name=name_cell.get_text(" ", strip=True),
                nation=nation_cell.get_text(strip=True),
                points=int(points_text),
                rank=int(row.select_one("td.rk").get_text(strip=True)),
            )
        )
    return results


def parse_schedules(page_html: str) -> list[ScheduleRow]:
    results = []
    for row in _player_rows(page_html):
        name_cell, nation_cell = _identity_cells(row)
        events = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all("td", recursive=False)
            if "ctr" in (cell.get("class") or []) and cell.get_text(" ", strip=True)
        ]
        results.append(
            ScheduleRow(
                name=name_cell.get_text(" ", strip=True),
                nation=nation_cell.get_text(strip=True),
                rank=int(row.select_one("td.rk").get_text(strip=True)),
                events=list(dict.fromkeys(events)),
            )
        )
    return results


class LiveTennisCollector:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def _get(self, url: str) -> str:
        try:
            response = self.session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceUnavailable(f"could not retrieve {url}: {exc}") from exc
        response.encoding = "utf-8"
        return response.text

    def collect(self, retrieved_at: datetime | None = None) -> LiveTennisSnapshot:
        return LiveTennisSnapshot(
            retrieved_at=retrieved_at or datetime.now(timezone.utc),
            ranking_source=RANKING_URL,
            schedule_source=SCHEDULE_URL,
            rankings=parse_rankings(self._get(RANKING_URL)),
            schedules=parse_schedules(self._get(SCHEDULE_URL)),
        )


def _semantic_payload(snapshot: LiveTennisSnapshot) -> dict:
    data = snapshot.model_dump(mode="json")
    data.pop("retrieved_at", None)
    return data


def write_snapshot_if_changed(snapshot: LiveTennisSnapshot, output: Path) -> bool:
    if output.exists():
        previous = LiveTennisSnapshot.model_validate_json(output.read_text(encoding="utf-8-sig"))
        if _semantic_payload(previous) == _semantic_payload(snapshot):
            return False

        previous_ids = {stable_player_id(row.name) for row in previous.rankings}
        current_ids = {stable_player_id(row.name) for row in snapshot.rankings}
        overlap = len(previous_ids & current_ids) / max(len(previous_ids), len(current_ids))
        if overlap < 0.85:
            raise ValueError(f"new ranking differs too much from previous valid snapshot: {overlap:.1%} overlap")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return True
