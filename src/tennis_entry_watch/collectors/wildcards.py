"""Pre-draw wildcard lists, associated through the calendar's exact singles page."""

import re
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup


def event_page_from_draw_url(draw_url: str | None, year: int) -> str | None:
    if not draw_url:
        return None
    parsed = urlparse(draw_url)
    if parsed.hostname != "en.wikipedia.org" or not parsed.path.startswith("/wiki/"):
        return None
    title = unquote(parsed.path[len("/wiki/"):]).replace("_", " ")
    if not title.startswith(f"{year} "):
        return None
    event_title = re.sub(r"\s+[–—-]\s+(?:Men's )?Singles$", "", title, flags=re.I)
    if event_title == title:
        return None
    return "https://en.wikipedia.org/wiki/" + quote(event_title.replace(" ", "_"))


def parse_wikipedia_wildcards(page_html: str) -> tuple[list[str], list[str]]:
    """Read explicit singles WC lists, not seeds, doubles, withdrawals or prose."""
    soup = BeautifulSoup(page_html, "html.parser")
    main: list[str] = []
    qualifying: list[str] = []
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if not re.search(r"received wild\s*cards? into (?:the )?(?:men's )?singles", text, re.I):
            continue
        if re.search(r"qualifying", text, re.I):
            target = qualifying
        elif re.search(r"main draw", text, re.I):
            target = main
        else:
            continue
        listing = paragraph.find_next_sibling()
        if listing is None or listing.name != "ul":
            continue
        for item in listing.find_all("li", recursive=False):
            for citation in item.select("sup"):
                citation.decompose()
            links = [link.get_text(" ", strip=True) for link in item.find_all("a")]
            name = next((name for name in links if name), item.get_text(" ", strip=True))
            if re.search(r"\b(?:TBA|TBD|to be announced)\b", name, re.I):
                continue
            if len(name.split()) < 2 or any(char.isdigit() for char in name):
                continue
            if name not in target:
                target.append(name)
    return main, qualifying
