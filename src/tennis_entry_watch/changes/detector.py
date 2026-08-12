from tennis_entry_watch.models import ChangeType, EntryChange, EntryList, EntryStatus


MAIN_DRAW_STATUSES = {
    EntryStatus.DA, EntryStatus.PR, EntryStatus.WC, EntryStatus.Q,
    EntryStatus.LL, EntryStatus.SE,
}


def detect_changes(previous: EntryList, current: EntryList) -> list[EntryChange]:
    """Compare two snapshots without guessing causality or missing source facts."""
    if previous.tournament.tournament_id != current.tournament.tournament_id:
        raise ValueError("snapshots must belong to the same tournament")
    if current.snapshot_at < previous.snapshot_at:
        raise ValueError("current snapshot cannot predate previous snapshot")

    old = {entry.player.player_id: entry for entry in previous.entries}
    new = {entry.player.player_id: entry for entry in current.entries}
    changes: list[EntryChange] = []

    def add(player_id, change_type, old_value, new_value):
        entry = new.get(player_id) or old[player_id]
        changes.append(EntryChange(
            tournament_id=current.tournament.tournament_id,
            player_id=player_id,
            player_name=entry.player.name,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            detected_at=current.snapshot_at,
            source=entry.source,
        ))

    for player_id in sorted(new.keys() - old.keys()):
        add(player_id, ChangeType.PLAYER_ADDED, None, new[player_id].status.value)
    for player_id in sorted(old.keys() - new.keys()):
        add(player_id, ChangeType.PLAYER_REMOVED, old[player_id].status.value, None)

    for player_id in sorted(old.keys() & new.keys()):
        before, after = old[player_id], new[player_id]
        if before.status != after.status:
            if after.status == EntryStatus.OUT:
                kind = ChangeType.PLAYER_WITHDRAWN
            elif before.status == EntryStatus.ALT and after.status in MAIN_DRAW_STATUSES:
                kind = ChangeType.ALT_TO_MAIN_DRAW
            else:
                kind = ChangeType.STATUS_CHANGED
            add(player_id, kind, before.status.value, after.status.value)
        elif before.status == EntryStatus.ALT and before.alternate_position != after.alternate_position:
            add(player_id, ChangeType.ALT_POSITION_CHANGED,
                before.alternate_position, after.alternate_position)
        if before.entry_rank != after.entry_rank:
            add(player_id, ChangeType.ENTRY_RANK_CHANGED,
                before.entry_rank, after.entry_rank)

    return changes

