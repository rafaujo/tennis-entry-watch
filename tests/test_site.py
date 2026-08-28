from pathlib import Path

from datetime import date, datetime, timezone

from tennis_entry_watch.collectors.live_tennis_snapshot import (
    entry_lists_from_live_snapshot,
    load_live_snapshot,
)
from tennis_entry_watch.models import EntryList, EntryStatus, Source, SourceType
from tennis_entry_watch.site.build import (
    build_page,
    build_site,
    overlay_official_wildcards,
)


def test_page_contains_tournament_entries_and_disclaimer(current):
    page = build_page(current)
    assert "Sample Open" in page
    assert "Marco Silva" in page
    assert "fictional tournament" in page
    assert "Entry snapshot" in page


def test_real_pre_draw_page_shows_confirmed_and_pending_places():
    from tennis_entry_watch.models import EntryList

    source = Path("data/entries/winston-salem-open-2026/current.json")
    entry_list = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    page = build_page(entry_list)
    assert "PRE-DRAW · ENTRY WATCH" in page
    assert "37/48" in page
    assert page.count("determined in qualifying") == 4
    assert page.count("not announced") == 4
    assert page.count("special exempt / late entry / performance bye allocation pending") == 3
    assert "#80 · Lorenzo Sonego" in page
    assert "No verified alternate list is available" in page
    assert "The draw has not been published" in page
    assert "22 Aug–29 Aug 2026" in page


def test_official_wildcards_overlay_a_manually_verified_list():
    source = Path("data/entries/us-open-2026/current.json")
    verified = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    target = next(
        entry for entry in verified.entries if entry.player.name == "Michael Zheng"
    )
    official_source = Source(
        url="https://example.test/official-wildcards",
        retrieved_at=datetime(2026, 8, 20, 23, tzinfo=timezone.utc),
        source_type=SourceType.TOURNAMENT_OFFICIAL,
        collector="official_wildcard_announcement",
    )
    retained = verified.model_copy(
        update={
            "snapshot_at": official_source.retrieved_at,
            "entries": [
                entry.model_copy(
                    update={"status": EntryStatus.WC, "source": official_source}
                )
                if entry.player.player_id == target.player.player_id
                else entry
                for entry in verified.entries
            ],
        }
    )

    result = overlay_official_wildcards(verified, retained)
    overlaid = next(
        entry for entry in result.entries if entry.player.player_id == target.player.player_id
    )
    assert overlaid.status == EntryStatus.WC
    assert overlaid.previous_status == EntryStatus.ALT
    assert overlaid.alternate_position is None
    assert overlaid.source.source_type == SourceType.TOURNAMENT_OFFICIAL


def test_qualifying_wild_card_is_visible(
    synthetic_catalog, synthetic_live_snapshot
):
    entry_list = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        as_of=synthetic_catalog.tracking_started_at,
    )[0]
    wildcard = entry_list.qualifying_entries[0].model_copy(
        update={"status": EntryStatus.WC}
    )
    entry_list.qualifying_entries[0] = wildcard

    page = build_page(entry_list)

    assert wildcard.player.name in page
    assert 'status-wc" title="Wild card">WC' in page


def test_us_open_page_shows_alternate_queue_and_promotion():
    from tennis_entry_watch.models import EntryList

    source = Path("data/entries/us-open-2026/current.json")
    entry_list = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    page = build_page(entry_list)
    assert "104/128" in page
    assert "99" in page
    assert "Benjamin Bonzi" in page
    assert "NEXT IN · 1 opening" in page
    assert "Aleksandar Vukic" in page
    assert "promoted from alternate" in page
    assert "Sebastian Korda" in page
    assert "PROJ Q" in page
    assert "Likely qualifying · MD alternate #1" in page
    assert "Neither predicts qualification" in page
    assert "Qualifying alternates" in page
    assert "No verified or projected qualifying-alternate queue" in page


def test_full_site_builds_tournaments_and_player_schedules(tmp_path):
    written = build_site(Path("data/entries"), tmp_path, as_of=date(2026, 8, 15))
    assert tmp_path / "index.html" in written
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Grand Slams &amp; ATP Tour" in index
    assert "Challenger Tour" in index
    assert "Week of 17 Aug 2026" in index
    assert "Week of 24 Aug 2026" in index
    assert "Week of 31 Aug 2026" in index
    assert "Week of 07 Sep 2026" in index
    assert "MONITORING · LIST NOT FOUND" in index
    assert "Wild cards" in index
    assert "Week of 14 Sep 2026" in index
    assert "Week of 21 Sep 2026" not in index
    tour_start = index.index("Grand Slams &amp; ATP Tour")
    challenger_start = index.index("Challenger Tour", tour_start)
    assert tour_start < challenger_start
    tour_block = index[tour_start:challenger_start]
    challenger_block = index[challenger_start:]
    assert "Winston-Salem Open" in tour_block
    assert "US Open" in tour_block
    assert "Kingston 1" not in tour_block
    assert challenger_block.index("Week of 17 Aug 2026") < challenger_block.index("Week of 24 Aug 2026") < challenger_block.index("Week of 31 Aug 2026")
    assert "Kingston 1" in challenger_block
    assert "Como Lake Challenger" in challenger_block
    assert "Allershausen" not in index
    assert (tmp_path / "tournaments" / "us-open-2026.html").exists()
    assert (tmp_path / "tournaments" / "cancun-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "quebec-city-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "augsburg-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "manacor-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "aon-open-challenger-2026.html").exists()
    assert (tmp_path / "archive" / "index.html").exists()
    schedules = (tmp_path / "schedules" / "index.html").read_text(encoding="utf-8")
    assert "Player schedules" in schedules
    assert "Luciano Darderi" in schedules
    assert "Winston-Salem Open" in schedules
    assert "US Open" in schedules
    assert "Live rank" in schedules
    assert "Allershausen" not in schedules
    assert schedules.index("Jannik Sinner") < schedules.index("Carlos Alcaraz")
    us_open = (tmp_path / "tournaments" / "us-open-2026.html").read_text(encoding="utf-8")
    # The live schedule changes as tournament weeks pass, so both the label and
    # candidate count can change while the qualifying projection remains valid.
    assert 'status-qalt">' in us_open
    assert "Tracked secondary · live ranking" in us_open
    winston_salem = (tmp_path / "tournaments" / "winston-salem-open-2026.html").read_text(encoding="utf-8")
    snapshot = load_live_snapshot(Path("data/rankings/atp-live-current.json"))
    snapshot_time = snapshot["retrieved_at"].replace("T", " ")[:16]
    assert f"Live ranking<br><strong>{snapshot_time} UTC" in winston_salem
    assert "No qualifying players are currently listed in the tracked schedule" in winston_salem
    assert "ATP official · 2026 draw composition" in winston_salem
    cincinnati = (tmp_path / "tournaments" / "cincinnati-open-2026.html").read_text(encoding="utf-8")
    assert "The draw has been published" in cincinnati
    assert "Open the published draw" in cincinnati
    assert "Open place 1" not in cincinnati
    assert "The draw has not been published" not in cincinnati
    assert "Luca Van Assche" in cincinnati
    assert cincinnati.count('status-wc" title="Wild card">WC') == 5
    assert "pre-draw qualifying estimates are closed" not in cincinnati


def test_completed_event_leaves_homepage_and_enters_archive(tmp_path):
    build_site(Path("data/entries"), tmp_path, as_of=date(2026, 8, 24))
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    archive = (tmp_path / "archive" / "index.html").read_text(encoding="utf-8")
    assert "Europcar Cancun Country Club" not in index
    assert "Europcar Cancun Country Club" in archive
    assert "Cincinnati Open" in archive
    assert "Winston-Salem Open" in index


def test_published_snapshot_replaces_stale_winston_salem_entry_watch(tmp_path):
    build_site(Path("data/entries"), tmp_path, as_of=date(2026, 8, 27))
    page = (tmp_path / "tournaments" / "winston-salem-open-2026.html").read_text(
        encoding="utf-8"
    )

    assert "The draw has been published" in page
    assert "Open the published draw" in page
    assert 'status-qda"' in page
    assert "PROJ Q" not in page
