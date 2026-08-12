from pathlib import Path
from copy import deepcopy

from tennis_entry_watch.collectors.live_tennis_snapshot import (
    entry_lists_from_live_snapshot,
    load_live_snapshot,
)


def test_snapshot_builds_current_and_upcoming_challenger_entry_lists():
    snapshot = load_live_snapshot(Path("data/rankings/atp-live-current.json"))
    entry_lists = entry_lists_from_live_snapshot(snapshot)
    assert len(entry_lists) == 34
    by_id = {item.tournament.tournament_id: item for item in entry_lists}

    cancun = by_id["cancun-challenger-2026"]
    assert len(cancun.entries) == 21
    assert len(cancun.qualifying_entries) == 12
    assert cancun.tournament.main_draw_size == 28

    kingston = by_id["kingston-1-challenger-2026"]
    assert len(kingston.entries) == 20
    assert len(kingston.qualifying_entries) == 20
    assert kingston.tournament.main_draw_size == 32

    augsburg = by_id["augsburg-challenger-2026"]
    assert len(augsburg.entries) == 23
    assert len(augsburg.qualifying_entries) == 20

    como = by_id["como-challenger-2026"]
    assert len(como.entries) == 23
    assert len(como.qualifying_entries) == 0
    assert como.tournament.qualifying_list_published is False

    september = by_id["aon-open-challenger-2026"]
    assert september.entries == []
    assert september.tournament.start_date.isoformat() == "2026-09-07"


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


def test_qualifying_overflow_becomes_ranked_projected_alternate_queue():
    snapshot = deepcopy(load_live_snapshot(Path("data/rankings/atp-live-current.json")))
    snapshot["schedules"].extend(
        {
            "name": f"Projected Player {index}",
            "nation": "USA",
            "rank": 900 + index,
            "events": ["Qual. Cancun"],
        }
        for index in range(1, 7)
    )
    cancun = next(
        item
        for item in entry_lists_from_live_snapshot(snapshot)
        if item.tournament.tournament_id == "cancun-challenger-2026"
    )
    acceptances = [entry for entry in cancun.qualifying_entries if entry.status.value == "QDA"]
    alternates = [entry for entry in cancun.qualifying_entries if entry.status.value == "QALT"]
    assert len(acceptances) == 16
    assert [entry.alternate_position for entry in alternates] == [1, 2]
