import argparse
import html
from collections import defaultdict
from pathlib import Path

from tennis_entry_watch.models import EntryList, EntryStatus, SourceType
from tennis_entry_watch.normalize.players import stable_player_id
from tennis_entry_watch.collectors.live_tennis_snapshot import (
    entry_lists_from_live_snapshot,
    load_live_snapshot,
)


MAIN_DRAW_STATUSES = {
    EntryStatus.DA,
    EntryStatus.PR,
    EntryStatus.WC,
    EntryStatus.Q,
    EntryStatus.LL,
    EntryStatus.SE,
}

STATUS_LABELS = {
    EntryStatus.DA: "Direct acceptance",
    EntryStatus.PR: "Protected ranking",
    EntryStatus.WC: "Wild card",
    EntryStatus.Q: "Qualifier",
    EntryStatus.LL: "Lucky loser",
    EntryStatus.SE: "Special exempt",
    EntryStatus.ALT: "Main-draw alternate",
    EntryStatus.QDA: "Qualifying acceptance",
    EntryStatus.QALT: "Qualifying alternate",
    EntryStatus.OUT: "Withdrawn",
}

SOURCE_LABELS = {
    SourceType.ATP_OFFICIAL: "ATP official",
    SourceType.TOURNAMENT_OFFICIAL: "Tournament official",
    SourceType.TRUSTED_SECONDARY: "Tracked secondary",
    SourceType.MANUAL: "Manual",
    SourceType.AI_EXTRACTED: "AI-assisted extraction",
}

CSS = """
:root{--nav:#10283d;--blue:#176b98;--sky:#eaf5fb;--ink:#15222c;--muted:#64727e;--line:#d4dde4;--soft:#f4f7f9;--paper:#fff;--green:#17704d;--amber:#8a5b00;--red:#a02b35}
*{box-sizing:border-box}body{margin:0;background:#edf2f5;color:var(--ink);font:14px/1.45 Arial,Helvetica,sans-serif}.topbar{background:var(--nav);border-bottom:4px solid #32a0d5;color:#fff}.nav{max-width:1180px;margin:auto;display:flex;align-items:center;gap:22px;padding:11px 18px}.brand{font-size:17px;font-weight:800;letter-spacing:.04em;color:#fff;text-decoration:none}.navlinks{display:flex;gap:18px;margin-left:auto}.navlinks a{color:#dce9f2;text-decoration:none}.navlinks a:hover{color:#fff}
main{max-width:1180px;margin:18px auto 44px;background:var(--paper);border:1px solid var(--line);padding:22px 24px}h1{font-size:28px;margin:0 0 5px}h2{font-size:19px;margin:28px 0 8px;border-bottom:2px solid var(--blue);padding-bottom:5px}h3{margin:0;font-size:18px}.eyebrow{color:var(--blue);font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.phase{display:inline-block;background:var(--sky);color:#0d587f;border:1px solid #abd3e8;border-radius:3px;padding:3px 7px;font-size:11px;font-weight:800;letter-spacing:.06em}.subhead{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.meta,.explain{color:var(--muted);margin:7px 0}.updated{text-align:right;color:var(--muted);font-size:12px}.updated strong{color:var(--ink)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);margin:18px 0 9px}.metric{padding:11px 13px;border-right:1px solid var(--line)}.metric:last-child{border:0}.metric strong{display:block;font-size:19px}.metric span{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}.notice{background:#fff8dd;border:1px solid #ecd78a;padding:10px 12px;margin:12px 0}.info{background:var(--sky);border:1px solid #bcddec;padding:10px 12px;margin:12px 0}
.scroll{overflow-x:auto;border:1px solid var(--line)}table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:7px 9px;border-bottom:1px solid #e1e7eb;text-align:left;white-space:nowrap}th{background:#e9eef2;color:#344553;font-size:11px;text-transform:uppercase;letter-spacing:.04em}tbody tr:nth-child(even){background:#f8fafb}tbody tr:hover{background:#eef6fa}td.num,th.num{text-align:right}td.player{font-weight:600;min-width:210px}td small{display:block;color:var(--muted);font-weight:400}.empty td{text-align:center;padding:20px;color:var(--muted);font-style:italic}.pending td{color:var(--muted)}
.status,.chance{display:inline-block;border-radius:2px;padding:2px 6px;font-size:11px;font-weight:800}.status{min-width:38px;text-align:center;background:#dfe8ee;color:#314553}.status-da,.status-pr,.status-qda{background:#dcefe7;color:#115b3e}.status-alt,.status-qalt{background:#fff0c2;color:#775000}.status-out{background:#f6d8da;color:#822128}.status-pending{background:#eceff2;color:#68737c}.chance-next{background:#d9f0e5;color:#11603f}.chance-near{background:#fff0c2;color:#725000}.chance-queue{background:#e9eef2;color:#50606c}.promoted{color:var(--green);font-weight:700}.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:8px;color:var(--muted);font-size:12px}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:18px}.card{border:1px solid var(--line);border-top:4px solid var(--blue);padding:16px;background:#fff}.card a{text-decoration:none;color:var(--ink)}.card a:hover{color:var(--blue)}.card-meta{color:var(--muted);margin:5px 0 12px}.card-stats{display:flex;gap:20px;border-top:1px solid var(--line);padding-top:11px}.card-stats strong{display:block;font-size:18px}.card-stats span{color:var(--muted);font-size:11px;text-transform:uppercase}.filters{display:flex;gap:10px;margin:14px 0}.filters input{width:100%;max-width:440px;border:1px solid #aebbc5;border-radius:3px;padding:9px 11px;font:inherit}.sources{background:var(--soft);border:1px solid var(--line);padding:11px 14px}.sources ul{margin:4px 0;padding-left:20px}a{color:var(--blue)}.footer-note{color:var(--muted);font-size:12px;margin-top:18px}
.tournament-page{max-width:1380px}.entry-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}.tournament-page h2{margin-top:18px}.tournament-page th,.tournament-page td{padding:3px 6px;font-size:12px;line-height:1.25}.tournament-page th{font-size:10px}.tournament-page td.player{min-width:150px}.tournament-page .status,.tournament-page .chance{font-size:10px;padding:1px 4px}.tournament-page .explain{font-size:12px;margin:4px 0 6px}
@media(max-width:760px){main{margin:0;border-width:0;padding:15px}.navlinks{gap:11px;font-size:12px}.subhead{display:block}.updated{text-align:left;margin-top:8px}.summary{grid-template-columns:1fr 1fr}.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}.cards{grid-template-columns:1fr}.hide-mobile{display:none}}
@media(max-width:980px){.entry-grid{grid-template-columns:1fr}}
"""


def _rank(value: int | None) -> str:
    return str(value) if value is not None else "—"


def _status(entry) -> str:
    detail = STATUS_LABELS[entry.status]
    movement = ""
    if entry.previous_status == EntryStatus.ALT and entry.status in MAIN_DRAW_STATUSES:
        movement = '<small class="promoted">promoted from alternate</small>'
    return (
        f'<span class="status status-{entry.status.value.lower()}" title="{html.escape(detail)}">'
        f'{entry.status.value}</span>{movement}'
    )


def _chance(position: int) -> str:
    if position == 1:
        return '<span class="chance chance-next">NEXT IN · 1 opening</span>'
    if position <= 4:
        return f'<span class="chance chance-near">{position} openings away</span>'
    return f'<span class="chance chance-queue">{position} openings away</span>'


def _nav(home_href: str, schedules_href: str) -> str:
    return (
        '<header class="topbar"><nav class="nav">'
        f'<a class="brand" href="{home_href}">TENNIS ENTRY WATCH</a>'
        '<div class="navlinks">'
        f'<a href="{home_href}">Tournaments</a>'
        f'<a href="{schedules_href}">Player schedules</a>'
        '</div></nav></header>'
    )


def _entry_row(entry) -> str:
    return (
        '<tr>'
        f'<td class="num">{_rank(entry.projected_seed)}</td>'
        f'<td class="player">{html.escape(entry.player.name)}</td>'
        f'<td>{html.escape(entry.player.nationality or "—")}</td>'
        f'<td class="num">{_rank(entry.current_rank)}</td>'
        f'<td class="num">{_rank(entry.entry_rank)}</td>'
        f'<td>{_status(entry)}</td></tr>'
    )


def _pending_row(label: str, status: str, detail: str) -> str:
    return (
        '<tr class="pending"><td class="num">—</td>'
        f'<td class="player">{html.escape(label)}<small>{html.escape(detail)}</small></td>'
        '<td>—</td><td class="num">—</td><td class="num">—</td>'
        f'<td><span class="status status-pending">{html.escape(status)}</span></td></tr>'
    )


def build_page(entry_list: EntryList, home_href: str = "../index.html", schedules_href: str = "../schedules/index.html", live_schedules: list[dict] | None = None) -> str:
    t = entry_list.tournament
    main_entries = sorted(
        (entry for entry in entry_list.entries if entry.status in MAIN_DRAW_STATUSES),
        key=lambda entry: (entry.entry_rank or 9999, entry.player.name),
    )
    seed_slots = (
        32 if t.category.lower() == "grand slam"
        else 8 if t.category.lower().startswith("challenger")
        else min(16, len(main_entries))
    )
    seedable = sorted((entry for entry in main_entries if entry.current_rank), key=lambda entry: entry.current_rank)
    for projected_seed, entry in enumerate(seedable[:seed_slots], 1):
        entry.projected_seed = projected_seed
    main_entries.sort(
        key=lambda entry: (
            entry.projected_seed is None,
            entry.projected_seed or entry.current_rank or entry.entry_rank or 9999,
            entry.player.name,
        )
    )
    alternates = sorted(
        (entry for entry in entry_list.entries if entry.status == EntryStatus.ALT),
        key=lambda entry: entry.alternate_position or 9999,
    )
    withdrawals = sorted(
        (entry for entry in entry_list.entries if entry.status == EntryStatus.OUT),
        key=lambda entry: entry.withdrawn_at or entry_list.snapshot_at,
        reverse=True,
    )
    q_acceptances = sorted(
        (entry for entry in entry_list.qualifying_entries if entry.status == EntryStatus.QDA),
        key=lambda entry: (entry.entry_rank or 9999, entry.player.name),
    )
    q_alternates = sorted(
        (entry for entry in entry_list.qualifying_entries if entry.status == EntryStatus.QALT),
        key=lambda entry: entry.alternate_position or 9999,
    )

    qualifier_slots = t.main_draw_qualifier_slots or 0
    wildcard_slots = t.main_draw_wildcard_slots or 0
    known_qualifiers = sum(entry.status == EntryStatus.Q for entry in main_entries)
    known_wildcards = sum(entry.status == EntryStatus.WC for entry in main_entries)
    qualifier_placeholders = max(0, qualifier_slots - known_qualifiers)
    wildcard_placeholders = max(0, wildcard_slots - known_wildcards)
    open_other = max(
        0,
        (t.main_draw_size or len(main_entries))
        - len(main_entries)
        - qualifier_placeholders
        - wildcard_placeholders,
    )
    cutoff_entries = [entry for entry in main_entries if entry.entry_rank is not None]
    cutoff = max(cutoff_entries, key=lambda entry: entry.entry_rank) if cutoff_entries else None

    main_rows = [_entry_row(entry) for entry in main_entries]
    main_rows.extend(
        _pending_row(f"Qualifier {index}", "Q", "determined in qualifying")
        for index in range(1, qualifier_placeholders + 1)
    )
    main_rows.extend(
        _pending_row(f"Wild card {index}", "WC", "not announced")
        for index in range(1, wildcard_placeholders + 1)
    )
    main_rows.extend(
        _pending_row(f"Open place {index}", "TBD", "entry route not yet published")
        for index in range(1, open_other + 1)
    )

    alternate_rows = "".join(
        '<tr>'
        f'<td class="num">{entry.alternate_position}</td>'
        f'<td class="player">{html.escape(entry.player.name)}</td>'
        f'<td>{html.escape(entry.player.nationality or "—")}</td>'
        f'<td class="num">{_rank(entry.entry_rank)}</td>'
        f'<td>{_chance(entry.alternate_position)}</td></tr>'
        for entry in alternates
    ) or '<tr class="empty"><td colspan="5">No verified alternate list is available from the selected source.</td></tr>'

    withdrawal_rows = "".join(
        '<tr>'
        f'<td>{entry.withdrawn_at.date().isoformat() if entry.withdrawn_at else "—"}</td>'
        f'<td class="player">{html.escape(entry.player.name)}</td>'
        f'<td>{html.escape(entry.player.nationality or "—")}</td>'
        f'<td>{entry.previous_status.value if entry.previous_status else "—"}</td>'
        f'<td class="num">{_rank(entry.entry_rank)}</td></tr>'
        for entry in withdrawals
    ) or '<tr class="empty"><td colspan="5">No withdrawals are identified in the selected source.</td></tr>'

    if q_acceptances or q_alternates:
        q_rows = "".join(
            '<tr>'
            f'<td class="num">{entry.alternate_position or "—"}</td>'
            f'<td class="player">{html.escape(entry.player.name)}</td>'
            f'<td>{html.escape(entry.player.nationality or "—")}</td>'
            f'<td class="num">{_rank(entry.current_rank or entry.entry_rank)}</td>'
            f'<td>{_status(entry)}</td>'
            f'<td>{_chance(entry.alternate_position) if entry.alternate_position else "In qualifying field"}</td></tr>'
            for entry in [*q_acceptances, *q_alternates]
        )
    elif (alternates or live_schedules) and t.qualifying_draw_size:
        alternate_by_id = {entry.player.player_id: entry for entry in alternates}
        projected = {}
        for entry in alternates:
            projected[entry.player.player_id] = {
                "rank": entry.current_rank,
                "name": entry.player.name,
                "nation": entry.player.nationality or "—",
                "entry_rank": entry.entry_rank,
                "listed": False,
            }
        if t.tournament_id == "us-open-2026":
            for item in live_schedules or []:
                if "Qual. US Open" not in item.get("events", []):
                    continue
                player_id = stable_player_id(item["name"])
                projected[player_id] = {
                    "rank": item.get("rank"),
                    "name": item["name"],
                    "nation": item.get("nation") or "—",
                    "entry_rank": alternate_by_id.get(player_id).entry_rank if player_id in alternate_by_id else None,
                    "listed": True,
                }
        q_rows = "".join(
            '<tr>'
            f'<td class="num">—</td>'
            f'<td class="player">{html.escape(item["name"])}</td>'
            f'<td>{html.escape(item["nation"])}</td>'
            f'<td class="num">{_rank(item["rank"])}</td>'
            f'<td><span class="status status-qalt">{"LISTED Q" if item["listed"] else "PROJ Q"}</span></td>'
            f'<td>{"Listed for qualifying" if item["listed"] else "Likely qualifying"}'
            f'{" · MD alternate #" + str(alternate_by_id[player_id].alternate_position) if player_id in alternate_by_id else ""}</td></tr>'
            for player_id, item in sorted(projected.items(), key=lambda pair: (pair[1]["rank"] or 9999, pair[1]["name"]))
        )
    else:
        q_rows = (
            '<tr class="empty"><td colspan="6">Qualifying entry list not yet available from a verified public source. '
            'Ranking alone is not treated as proof of entry.</td></tr>'
        )

    unique_sources = {}
    for entry in [*entry_list.entries, *entry_list.qualifying_entries]:
        unique_sources[(entry.source.url, entry.source.source_type)] = entry.source
    sources = "".join(
        '<li>'
        f'<a href="{html.escape(source.url, quote=True)}">{html.escape(SOURCE_LABELS[source.source_type])}</a>'
        f' · retrieved {source.retrieved_at:%Y-%m-%d}'
        '</li>'
        for source in unique_sources.values()
    )
    if live_schedules:
        sources += '<li><a href="https://live-tennis.eu/en/atp-live-ranking">Tracked secondary · live ranking</a></li>'
        sources += '<li><a href="https://live-tennis.eu/en/atp-schedule">Tracked secondary · player schedules</a></li>'
    cutoff_text = f"#{cutoff.entry_rank} · {html.escape(cutoff.player.name)}" if cutoff else "Not known"
    draw_phase = "PRE-DRAW · ENTRY WATCH" if t.draw_published is False else "ENTRY LIST"
    sample_notice = ""
    if t.tournament_id == "sample-open-2026":
        sample_notice = '<p class="notice"><strong>Sample data:</strong> This fictional tournament demonstrates the MVP.</p>'

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t.name)} entry watch</title><style>{CSS}</style></head><body>
{_nav(home_href, schedules_href)}
<main class="tournament-page">{sample_notice}<div class="subhead"><div><span class="phase">{draw_phase}</span><h1>{html.escape(t.name)}</h1><p class="meta">{t.start_date:%d %b}–{t.end_date:%d %b %Y} · {html.escape(t.category)} · {t.surface.value} · {html.escape(t.location.city)}, {html.escape(t.location.country)}</p></div><div class="updated">Snapshot<br><strong>{entry_list.snapshot_at:%Y-%m-%d %H:%M UTC}</strong></div></div>
<div class="summary"><div class="metric"><strong>{len(main_entries)}/{t.main_draw_size or '—'}</strong><span>named in main field</span></div><div class="metric"><strong>{len(alternates)}</strong><span>verified alternates</span></div><div class="metric"><strong>{len(withdrawals)}</strong><span>withdrawals tracked</span></div><div class="metric"><strong>{cutoff_text}</strong><span>current direct cutoff</span></div></div>
<p class="notice"><strong>The draw has not been published.</strong> This is an entry watch, not the draw. “X openings away” is the player's current queue distance, not a subjective probability.</p>
<div class="entry-grid"><section id="main-draw"><h2>Main draw</h2><p class="explain">Projected seeds use the current live ranking.</p><div class="scroll"><table><thead><tr><th class="num">Seed</th><th>Player / place</th><th>Nat.</th><th class="num">Rk</th><th class="num">ER</th><th>Status</th></tr></thead><tbody>{''.join(main_rows)}</tbody></table></div><div class="legend"><span><b>DA</b> Direct</span><span><b>PR</b> Protected ranking</span><span><b>Q</b> Qualifier</span><span><b>WC</b> Wild card</span></div></section><div>
<section id="alternates"><h2>Main-draw alternates</h2><p class="explain">The order follows the latest verified list. Each withdrawal can move the queue by one place.</p><div class="scroll"><table><thead><tr><th class="num">Queue</th><th>Player</th><th>Nation</th><th class="num">Entry rank</th><th>Path to main draw</th></tr></thead><tbody>{alternate_rows}</tbody></table></div></section>
<section id="withdrawals"><h2>Withdrawals</h2><div class="scroll"><table><thead><tr><th>Date</th><th>Player</th><th>Nat.</th><th>Previous</th><th class="num">ER</th></tr></thead><tbody>{withdrawal_rows}</tbody></table></div></section></div></div>
<section id="qualifying"><h2>Qualifying</h2><p class="explain"><b>LISTED Q</b> comes from the tracked Live Tennis schedule; <b>PROJ Q</b> is inferred from the verified main-draw alternate list. Neither predicts qualification.</p><div class="scroll"><table><thead><tr><th class="num">Q</th><th>Player</th><th>Nat.</th><th class="num">Live Rk</th><th>Status</th><th>Path</th></tr></thead><tbody>{q_rows}</tbody></table></div></section>
<section id="sources"><h2>Sources and method</h2><div class="sources"><ul>{sources}</ul><p>Official, tracked-secondary, and projected information are kept separate. A ranking position is never treated as confirmation that a player entered.</p></div></section>
</main></body></html>'''


def build_index(entry_lists: list[EntryList]) -> str:
    cards = []
    for entry_list in sorted(entry_lists, key=lambda item: item.tournament.start_date):
        t = entry_list.tournament
        main_count = sum(entry.status in MAIN_DRAW_STATUSES for entry in entry_list.entries)
        alt_count = sum(entry.status == EntryStatus.ALT for entry in entry_list.entries)
        cards.append(
            '<article class="card">'
            f'<span class="eyebrow">{html.escape(t.category)} · {t.surface.value}</span>'
            f'<h3><a href="tournaments/{t.tournament_id}.html">{html.escape(t.name)}</a></h3>'
            f'<p class="card-meta">{t.start_date:%d %b}–{t.end_date:%d %b %Y} · {html.escape(t.location.city)}, {html.escape(t.location.country)}</p>'
            '<div class="card-stats">'
            f'<div><strong>{main_count}</strong><span>Main entries</span></div>'
            f'<div><strong>{alt_count}</strong><span>Alternates</span></div>'
            f'<div><strong>{sum(entry.status == EntryStatus.OUT for entry in entry_list.entries)}</strong><span>Withdrawals</span></div>'
            '</div></article>'
        )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tennis Entry Watch</title><style>{CSS}</style></head><body>
{_nav("index.html", "schedules/index.html")}<main><span class="eyebrow">Upcoming tournaments</span><h1>Tennis entry lists before the draw</h1><p class="meta">Verified main-draw entries, alternate queues, qualifying paths, withdrawals, and player schedules.</p><div class="info"><strong>How to read it:</strong> confirmed entry is a fact from a cited list; queue distance is a calculation; projections are labelled separately.</div><div class="cards">{''.join(cards)}</div><p class="footer-note">Unofficial tracker. Always confirm time-sensitive participation with the tournament.</p></main></body></html>'''


def build_schedules(entry_lists: list[EntryList], live_snapshot: dict | None = None) -> str:
    players = defaultdict(lambda: {"name": "", "nation": "", "rank": None, "points": None, "events": [], "external": []})
    ranking_by_id = {}
    for item in (live_snapshot or {}).get("rankings", []):
        ranking_by_id[stable_player_id(item["name"])] = item
    for item in (live_snapshot or {}).get("schedules", []):
        player_id = stable_player_id(item["name"])
        record = players[player_id]
        record.update(name=item["name"], nation=item.get("nation") or "—", rank=item.get("rank"))
        record["points"] = ranking_by_id.get(player_id, {}).get("points")
        record["external"] = item.get("events", [])
    for entry_list in entry_lists:
        t = entry_list.tournament
        by_player = defaultdict(list)
        for entry in entry_list.entries:
            by_player[entry.player.player_id].append(entry)
        for entry in entry_list.qualifying_entries:
            by_player[entry.player.player_id].append(entry)
        for player_id, entries in by_player.items():
            first = entries[0]
            record = players[player_id]
            record["name"] = first.player.name
            if first.player.nationality:
                record["nation"] = first.player.nationality
            rank_item = ranking_by_id.get(player_id, {})
            record["rank"] = rank_item.get("rank", first.current_rank)
            record["points"] = rank_item.get("points")
            labels = []
            for entry in entries:
                label = entry.status.value
                if entry.alternate_position:
                    label += f" #{entry.alternate_position}"
                labels.append(label)
            record["events"].append((t.start_date, t.name, t.tournament_id, " + ".join(labels)))

    rows = []
    for record in sorted(players.values(), key=lambda item: (item["rank"] or 99999, item["name"])):
        events = sorted(record["events"])
        aliases = {
            "Europcar Cancun Country Club": "cancun",
            "Quebec National Bank Challenger": "quebec city",
            "Kingston 1": "kingston",
            "Advantage Cars Prague Open": "prague",
            "Roehampton 1": "roehampton",
            "Sion Challenger": "sion",
            "Winston-Salem Open": "winston salem",
            "US Open": "us open",
        }
        tracked_names = {
            aliases.get(name, name).lower().replace("-", " ")
            for _, name, _, _ in events
        }
        tracked_html = [
            f'<a href="../tournaments/{event_id}.html">{html.escape(name)}</a> '
            f'<span class="status status-{status.split()[0].lower()}">{html.escape(status)}</span>'
            for _, name, event_id, status in events
        ]
        external = [event for event in record["external"] if event.lower().replace("-", " ") not in tracked_names]
        external_html = [f'{html.escape(event)} <span class="status">LISTED</span>' for event in external]
        event_html = "<br>".join([*tracked_html, *external_html]) or "—"
        all_names = [event[1] for event in events] + external
        search = html.escape(f'{record["name"]} {record["nation"]} {" ".join(all_names)}'.lower(), quote=True)
        rows.append(
            f'<tr data-search="{search}"><td class="num">{_rank(record["rank"])}</td>'
            f'<td class="player">{html.escape(record["name"])}</td><td>{html.escape(record["nation"])}</td>'
            f'<td class="num">{_rank(record["points"])}</td><td>{event_html}</td><td class="num">{len(all_names)}</td></tr>'
        )
    retrieved_raw = (live_snapshot or {}).get("retrieved_at")
    retrieved = f'{retrieved_raw.replace("T", " ")[:16]} UTC' if retrieved_raw else "not available"
    source_url = (live_snapshot or {}).get("schedule_source", "https://live-tennis.eu/en/atp-schedule")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Player schedules | Tennis Entry Watch</title><style>{CSS}</style></head><body>
{_nav("../index.html", "index.html")}<main><span class="eyebrow">Ordered by live ranking</span><h1>Player schedules</h1><p class="meta">Current live rank and upcoming tournament listings. Tracked tournament statuses take priority over the secondary schedule.</p><div class="info">Live Tennis snapshot: {html.escape(retrieved)} · <a href="{html.escape(source_url, quote=True)}">schedule source</a></div><div class="filters"><input id="search" type="search" placeholder="Search player, country, or tournament…" aria-label="Search schedules"></div><div class="scroll"><table id="schedule"><thead><tr><th class="num">Live rank</th><th>Player</th><th>Nation</th><th class="num">Points</th><th>Tournaments and entry status</th><th class="num">Events</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p class="footer-note">This is not a travel itinerary: players may withdraw, and alternate status does not guarantee a place.</p></main><script>const input=document.querySelector('#search');input.addEventListener('input',()=>{{const q=input.value.trim().toLowerCase();document.querySelectorAll('#schedule tbody tr').forEach(row=>row.hidden=!row.dataset.search.includes(q));}});</script></body></html>'''


def discover_entry_lists(data_root: Path) -> list[EntryList]:
    entry_lists = []
    for path in sorted(data_root.glob("*/current.json")):
        data = EntryList.model_validate_json(path.read_text(encoding="utf-8"))
        if not data.tournament.tournament_id.startswith("sample-"):
            entry_lists.append(data)
    return entry_lists


def build_site(data_root: Path, output_dir: Path, ranking_path: Path = Path("data/rankings/atp-live-current.json")) -> list[Path]:
    entry_lists = discover_entry_lists(data_root)
    if not entry_lists:
        raise ValueError(f"no current entry lists found under {data_root}")
    live_snapshot = load_live_snapshot(ranking_path) if ranking_path.exists() else {}
    known_ids = {item.tournament.tournament_id for item in entry_lists}
    entry_lists.extend(
        item
        for item in entry_lists_from_live_snapshot(live_snapshot)
        if item.tournament.tournament_id not in known_ids
    )
    ranking_by_id = {stable_player_id(item["name"]): item for item in live_snapshot.get("rankings", [])}
    for entry_list in entry_lists:
        for entry in [*entry_list.entries, *entry_list.qualifying_entries]:
            ranking = ranking_by_id.get(entry.player.player_id)
            if ranking:
                entry.current_rank = ranking["rank"]
    tournaments_dir = output_dir / "tournaments"
    schedules_dir = output_dir / "schedules"
    tournaments_dir.mkdir(parents=True, exist_ok=True)
    schedules_dir.mkdir(parents=True, exist_ok=True)
    written = []
    index_path = output_dir / "index.html"
    index_path.write_text(build_index(entry_lists), encoding="utf-8")
    written.append(index_path)
    for entry_list in entry_lists:
        destination = tournaments_dir / f"{entry_list.tournament.tournament_id}.html"
        destination.write_text(build_page(entry_list, live_schedules=live_snapshot.get("schedules", [])), encoding="utf-8")
        written.append(destination)
    schedules_path = schedules_dir / "index.html"
    schedules_path.write_text(build_schedules(entry_lists, live_snapshot), encoding="utf-8")
    written.append(schedules_path)
    return written


def build(input_path: Path, output_dir: Path) -> Path:
    """Backward-compatible single-page builder used by early integrations."""
    data = EntryList.model_validate_json(input_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "index.html"
    destination.write_text(build_page(data, "index.html", "schedules/index.html"), encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the static entry-watch site")
    parser.add_argument("--data-root", type=Path, default=Path("data/entries"))
    parser.add_argument("--output", type=Path, default=Path("site"))
    args = parser.parse_args()
    for path in build_site(args.data_root, args.output):
        print(path)


if __name__ == "__main__":
    main()
