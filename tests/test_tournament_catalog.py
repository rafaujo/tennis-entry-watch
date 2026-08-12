from datetime import datetime, timezone
from pathlib import Path

from tennis_entry_watch.collectors.tournament_catalog import (
    TournamentCatalogCollector,
    parse_calendar_page,
    write_catalog_if_changed,
)


HTML = """
<table class="wikitable">
  <tr><th>Week</th><th>Tournament</th><th>Champions</th></tr>
  <tr><td>24 Aug</td><td><a>Winston-Salem Open</a><br><a>Winston-Salem</a>, United States<br>ATP 250<br>Hard – 48S/16Q/16D</td><td></td></tr>
</table>
<table class="wikitable">
  <tr><th>Unrelated</th><th>Table</th></tr>
  <tr><td>Grand Slam (128S)</td><td>not a calendar event</td></tr>
</table>
"""


def test_calendar_parser_extracts_tournament_metadata():
    events = parse_calendar_page(HTML, 2026, "https://example.test/calendar")
    assert len(events) == 1
    tournament = events[0].tournament
    assert tournament.tournament_id == "winston-salem-open-2026"
    assert tournament.start_date.isoformat() == "2026-08-24"
    assert tournament.end_date.isoformat() == "2026-08-30"
    assert tournament.category == "ATP 250"
    assert tournament.main_draw_size == 48
    assert tournament.qualifying_draw_size == 16
    assert events[0].schedule_aliases == ["Winston-Salem", "Winston-Salem Open"]


def test_catalog_timestamp_only_change_does_not_rewrite(tmp_path, monkeypatch):
    class Session:
        def get(self, url, headers, timeout):
            class Response:
                text = HTML
                encoding = "utf-8"

                def raise_for_status(self):
                    return None

            return Response()

    # Use enough repeated rows to exercise the write behavior without invoking
    # the collector's real-source minimum-count guard.
    events = parse_calendar_page(HTML, 2026, "https://example.test/calendar")
    from tennis_entry_watch.models import CatalogSource, SourceType, TournamentCatalog

    first = TournamentCatalog(
        year=2026,
        retrieved_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
        tracking_started_at="2026-08-12",
        sources=[CatalogSource(url="https://example.test", source_type=SourceType.TRUSTED_SECONDARY, label="test")],
        events=events,
    )
    output = tmp_path / "catalog.json"
    assert write_catalog_if_changed(first, output) is True
    before = output.read_bytes()
    second = first.model_copy(update={"retrieved_at": datetime(2026, 8, 13, tzinfo=timezone.utc)})
    assert write_catalog_if_changed(second, output) is False
    assert output.read_bytes() == before
