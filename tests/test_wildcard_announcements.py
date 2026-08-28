from datetime import datetime, timezone
from pathlib import Path

import json
import requests

from tennis_entry_watch.collectors.entry_snapshots import (
    snapshot_path,
    write_entry_snapshot,
)
from tennis_entry_watch.collectors.live_tennis_snapshot import load_live_snapshot
from tennis_entry_watch.collectors.live_tennis_snapshot import entry_lists_from_live_snapshot
from tennis_entry_watch.collectors.published_draws import (
    PlayerResolver,
    _entry,
    _source,
    apply_main_draw_wildcards,
    collect_configured_draws,
    parse_official_main_draw_wildcards,
)
from tennis_entry_watch.models import EntryList, EntryStatus, SourceType


ROOT = Path(__file__).resolve().parents[1]
ANNOUNCEMENT_HTML = """
<article>
  <p><strong>Who received 2026 US Open Men's Singles Main Draw wild cards?</strong></p>
  <ul>
    <li><a>Martin Damm</a>, 22, current world No. 94</li>
    <li>Michael Zheng, 22, NCAA champion</li>
    <li>Gael Monfils, 39, FFT reciprocal agreement</li>
    <li>To Be Announced</li>
  </ul>
  <p><strong>Who received 2026 US Open Men's Singles Qualifying Tournament wild cards?</strong></p>
  <ul><li>Kei Nishikori, 36, former finalist</li></ul>
</article>
"""


def test_parses_only_announced_main_draw_wildcards():
    assert parse_official_main_draw_wildcards(ANNOUNCEMENT_HTML) == [
        "Martin Damm",
        "Michael Zheng",
        "Gael Monfils",
    ]


def test_official_wildcards_replace_alternate_or_direct_status():
    entry_list = EntryList.model_validate_json(
        (ROOT / "data/entries/us-open-2026/current.json").read_text(encoding="utf-8")
    )
    resolver = PlayerResolver(
        load_live_snapshot(ROOT / "data/rankings/atp-live-current.json")
    )
    retrieved_at = datetime(2026, 8, 20, 22, tzinfo=timezone.utc)
    source = _source(
        "https://example.test/official-wildcards",
        SourceType.TOURNAMENT_OFFICIAL,
        retrieved_at,
        "official_wildcard_announcement",
    )
    wildcards = [
        _entry(resolver, name, EntryStatus.WC, source)
        for name in parse_official_main_draw_wildcards(ANNOUNCEMENT_HTML)
    ]

    overlaid = apply_main_draw_wildcards(entry_list, wildcards, retrieved_at)
    by_name = {entry.player.name: entry for entry in overlaid.entries}

    assert by_name["Martin Damm"].status == EntryStatus.WC
    assert by_name["Martin Damm"].previous_status == EntryStatus.ALT
    assert by_name["Martin Damm"].alternate_position is None
    assert by_name["Michael Zheng"].status == EntryStatus.WC
    assert by_name["Gaël Monfils"].status == EntryStatus.WC
    assert by_name["Gaël Monfils"].source.source_type == SourceType.TOURNAMENT_OFFICIAL


def test_wildcard_overlay_runs_before_the_draw_is_published(
    tmp_path, synthetic_catalog, synthetic_live_snapshot
):
    wildcard_url = "https://example.test/wildcards"
    config_path = tmp_path / "draw-sources.json"
    config_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "tournament_id": "fixture-open-2026",
                        "format": "protennislive_pdf",
                        "main_url": "https://example.test/not-published.pdf",
                        "minimum_main_players": 16,
                        "wildcard_url": wildcard_url,
                        "minimum_main_wildcards": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    entry_list = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        as_of=synthetic_catalog.tracking_started_at,
    )[0]
    output_root = tmp_path / "snapshots"
    write_entry_snapshot(entry_list, output_root)

    class Response:
        def __init__(self, text="", status_code=200):
            self.text = text
            self.content = text.encode()
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

    class Session:
        def get(self, url, **_kwargs):
            if url == wildcard_url:
                return Response(
                    "<p><strong>Main Draw wild cards</strong></p>"
                    "<ul><li>Main Player One, officially announced</li></ul>"
                )
            if url.endswith("not-published.pdf"):
                return Response(status_code=404)
            return Response("<html></html>")

    updated, warnings = collect_configured_draws(
        config_path,
        synthetic_catalog,
        synthetic_live_snapshot,
        output_root,
        session=Session(),
        as_of=synthetic_catalog.tracking_started_at,
    )

    result = EntryList.model_validate_json(
        snapshot_path(output_root, "fixture-open-2026").read_text(encoding="utf-8")
    )
    assert updated == 1
    assert "fixture-open-2026: 404" in warnings
    assert not any("wild cards:" in warning for warning in warnings)
    assert result.entries[0].status == EntryStatus.WC


def test_published_challenger_draw_preserves_automatic_alternate_projection(
    tmp_path,
    monkeypatch,
    synthetic_catalog,
    synthetic_live_snapshot,
):
    config_path = tmp_path / "draw-sources.json"
    config_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "tournament_id": "fixture-open-2026",
                        "format": "protennislive_pdf",
                        "main_url": "https://example.test/main.pdf",
                        "minimum_main_players": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    history = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        as_of=synthetic_catalog.tracking_started_at,
    )[0]
    output_root = tmp_path / "snapshots"
    write_entry_snapshot(history, output_root)
    official_source = _source(
        "https://example.test/main.pdf",
        SourceType.ATP_OFFICIAL,
        datetime(2026, 8, 16, tzinfo=timezone.utc),
        "protennislive_pdf_draw",
    )
    official_main = [
        entry.model_copy(update={"source": official_source})
        for entry in history.entries
        if entry.status == EntryStatus.DA
    ]
    monkeypatch.setattr(
        "tennis_entry_watch.collectors.published_draws.collect_protennislive_draw",
        lambda *_args, **_kwargs: (official_main, []),
    )

    class Response:
        text = "<html></html>"
        content = b"<html></html>"

        def raise_for_status(self):
            return None

    class Session:
        def get(self, _url, **_kwargs):
            return Response()

    updated, _warnings = collect_configured_draws(
        config_path,
        synthetic_catalog,
        synthetic_live_snapshot,
        output_root,
        session=Session(),
        as_of=synthetic_catalog.tracking_started_at,
    )
    result = EntryList.model_validate_json(
        snapshot_path(output_root, "fixture-open-2026").read_text(encoding="utf-8")
    )
    alternates = [
        entry for entry in result.entries if entry.status == EntryStatus.ALT
    ]

    assert updated == 1
    assert result.tournament.draw_published is True
    assert len(alternates) == 6
    assert [entry.alternate_position for entry in alternates] == [
        1, 2, 3, 4, 5, 6
    ]
    assert all(
        entry.source.collector == "live_tennis_schedule_snapshot"
        for entry in alternates
    )


def test_configured_wildcards_are_used_when_official_page_is_unavailable(
    tmp_path, synthetic_catalog, synthetic_live_snapshot
):
    wildcard_url = "https://example.test/unavailable-wildcards"
    config_path = tmp_path / "draw-sources.json"
    config_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "tournament_id": "fixture-open-2026",
                        "format": "protennislive_pdf",
                        "main_url": "https://example.test/not-published.pdf",
                        "minimum_main_players": 16,
                        "wildcard_url": wildcard_url,
                        "minimum_main_wildcards": 1,
                        "main_wildcards": ["Main Player One"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    entry_list = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        as_of=synthetic_catalog.tracking_started_at,
    )[0]
    output_root = tmp_path / "snapshots"
    write_entry_snapshot(entry_list, output_root)

    class Response:
        def __init__(self, status_code=404):
            self.text = ""
            self.content = b""
            self.status_code = status_code

        def raise_for_status(self):
            raise requests.HTTPError(str(self.status_code))

    class Session:
        def get(self, _url, **_kwargs):
            return Response()

    updated, warnings = collect_configured_draws(
        config_path,
        synthetic_catalog,
        synthetic_live_snapshot,
        output_root,
        session=Session(),
        as_of=synthetic_catalog.tracking_started_at,
    )

    result = EntryList.model_validate_json(
        snapshot_path(output_root, "fixture-open-2026").read_text(encoding="utf-8")
    )
    assert updated == 1
    assert any("configured fallback used" in warning for warning in warnings)
    assert result.entries[0].status == EntryStatus.WC
