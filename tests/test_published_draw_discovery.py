from datetime import date
from pathlib import Path

from tennis_entry_watch.models import EntryStatus
from tennis_entry_watch.collectors.published_draws import (
    _us_open_text_names,
    discover_atp_draw_sources,
    discover_challenger_draw_sources,
    discover_wikipedia_challenger_draw_sources,
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

CHALLENGER_HTML = """
<a href="/en/tournaments/kingston/3129/overview">
  Kingston 2, Jamaica | 24 - 29 August, 2026
</a>
<a href="/en/tournaments/roehampton-2/3125/overview">
  Roehampton 2, Great Britain | 24 - 29 August, 2026
</a>
<a href="/en/tournaments/augsburg/8266/overview">
  Schwaben Open Augsburg, Germany | 24 - 29 August, 2026
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


def test_challenger_discovery_builds_official_pdf_urls():
    catalog = load_catalog(ROOT / "data/tournaments/catalog.json")
    sources = discover_challenger_draw_sources(
        CHALLENGER_HTML,
        catalog,
        today=date(2026, 8, 27),
    )
    by_tournament = {item["tournament_id"]: item for item in sources}

    assert by_tournament["kingston-2-challenger-2026"]["main_url"].endswith(
        "/3129/mds.pdf"
    )
    assert by_tournament["roehampton-2-challenger-2026"]["qualifying_url"].endswith(
        "/3125/qs.pdf"
    )
    assert by_tournament["augsburg-challenger-2026"]["minimum_main_players"] == 24


def test_us_open_parser_reads_official_draw_and_wild_cards():
    names = _us_open_text_names(
        """US Open 2026
Men's Singles
Round 1
[1]1.ZVEREV, Alexander GER
(Q/LL)2.QUALIFIER/LUCKY LOSER
(W)3.ZHENG, Michael USA
4.KHACHANOV, Karen
Round 2
A. ZVEREV [1]
"""
    )

    assert names == [
        ("Alexander ZVEREV", EntryStatus.DA, "GER", 1),
        ("Michael ZHENG", EntryStatus.WC, "USA", None),
        ("Karen KHACHANOV", EntryStatus.DA, None, None),
    ]


def test_wikipedia_discovery_matches_the_second_tournament_week():
    catalog = load_catalog(ROOT / "data/tournaments/catalog.json")

    class Response:
        def __init__(self, url):
            self.url = url
            self.text = (
                "<main>Date 24–29 August 2026</main>"
                if "Kingston_Open_II" in url
                else "<main>Date 17–22 August 2026</main>"
            )

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "query": {
                    "search": [
                        {"title": "2026 Kingston Open – Singles"},
                        {"title": "2026 Kingston Open II – Singles"},
                    ]
                }
            }

    class Session:
        def get(self, url, **_kwargs):
            return Response(url)

    sources, warnings = discover_wikipedia_challenger_draw_sources(
        catalog,
        Session(),
        today=date(2026, 8, 27),
        lookahead_days=0,
    )

    assert warnings == []
    assert sources == [
        {
            "tournament_id": "kingston-2-challenger-2026",
            "format": "wikipedia_draw",
            "main_url": (
                "https://en.wikipedia.org/wiki/"
                "2026_Kingston_Open_II_%E2%80%93_Singles"
            ),
            "minimum_main_players": 24,
        }
    ]

