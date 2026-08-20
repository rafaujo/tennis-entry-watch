from datetime import date
from pathlib import Path

from tennis_entry_watch.collectors.published_draws import (
    discover_atp_draw_sources,
    parse_atp_tournament_links,
)
from tennis_entry_watch.collectors.tournament_catalog import load_catalog


ROOT = Path(__file__).resolve().parents[1]
ATP_HTML = """
<a href="/en/tournaments/winston-salem/6242/overview">
  Winston-Salem, United States Winston-Salem Open | 23 - 29 August, 2026
</a>
<a href="/en/tournaments/us-open/560/overview">
  US Open New York, United States | 30 August - 13 September, 2026
</a>
<a href="/en/tournaments/chengdu/7581/overview">
  Chengdu, China Chengdu Open | 23 - 29 September, 2026
</a>
<a href="/en/tournaments/hangzhou/4713/overview">
  Hangzhou, China Hangzhou Open | 23 - 29 September, 2026
</a>
<a href="/en/tournaments/beijing/747/overview">
  Beijing, China China Open | 30 September - 6 October, 2026
</a>
<a href="/en/tournaments/davis-cup-qualifiers-2nd-rd/8097/overview">
  Davis Cup Qualifiers 2nd Rd Multiple Locations | 17 - 20 September, 2026
</a>
"""


def test_parse_atp_tournament_links_extracts_ids_and_start_dates():
    links = {item["atp_id"]: item for item in parse_atp_tournament_links(ATP_HTML)}

    assert links["6242"]["start_date"] == date(2026, 8, 23)
    assert links["560"]["start_date"] == date(2026, 8, 30)
    assert links["560"]["slug"] == "us-open"


def test_discovery_matches_catalog_and_builds_official_pdf_urls():
    catalog = load_catalog(ROOT / "data/tournaments/catalog.json")
    sources = discover_atp_draw_sources(
        ATP_HTML,
        catalog,
        today=date(2026, 8, 20),
    )
    by_tournament = {item["tournament_id"]: item for item in sources}

    assert by_tournament["winston-salem-open-2026"]["main_url"] == (
        "https://www.protennislive.com/posting/2026/6242/mds.pdf"
    )
    assert by_tournament["us-open-2026"]["qualifying_url"] == (
        "https://www.protennislive.com/posting/2026/560/qs.pdf"
    )
    assert by_tournament["chengdu-open-2026"]["main_url"].endswith("/7581/mds.pdf")
    assert by_tournament["hangzhou-open-2026"]["main_url"].endswith("/4713/mds.pdf")
    assert by_tournament["china-open-2026"]["main_url"].endswith("/747/mds.pdf")
    assert all("8097" not in item["main_url"] for item in sources)

