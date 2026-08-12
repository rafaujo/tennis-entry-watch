from pathlib import Path

from tennis_entry_watch.site.build import build_page, build_site


def test_page_contains_tournament_entries_and_disclaimer(current):
    page = build_page(current)
    assert "Sample Open" in page
    assert "Marco Silva" in page
    assert "fictional tournament" in page
    assert "Entry snapshot" in page


def test_real_pre_draw_page_shows_confirmed_and_pending_places():
    from tennis_entry_watch.models import EntryList

    source = Path("data/entries/winston-salem-open-2026/current.json")
    entry_list = EntryList.model_validate_json(source.read_text(encoding="utf-8"))
    page = build_page(entry_list)
    assert "PRE-DRAW · ENTRY WATCH" in page
    assert "37/48" in page
    assert page.count("determined in qualifying") == 4
    assert page.count("not announced") == 4
    assert page.count("special exempt / late entry / performance bye allocation pending") == 3
    assert "#80 · Lorenzo Sonego" in page
    assert "No verified alternate list is available" in page
    assert "The draw has not been published" in page
    assert "22 Aug–29 Aug 2026" in page


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
    assert "Neither predicts qualification" in page


def test_full_site_builds_tournaments_and_player_schedules(tmp_path):
    written = build_site(Path("data/entries"), tmp_path)
    assert tmp_path / "index.html" in written
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Grand Slams &amp; ATP Tour" in index
    assert "Challenger Tour" in index
    assert "Week of 17 Aug 2026" in index
    assert "Week of 24 Aug 2026" in index
    assert "Week of 31 Aug 2026" in index
    tour_start = index.index("Grand Slams &amp; ATP Tour")
    challenger_start = index.index("Challenger Tour", tour_start)
    assert tour_start < challenger_start
    tour_block = index[tour_start:challenger_start]
    challenger_block = index[challenger_start:]
    assert "Winston-Salem Open" in tour_block
    assert "US Open" in tour_block
    assert "Kingston 1" not in tour_block
    assert challenger_block.index("Week of 17 Aug 2026") < challenger_block.index("Week of 24 Aug 2026") < challenger_block.index("Week of 31 Aug 2026")
    assert "Kingston 1" in challenger_block
    assert "Como Lake Challenger" in challenger_block
    assert "Allershausen" not in index
    assert (tmp_path / "tournaments" / "us-open-2026.html").exists()
    assert (tmp_path / "tournaments" / "cancun-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "quebec-city-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "augsburg-challenger-2026.html").exists()
    assert (tmp_path / "tournaments" / "manacor-challenger-2026.html").exists()
    schedules = (tmp_path / "schedules" / "index.html").read_text(encoding="utf-8")
    assert "Player schedules" in schedules
    assert "Luciano Darderi" in schedules
    assert "Winston-Salem Open" in schedules
    assert "US Open" in schedules
    assert "Live rank" in schedules
    assert "Allershausen" not in schedules
    assert schedules.index("Jannik Sinner") < schedules.index("Carlos Alcaraz")
    us_open = (tmp_path / "tournaments" / "us-open-2026.html").read_text(encoding="utf-8")
    assert us_open.count('status-qalt">LISTED Q') == 117
    assert "Tracked secondary · live ranking" in us_open
    winston_salem = (tmp_path / "tournaments" / "winston-salem-open-2026.html").read_text(encoding="utf-8")
    assert "Live ranking<br><strong>2026-08-12 16:39 UTC" in winston_salem
    assert "No qualifying players are currently listed in the tracked schedule" in winston_salem
    assert "ATP official · 2026 draw composition" in winston_salem
