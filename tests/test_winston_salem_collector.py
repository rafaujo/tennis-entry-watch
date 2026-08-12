from datetime import datetime, timezone
from pathlib import Path

import pytest

from tennis_entry_watch.collectors import (
    EntryListNotPublished,
    ParsingFailed,
    WinstonSalem2026Collector,
)
from tennis_entry_watch.models import EntryStatus, SourceType


FIXTURE = Path(__file__).parent / "fixtures/winston_salem_2026_entry_list.html"
RETRIEVED_AT = datetime(2026, 8, 12, 14, 17, 25, tzinfo=timezone.utc)


def test_parses_official_entry_list_fixture():
    result = WinstonSalem2026Collector().parse(
        FIXTURE.read_text(encoding="utf-8"), retrieved_at=RETRIEVED_AT
    )
    assert len(result.entries) == 37
    assert result.entries[0].player.name == "Luciano Darderi"
    assert result.entries[0].entry_rank == 23
    assert all(entry.status == EntryStatus.DA for entry in result.entries)
    assert result.tournament.entry_ranking_date.isoformat() == "2026-07-27"
    assert result.entries[0].source.source_type == SourceType.TOURNAMENT_OFFICIAL


def test_rejects_silent_partial_parse():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        "37. Lorenzo Sonego (ITA) – 80", "unparseable player row"
    )
    with pytest.raises(ParsingFailed, match="parsed 36.*declares 37"):
        WinstonSalem2026Collector().parse(html, retrieved_at=RETRIEVED_AT)


def test_distinguishes_unpublished_list():
    with pytest.raises(EntryListNotPublished):
        WinstonSalem2026Collector().parse("<html><body>Coming soon</body></html>", RETRIEVED_AT)

