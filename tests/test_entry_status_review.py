from datetime import date, datetime, timezone

import pytest

from tennis_entry_watch.collectors.live_tennis_snapshot import entry_lists_from_live_snapshot
from tennis_entry_watch.collectors.entry_snapshots import merge_published_draw_history
from tennis_entry_watch.collectors.published_draws import (
    PlayerResolver, _atp_text_names, _entry, _source,
    apply_main_draw_wildcards, apply_qualifying_wildcards,
)
from tennis_entry_watch.collectors.qualifying import preserve_entry_metadata, reproject_qualifying_queue
from tennis_entry_watch.collectors.tournament_catalog import _qualifying_wildcard_slots, parse_calendar_page
from tennis_entry_watch.collectors.wildcards import event_page_from_draw_url, parse_wikipedia_wildcards
from tennis_entry_watch.models import EntryStatus, SourceType
from tennis_entry_watch.quality import validate_quality
from tennis_entry_watch.site.build import _status, overlay_official_wildcards


@pytest.mark.parametrize("row,name,status,seed,previous", [
    ("1 WC1 GIRON, Marcos USA", "Marcos GIRON", EntryStatus.WC, 1, None),
    ("5 WC2 GIUNTA, Massimo ITA", "Massimo GIUNTA", EntryStatus.WC, 2, None),
    ("9 WC 3 VASAMI, Jacopo ITA", "Jacopo VASAMI", EntryStatus.WC, 3, None),
    ("1 1/WC GIRON, Marcos USA", "Marcos GIRON", EntryStatus.WC, 1, None),
    ("5 JR KENNEDY, Jack USA", "Jack KENNEDY", EntryStatus.JR, None, None),
    ("1 Alt 1 PEREIRA, Tiago POR", "Tiago PEREIRA", EntryStatus.DA, 1, EntryStatus.ALT),
    ("2 PR TABERNER, Carlos ESP", "Carlos TABERNER", EntryStatus.PR, None, None),
    ("3 JE SAMPLE, Junior USA", "Junior SAMPLE", EntryStatus.JE, None, None),
])
def test_pdf_markers_are_not_mistaken_for_names_or_direct_acceptances(row, name, status, seed, previous):
    text = f"Main Draw Singles\n{row}\nRound of 32\n1 Another Player USA"
    assert _atp_text_names(text, "Main Draw Singles") == [(name, status, row[-3:], seed, previous)]


@pytest.mark.parametrize("category,size,wildcards", [
    ("Challenger 75", 24, 4), ("Challenger 125", 24, 4),
    ("ATP 250", 16, 2), ("ATP 500", 16, 3),
    ("ATP 1000", 28, 4), ("ATP 1000", 48, 5),
    ("Grand Slam", 128, None),
])
def test_qualifying_wc_reservations_follow_draw_composition(category, size, wildcards):
    assert _qualifying_wildcard_slots(category, size) == wildcards


def test_calendar_country_does_not_include_surface():
    html = '<table class="wikitable"><tr><th>Week</th><th>Tournament</th></tr><tr><td>2 Nov</td><td><a>Fixture Cup</a><br>Testville, Brazil Clay – Challenger 75 – 32S/24Q/16D</td></tr></table>'
    event = parse_calendar_page(html, 2026, "https://example.test/calendar")[0]
    assert event.tournament.location.country == "Brazil"
    assert event.tournament.qualifying_direct_capacity == 20


def _fixture(synthetic_catalog, synthetic_live_snapshot):
    synthetic_catalog.events[0].tournament.qualifying_wildcard_slots = 1
    return entry_lists_from_live_snapshot(synthetic_live_snapshot, synthetic_catalog, date(2026, 8, 15))[0]


def test_qualifying_reserves_wcs_before_building_the_projected_queue(synthetic_catalog, synthetic_live_snapshot):
    entries = _fixture(synthetic_catalog, synthetic_live_snapshot).qualifying_entries
    assert [item.current_rank for item in entries if item.status == EntryStatus.QDA] == [301, 302, 303]
    queue = [item for item in entries if item.status == EntryStatus.QALT]
    assert [item.current_rank for item in queue] == [304, 305, 306]
    assert [item.alternate_position for item in queue] == [1, 2, 3]


def test_confirmed_main_and_qualifying_wcs_survive_schedule_refresh(synthetic_catalog, synthetic_live_snapshot):
    current = _fixture(synthetic_catalog, synthetic_live_snapshot)
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    source = _source("https://example.test/wildcards", SourceType.TOURNAMENT_OFFICIAL, now, "official_wildcard_announcement")
    resolver = PlayerResolver({})
    previous = apply_main_draw_wildcards(current, [_entry(resolver, "New Wildcard", EntryStatus.WC, source)], now)
    q_name = current.qualifying_entries[-1].player.name
    previous = apply_qualifying_wildcards(previous, [_entry(resolver, q_name, EntryStatus.WC, source)], now)
    refreshed = preserve_entry_metadata(current, previous)
    assert next(item for item in refreshed.entries if item.player.name == "New Wildcard").status == EntryStatus.WC
    q_wc = next(item for item in refreshed.qualifying_entries if item.player.name == q_name)
    assert q_wc.status == EntryStatus.WC
    assert q_wc.alternate_position is None
    assert q_wc.source == source
    assert sum(item.status == EntryStatus.QDA for item in refreshed.qualifying_entries) == 3
    assert [item.alternate_position for item in refreshed.qualifying_entries if item.status == EntryStatus.QALT] == [1, 2]


def test_announced_main_wc_is_not_also_projected_into_qualifying(synthetic_catalog, synthetic_live_snapshot):
    current = _fixture(synthetic_catalog, synthetic_live_snapshot)
    wc = current.qualifying_entries[0].model_copy(update={"status": EntryStatus.WC})
    result = reproject_qualifying_queue(apply_main_draw_wildcards(current, [wc], current.snapshot_at))
    assert wc.player.player_id not in {item.player.player_id for item in result.qualifying_entries}


def test_published_qualifying_field_is_not_reprojected(synthetic_catalog, synthetic_live_snapshot):
    current = _fixture(synthetic_catalog, synthetic_live_snapshot)
    current.tournament.draw_published = True
    assert reproject_qualifying_queue(current) is current


def test_published_draw_keeps_waiting_q_alternates_and_marks_entered_ones(synthetic_catalog, synthetic_live_snapshot):
    history = _fixture(synthetic_catalog, synthetic_live_snapshot)
    entrants = [item.model_copy(update={"status": EntryStatus.QDA, "alternate_position": None, "previous_status": None}) for item in history.qualifying_entries[:4]]
    published = history.model_copy(update={"qualifying_entries": entrants})
    result = merge_published_draw_history(published, history)
    assert result.qualifying_entries[3].previous_status == EntryStatus.QALT
    assert result.qualifying_entries[3].status == EntryStatus.QDA
    assert len([item for item in result.qualifying_entries if item.status == EntryStatus.QALT]) == 2


def test_entered_alternate_is_not_still_waiting_or_a_promoted_wc(synthetic_catalog, synthetic_live_snapshot):
    current = _fixture(synthetic_catalog, synthetic_live_snapshot)
    entered = current.qualifying_entries[0].model_copy(update={"previous_status": EntryStatus.QALT})
    assert "entered from qualifying alternates" in _status(entered)
    assert "entered from" not in _status(entered.model_copy(update={"status": EntryStatus.WC}))
    assert "entered from" not in _status(entered.model_copy(update={"status": EntryStatus.OUT}))


def test_wc_page_association_uses_exact_year_and_singles_event():
    assert event_page_from_draw_url("https://en.wikipedia.org/wiki/2026_Fixture_Cup_%E2%80%93_Men%27s_singles", 2026) == "https://en.wikipedia.org/wiki/2026_Fixture_Cup"
    assert event_page_from_draw_url("https://en.wikipedia.org/wiki/2025_Fixture_Cup_%E2%80%93_Singles", 2026) is None
    assert event_page_from_draw_url("https://example.test/wiki/2026_Fixture_Cup_%E2%80%93_Singles", 2026) is None
    assert event_page_from_draw_url("https://en.wikipedia.org/wiki/2026_Fixture_Cup_%E2%80%93_Doubles", 2026) is None


def test_wc_parser_separates_main_qualifying_and_doubles():
    html = '''<p>The following players received wildcards into the singles main draw:</p>
    <ul><li><a><img alt="Flag"></a><a>Elias Ymer</a><sup>[1]</sup></li><li>TBA</li></ul>
    <p>The following players received wildcards into the singles qualifying draw:</p>
    <ul><li><a>Leo Borg</a></li></ul>
    <p>The following pairs received wildcards into the doubles main draw:</p>
    <ul><li><a>Wrong Player</a></li></ul>
    <p>Withdrawals</p><ul><li><a>Another Player</a></li></ul>'''
    assert parse_wikipedia_wildcards(html) == (["Elias Ymer"], ["Leo Borg"])


def test_calendar_retains_the_exact_event_page_before_a_singles_page_exists():
    html = '<table class="wikitable"><tr><th>Week</th><th>Tournament</th></tr><tr><td>2 Nov</td><td><a href="/wiki/2026_Fixture_Cup">Fixture Cup</a><br>Testville, Brazil<br>Challenger 75<br>Clay – 32S/24Q/16D</td></tr></table>'
    event = parse_calendar_page(html, 2026, "https://en.wikipedia.org/wiki/2026_ATP_Challenger_Tour")[0]
    assert event.event_page_url == "https://en.wikipedia.org/wiki/2026_Fixture_Cup"
    assert event.draw_page_url is None


def test_secondary_wc_announcement_does_not_overwrite_an_official_entry_method(synthetic_catalog, synthetic_live_snapshot):
    current = _fixture(synthetic_catalog, synthetic_live_snapshot)
    now = current.snapshot_at
    entry = current.entries[0].model_copy(update={
        "status": EntryStatus.PR,
        "source": _source("https://example.test/official", SourceType.ATP_OFFICIAL, now, "fixture"),
    })
    current.entries = [entry]
    candidate = entry.model_copy(update={
        "status": EntryStatus.WC,
        "source": _source("https://example.test/wiki", SourceType.TRUSTED_SECONDARY, now, "fixture"),
    })
    result = apply_main_draw_wildcards(current, [candidate], now)
    assert result.entries[0].status == EntryStatus.PR


def test_site_overlays_official_qualifying_wcs_on_a_manually_verified_list(synthetic_catalog, synthetic_live_snapshot):
    base = _fixture(synthetic_catalog, synthetic_live_snapshot)
    target = base.qualifying_entries[-1]
    official_wc = target.model_copy(update={
        "status": EntryStatus.WC, "alternate_position": None,
        "source": _source("https://example.test/official", SourceType.TOURNAMENT_OFFICIAL, base.snapshot_at, "fixture"),
    })
    retained = base.model_copy(update={"qualifying_entries": [official_wc]})
    result = overlay_official_wildcards(base, retained)
    entry = next(item for item in result.qualifying_entries if item.player.player_id == target.player.player_id)
    assert entry.status == EntryStatus.WC
    assert entry.alternate_position is None
    assert "entered from" not in _status(entry)


def test_quality_uses_the_retained_draw_phase_not_just_calendar(synthetic_catalog, synthetic_live_snapshot):
    current = _fixture(synthetic_catalog, synthetic_live_snapshot)
    current.tournament = current.tournament.model_copy(update={"draw_published": True})
    current.entries = []
    result = validate_quality(synthetic_catalog, {current.tournament.tournament_id: current}, date(2026, 8, 19))
    assert any("published active draw has no players" in error for error in result.errors)
