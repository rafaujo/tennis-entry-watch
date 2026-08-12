from tennis_entry_watch.site.build import build_page


def test_page_contains_tournament_entries_and_disclaimer(current):
    page = build_page(current)
    assert "Sample Open" in page
    assert "Marco Silva" in page
    assert "fictional tournament" in page
    assert "Snapshot:" in page

