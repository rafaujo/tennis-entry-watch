from tennis_entry_watch.site.build import build_page


def test_page_contains_tournament_entries_and_disclaimer(current):
    page = build_page(current)
    assert "Sample Open" in page
    assert "Marco Silva" in page
    assert "fictional tournament" in page
    assert "Entry-list snapshot" in page


def test_real_pre_draw_page_shows_confirmed_and_pending_places():
    from pathlib import Path

    from tennis_entry_watch.models import EntryList

    source = Path("data/entries/winston-salem-open-2026/current.json")
    entry_list = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    page = build_page(entry_list)
    assert "PRE-DRAW · ENTRY LIST" in page
    assert "37/48" in page
    assert page.count("player to be determined") == 4
    assert page.count("entry route not yet published") == 7
    assert "#80 · Lorenzo Sonego" in page
    assert "No official alternate list has been published" in page
    assert "The draw has not been published" in page
