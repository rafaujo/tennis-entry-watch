from pathlib import Path

from tennis_entry_watch.collectors.live_tennis_snapshot import (
    entry_lists_from_live_snapshot,
    load_live_snapshot,
)


def test_snapshot_builds_six_challenger_entry_lists():
    snapshot = load_live_snapshot(Path("data/rankings/atp-live-current.json"))
    entry_lists = entry_lists_from_live_snapshot(snapshot)
    assert len(entry_lists) == 6
    by_id = {item.tournament.tournament_id: item for item in entry_lists}

    cancun = by_id["cancun-challenger-2026"]
    assert len(cancun.entries) == 21
    assert len(cancun.qualifying_entries) == 12
    assert cancun.tournament.main_draw_size == 28

    kingston = by_id["kingston-1-challenger-2026"]
    assert len(kingston.entries) == 20
    assert len(kingston.qualifying_entries) == 20
    assert kingston.tournament.main_draw_size == 32


def test_generated_entries_keep_live_rank_and_secondary_provenance():
    snapshot = load_live_snapshot(Path("data/rankings/atp-live-current.json"))
    entry_lists = entry_lists_from_live_snapshot(snapshot)
    darderi = next(
        entry
        for item in entry_lists
        if item.tournament.tournament_id == "cancun-challenger-2026"
        for entry in item.entries
        if entry.player.player_id == "luciano-darderi"
    )
    assert darderi.current_rank == 20
    assert darderi.source.source_type.value == "trusted_secondary"
