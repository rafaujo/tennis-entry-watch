from copy import deepcopy

import pytest

from tennis_entry_watch.changes import detect_changes
from tennis_entry_watch.models import ChangeType, EntryList, EntryStatus


def test_detects_sample_changes(previous, current):
    found = {(c.player_id, c.change_type, c.old_value, c.new_value) for c in detect_changes(previous, current)}
    assert ("alex-river", ChangeType.PLAYER_WITHDRAWN, "DA", "OUT") in found
    assert ("marco-silva", ChangeType.ALT_TO_MAIN_DRAW, "ALT", "DA") in found
    assert ("daniel-lee", ChangeType.ALT_POSITION_CHANGED, 2, 1) in found
    assert ("emil-novak", ChangeType.PLAYER_ADDED, None, "WC") in found


def test_detects_removed_player(previous, current):
    data = current.model_dump()
    data["entries"] = [e for e in data["entries"] if e["player"]["player_id"] != "daniel-lee"]
    changes = detect_changes(previous, EntryList.model_validate(data))
    assert any(c.player_id == "daniel-lee" and c.change_type == ChangeType.PLAYER_REMOVED for c in changes)


def test_detects_generic_status_change(previous):
    data = previous.model_dump()
    data["snapshot_at"] = previous.snapshot_at.replace(day=11)
    data["entries"][0]["status"] = EntryStatus.WC
    changes = detect_changes(previous, EntryList.model_validate(data))
    assert changes[0].change_type == ChangeType.STATUS_CHANGED


def test_rejects_different_tournaments(previous, current):
    data = current.model_dump()
    data["tournament"]["tournament_id"] = "other-2026"
    with pytest.raises(ValueError, match="same tournament"):
        detect_changes(previous, EntryList.model_validate(data))

