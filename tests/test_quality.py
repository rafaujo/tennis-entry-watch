from datetime import date

from tennis_entry_watch.collectors.live_tennis_snapshot import entry_lists_from_live_snapshot
from tennis_entry_watch.quality import validate_quality


def test_quality_report_accepts_plausible_current_data(
    synthetic_live_snapshot, synthetic_catalog
):
    entry_list = entry_lists_from_live_snapshot(
        synthetic_live_snapshot, synthetic_catalog, date(2026, 8, 18)
    )[0]
    result = validate_quality(
        synthetic_catalog,
        {entry_list.tournament.tournament_id: entry_list},
        date(2026, 8, 18),
    )

    assert result.errors == []
    assert "Fixture Open" in result.markdown
    assert "✅ No blocking data-quality errors." in result.markdown


def test_quality_report_blocks_an_empty_published_active_draw(synthetic_catalog):
    event = synthetic_catalog.events[0]
    event.tournament.draw_published = True
    result = validate_quality(synthetic_catalog, {}, date(2026, 8, 18))

    assert result.errors == ["Fixture Open: published active draw has no players"]
    assert "❌ Blocking errors" in result.markdown
