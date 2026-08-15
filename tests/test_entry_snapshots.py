from copy import deepcopy
from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.entry_snapshots import (
    load_entry_snapshots,
    retain_live_entry_snapshots,
)
from tennis_entry_watch.collectors.live_tennis_snapshot import load_live_snapshot
from tennis_entry_watch.collectors.tournament_catalog import load_catalog


def test_empty_schedule_refresh_retains_last_non_empty_entry_list(tmp_path):
    live = load_live_snapshot(Path("data/rankings/atp-live-current.json"))
    catalog = load_catalog(Path("data/tournaments/catalog.json"))
    reference_date = date(2026, 8, 15)

    updated, _ = retain_live_entry_snapshots(live, catalog, tmp_path, reference_date)
    assert updated > 0
    before = {
        item.tournament.tournament_id: item for item in load_entry_snapshots(tmp_path)
    }["cancun-challenger-2026"]
    assert before.entries

    empty_refresh = deepcopy(live)
    empty_refresh["retrieved_at"] = "2026-08-18T12:00:00Z"
    empty_refresh["schedules"] = [
        item
        for item in empty_refresh["schedules"]
        if "Cancun" not in item.get("events", [])
        and "Qual. Cancun" not in item.get("events", [])
    ]
    _, retained = retain_live_entry_snapshots(
        empty_refresh, catalog, tmp_path, reference_date
    )
    after = {
        item.tournament.tournament_id: item for item in load_entry_snapshots(tmp_path)
    }["cancun-challenger-2026"]

    assert retained >= 1
    assert [entry.player.player_id for entry in after.entries] == [
        entry.player.player_id for entry in before.entries
    ]
    assert [entry.player.player_id for entry in after.qualifying_entries] == [
        entry.player.player_id for entry in before.qualifying_entries
    ]
    assert after.snapshot_at == before.snapshot_at
