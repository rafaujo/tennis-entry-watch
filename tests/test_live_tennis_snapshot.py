from datetime import date

from tennis_entry_watch.collectors.live_tennis_snapshot import entry_lists_from_live_snapshot


REFERENCE_DATE = date(2026, 8, 15)


def test_snapshot_builds_entry_lists_from_a_fixed_schedule(
    synthetic_live_snapshot, synthetic_catalog
):
    entry_lists = entry_lists_from_live_snapshot(
        synthetic_live_snapshot, synthetic_catalog, REFERENCE_DATE
    )

    assert len(entry_lists) == 1
    fixture = entry_lists[0]
    assert fixture.tournament.tournament_id == "fixture-open-2026"
    assert len(fixture.entries) == 8
    assert len(fixture.qualifying_entries) == 6
    assert fixture.tournament.main_draw_size == 28
    assert fixture.tournament.qualifying_list_published is True


def test_generated_entries_keep_rank_and_secondary_provenance(
    synthetic_live_snapshot, synthetic_catalog
):
    fixture = entry_lists_from_live_snapshot(
        synthetic_live_snapshot, synthetic_catalog, REFERENCE_DATE
    )[0]
    player = fixture.entries[0]

    assert player.player.name == "Main Player One"
    assert player.current_rank == 101
    assert player.source.url == "https://example.test/schedules"
    assert player.source.source_type.value == "trusted_secondary"


def test_qualifying_overflow_becomes_ranked_projected_alternate_queue(
    synthetic_live_snapshot, synthetic_catalog
):
    fixture = entry_lists_from_live_snapshot(
        synthetic_live_snapshot, synthetic_catalog, REFERENCE_DATE
    )[0]
    acceptances = [entry for entry in fixture.qualifying_entries if entry.status.value == "QDA"]
    alternates = [entry for entry in fixture.qualifying_entries if entry.status.value == "QALT"]

    assert len(acceptances) == 4
    assert [entry.alternate_position for entry in alternates] == [1, 2]
    assert [entry.current_rank for entry in fixture.qualifying_entries] == [301, 302, 303, 304, 305, 306]


def test_qualifying_candidates_form_a_projected_main_alternate_queue(
    synthetic_live_snapshot, synthetic_catalog
):
    fixture = entry_lists_from_live_snapshot(
        synthetic_live_snapshot, synthetic_catalog, REFERENCE_DATE
    )[0]
    alternates = [entry for entry in fixture.entries if entry.status.value == "ALT"]

    assert [entry.alternate_position for entry in alternates] == [1, 2, 3, 4, 5, 6]
    assert [entry.current_rank for entry in alternates] == [301, 302, 303, 304, 305, 306]
    assert all(
        entry.source.collector == "live_tennis_schedule_snapshot"
        for entry in alternates
    )
