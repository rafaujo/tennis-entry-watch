from pathlib import Path

from tennis_entry_watch.site.build import build_page, build_site


def test_page_contains_tournament_entries_and_disclaimer(current):
    page = build_page(current)
    assert "Sample Open" in page
    assert "Marco Silva" in page
    assert "fictional tournament" in page
    assert "Snapshot" in page


def test_real_pre_draw_page_shows_confirmed_and_pending_places():
    from tennis_entry_watch.models import EntryList

    source = Path("data/entries/winston-salem-open-2026/current.json")
    entry_list = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    page = build_page(entry_list)
    assert "PRE-DRAW · ENTRY WATCH" in page
    assert "37/48" in page
    assert page.count("determined in qualifying") == 4
    assert page.count("entry route not yet published") == 7
    assert "#80 · Lorenzo Sonego" in page
    assert "No verified alternate list is available" in page
    assert "The draw has not been published" in page


def test_us_open_page_shows_alternate_queue_and_promotion():
    from tennis_entry_watch.models import EntryList

    source = Path("data/entries/us-open-2026/current.json")
    entry_list = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    page = build_page(entry_list)
    assert "104/128" in page
    assert "99" in page
    assert "Benjamin Bonzi" in page
    assert "NEXT IN · 1 opening" in page
    assert "Aleksandar Vukic" in page
    assert "promoted from alternate" in page
    assert "Sebastian Korda" in page
    assert "PROJ Q" in page
    assert "Likely qualifying · MD alternate #1" in page
    assert "not confirmed acceptance" in page


def test_full_site_builds_tournaments_and_player_schedules(tmp_path):
    written = build_site(Path("data/entries"), tmp_path)
    assert tmp_path / "index.html" in written
    assert (tmp_path / "tournaments" / "us-open-2026.html").exists()
    schedules = (tmp_path / "schedules" / "index.html").read_text(encoding="utf-8")
    assert "Player schedules" in schedules
    assert "Luciano Darderi" in schedules
    assert "Winston-Salem Open" in schedules
    assert "US Open" in schedules
