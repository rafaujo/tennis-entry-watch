from copy import deepcopy
from datetime import date

from tennis_entry_watch.collectors.entry_snapshots import (
    load_entry_snapshots,
    retain_live_entry_snapshots,
)


def test_empty_schedule_refresh_retains_last_non_empty_entry_list(
    tmp_path, synthetic_live_snapshot, synthetic_catalog
):
    reference_date = date(2026, 8, 15)
    updated, _ = retain_live_entry_snapshots(
        synthetic_live_snapshot, synthetic_catalog, tmp_path, reference_date
    )
    assert updated == 1
    before = load_entry_snapshots(tmp_path)[0]
    assert len(before.entries) == 2
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
