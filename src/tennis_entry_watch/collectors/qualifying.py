from tennis_entry_watch.models import EntryList, EntryStatus


PROJECTED_QUALIFYING_COLLECTORS = {"live_tennis_schedule_snapshot", "main_alternate_qualifying_projection"}


def reproject_qualifying_queue(entry_list: EntryList) -> EntryList:
    """Rank tracked candidates into available direct places and a labelled queue."""
    capacity = entry_list.tournament.qualifying_direct_capacity
    if entry_list.tournament.draw_published or capacity is None:
        return entry_list
    main_wildcards = {entry.player.player_id for entry in entry_list.entries if entry.status == EntryStatus.WC}
    confirmed = []
    candidates = []
    for entry in entry_list.qualifying_entries:
        if entry.player.player_id in main_wildcards:
            continue
        if entry.status in {EntryStatus.QDA, EntryStatus.QALT} and entry.source.collector in PROJECTED_QUALIFYING_COLLECTORS:
            candidates.append(entry)
        else:
            confirmed.append(entry)
    # Published acceptances and announced wild cards are never demoted by a projection.
    known_wildcards = sum(entry.status == EntryStatus.WC for entry in confirmed)
    capacity = min(capacity, entry_list.tournament.qualifying_draw_size - known_wildcards)
    known_direct = sum(entry.status == EntryStatus.QDA for entry in confirmed)
    capacity = max(0, capacity - known_direct)
    candidates.sort(key=lambda entry: (entry.entry_rank or entry.current_rank or 99999, entry.player.name))
    positions = [entry.alternate_position for entry in confirmed if entry.status == EntryStatus.QALT]
    queue_start = max(positions, default=0)
    projected = []
    for index, entry in enumerate(candidates):
        is_alternate = index >= capacity
        projected.append(entry.model_copy(update={
            "status": EntryStatus.QALT if is_alternate else EntryStatus.QDA,
            "alternate_position": queue_start + index - capacity + 1 if is_alternate else None,
        }))
    return entry_list.model_copy(update={"qualifying_entries": [*confirmed, *projected]})


def preserve_entry_metadata(current: EntryList, previous: EntryList) -> EntryList:
    """Retain known entry methods while a lower-detail schedule changes."""
    def merge(pool, history):
        entries = list(pool)
        positions = {entry.player.player_id: i for i, entry in enumerate(entries)}
        for known in history:
            if known.status not in {EntryStatus.WC, EntryStatus.PR, EntryStatus.JR, EntryStatus.JE}:
                continue
            index = positions.get(known.player.player_id)
            if index is None:
                if known.status == EntryStatus.WC:
                    positions[known.player.player_id] = len(entries)
                    entries.append(known)
                continue
            candidate = entries[index]
            if candidate.status == EntryStatus.OUT:
                continue
            if candidate.source.collector != "live_tennis_schedule_snapshot":
                continue
            entries[index] = candidate.model_copy(update={
                "status": known.status,
                "alternate_position": None,
                "entry_rank": known.entry_rank or candidate.entry_rank,
                "source": known.source,
            })
        return entries

    return reproject_qualifying_queue(current.model_copy(update={
        "entries": merge(current.entries, previous.entries),
        "qualifying_entries": merge(current.qualifying_entries, previous.qualifying_entries),
    }))
