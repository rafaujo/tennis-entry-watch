from copy import deepcopy
from datetime import date

from tennis_entry_watch.collectors.entry_snapshots import (
    load_entry_snapshots,
    merge_missing_alternate_history,
    merge_published_draw_history,
    predraw_snapshot_path,
    project_main_alternates_from_qualifying,
    retain_live_entry_snapshots,
    write_entry_snapshot,
)
from tennis_entry_watch.collectors.live_tennis_snapshot import (
    entry_lists_from_live_snapshot,
)
from tennis_entry_watch.models import EntryStatus


def test_empty_schedule_refresh_retains_last_non_empty_entry_list(
    tmp_path, synthetic_live_snapshot, synthetic_catalog
):
    reference_date = date(2026, 8, 15)
    updated, _ = retain_live_entry_snapshots(
        synthetic_live_snapshot, synthetic_catalog, tmp_path, reference_date
    )
    assert updated == 1
    before = load_entry_snapshots(tmp_path)[0]
    assert len(before.entries) == 8
    assert len(before.qualifying_entries) == 6

    empty_refresh = deepcopy(synthetic_live_snapshot)
    empty_refresh["retrieved_at"] = "2026-08-18T12:00:00Z"
    empty_refresh["schedules"] = []
    updated, retained = retain_live_entry_snapshots(
        empty_refresh, synthetic_catalog, tmp_path, reference_date
    )
    after = load_entry_snapshots(tmp_path)[0]

    assert updated == 0
    assert retained == 1
    assert [entry.player.player_id for entry in after.entries] == [
        entry.player.player_id for entry in before.entries
    ]
    assert [entry.player.player_id for entry in after.qualifying_entries] == [
        entry.player.player_id for entry in before.qualifying_entries
    ]
    assert after.snapshot_at == before.snapshot_at


def test_published_challenger_draw_keeps_known_er_and_pr(
    synthetic_live_snapshot, synthetic_catalog
):
    history = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        synthetic_catalog.tracking_started_at,
    )[0]
    protected = history.entries[0].model_copy(
        update={"status": EntryStatus.PR, "entry_rank": 201}
    )
    protected_alternate = history.entries[1].model_copy(
        update={
            "status": EntryStatus.ALT,
            "entry_rank": 202,
            "alternate_position": 1,
            "previous_status": EntryStatus.PR,
        }
    )
    history = history.model_copy(
        update={"entries": [protected, protected_alternate]}
    )
    published = history.model_copy(
        update={
            "tournament": history.tournament.model_copy(
                update={"draw_published": True}
            ),
            "entries": [
                entry.model_copy(
                    update={
                        "status": EntryStatus.DA,
                        "entry_rank": None,
                        "alternate_position": None,
                        "previous_status": None,
                    }
                )
                for entry in history.entries
            ],
        }
    )

    merged = merge_published_draw_history(published, history)
    by_name = {entry.player.name: entry for entry in merged.entries}

    assert by_name["Main Player One"].status == EntryStatus.PR
    assert by_name["Main Player One"].entry_rank == 201
    assert by_name["Main Player Two"].status == EntryStatus.PR
    assert by_name["Main Player Two"].entry_rank == 202
    assert by_name["Main Player Two"].previous_status == EntryStatus.ALT

    repeated = merge_published_draw_history(published, merged)
    assert len(repeated.entries) == len(merged.entries)
    assert repeated.entries == merged.entries


def test_schedule_refresh_does_not_replace_a_published_draw(
    tmp_path, synthetic_live_snapshot, synthetic_catalog
):
    tracked = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        synthetic_catalog.tracking_started_at,
    )[0]
    write_entry_snapshot(tracked, tmp_path)
    published = tracked.model_copy(
        update={
            "tournament": tracked.tournament.model_copy(
                update={"draw_published": True}
            )
        }
    )
    write_entry_snapshot(published, tmp_path)

    changed_schedule = deepcopy(synthetic_live_snapshot)
    changed_schedule["retrieved_at"] = "2026-08-19T12:00:00Z"
    changed_schedule["schedules"] = changed_schedule["schedules"][1:]
    updated, retained = retain_live_entry_snapshots(
        changed_schedule,
        synthetic_catalog,
        tmp_path,
        synthetic_catalog.tracking_started_at,
    )
    after = load_entry_snapshots(tmp_path)[0]

    assert updated == 0
    assert retained == 1
    assert after == published
    assert predraw_snapshot_path(
        tmp_path, "fixture-open-2026"
    ).exists()


def test_published_draw_projects_alternates_from_qualifying_as_fallback(
    synthetic_live_snapshot, synthetic_catalog
):
    tracked = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        synthetic_catalog.tracking_started_at,
    )[0]
    published = tracked.model_copy(
        update={
            "tournament": tracked.tournament.model_copy(
                update={"draw_published": True}
            ),
            "entries": [
                entry for entry in tracked.entries if entry.status == EntryStatus.DA
            ],
        }
    )

    projected = project_main_alternates_from_qualifying(published)
    alternates = [
        entry for entry in projected.entries if entry.status == EntryStatus.ALT
    ]

    assert len(alternates) == 6
    assert [entry.alternate_position for entry in alternates] == [1, 2, 3, 4, 5, 6]
    assert all(
        entry.source.collector == "qualifying_draw_main_alternate_projection"
        for entry in alternates
    )
    assert all(
        entry.source.source_type.value == "trusted_secondary"
        for entry in alternates
    )


def test_live_history_restores_qualifying_alternates_when_main_queue_exists(
    synthetic_live_snapshot, synthetic_catalog
):
    history = entry_lists_from_live_snapshot(
        synthetic_live_snapshot,
        synthetic_catalog,
        synthetic_catalog.tracking_started_at,
    )[0]
    published = history.model_copy(
        update={
            "tournament": history.tournament.model_copy(
                update={"draw_published": True}
            ),
            "qualifying_entries": [
                entry
                for entry in history.qualifying_entries
                if entry.status == EntryStatus.QDA
            ],
        }
    )
    assert any(entry.status == EntryStatus.ALT for entry in published.entries)
    assert not any(
        entry.status == EntryStatus.QALT
        for entry in published.qualifying_entries
    )

    merged = merge_missing_alternate_history(published, history)
    qualifying_alternates = [
        entry
        for entry in merged.qualifying_entries
        if entry.status == EntryStatus.QALT
    ]

    assert [entry.alternate_position for entry in qualifying_alternates] == [1, 2]
