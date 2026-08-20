import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_current_atp_draws_are_monitored_from_official_pdfs() -> None:
    config = json.loads(
        (ROOT / "data/tournaments/draw_sources.json").read_text(encoding="utf-8")
    )
    events = {item["tournament_id"]: item for item in config["events"]}

    assert events["winston-salem-open-2026"] == {
        "tournament_id": "winston-salem-open-2026",
        "format": "protennislive_pdf",
        "main_url": "https://www.protennislive.com/posting/2026/6242/mds.pdf",
        "qualifying_url": "https://www.protennislive.com/posting/2026/6242/qs.pdf",
        "minimum_main_players": 32,
    }
    assert events["us-open-2026"] == {
        "tournament_id": "us-open-2026",
        "format": "protennislive_pdf",
        "main_url": "https://www.protennislive.com/posting/2026/560/mds.pdf",
        "qualifying_url": "https://www.protennislive.com/posting/2026/560/qs.pdf",
        "minimum_main_players": 112,
        "wildcard_url": "https://www.usopen.org/en_US/news/articles/2026-08-18/gael_monfils_alexei_popyrin_lead_2026_us_open_mens_wild_cards.html",
        "minimum_main_wildcards": 6,
        "main_wildcards": [
            "Michael Zheng",
            "J.J. Wolf",
            "Sebastian Gorzny",
            "Jack Kennedy",
            "Gael Monfils",
            "Dane Sweeny",
        ],
    }
