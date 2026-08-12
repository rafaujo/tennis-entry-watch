import argparse
import html
from pathlib import Path

from tennis_entry_watch.models import EntryList, EntryStatus


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
    EntryStatus.ALT: "Alternate",
    EntryStatus.OUT: "Withdrawn",
}


def _rank(value: int | None) -> str:
    return str(value) if value is not None else "—"


def _entry_row(entry) -> str:
    projected_seed = _rank(entry.projected_seed)
    return (
        f'<tr><td class="num">{projected_seed}</td>'
        f'<td class="player">{html.escape(entry.player.name)}</td>'
        f'<td>{html.escape(entry.player.nationality or "—")}</td>'
        f'<td class="num">{_rank(entry.current_rank)}</td>'
        f'<td class="num">{_rank(entry.entry_rank)}</td>'
        f'<td><span class="status status-{entry.status.value.lower()}">{entry.status.value}</span></td></tr>'
    )


def _pending_row(label: str, status: str, detail: str) -> str:
    return (
        '<tr class="pending"><td class="num">—</td>'
        f'<td class="player">{html.escape(label)} <small>{html.escape(detail)}</small></td>'
        '<td>—</td><td class="num">—</td><td class="num">—</td>'
        f'<td><span class="status status-pending">{html.escape(status)}</span></td></tr>'
    )


def build_page(entry_list: EntryList) -> str:
    t = entry_list.tournament
    entries = entry_list.entries
    main_entries = sorted(
        (entry for entry in entries if entry.status in MAIN_DRAW_STATUSES),
        key=lambda entry: (entry.entry_rank or 9999, entry.player.name),
    )
    alternates = sorted(
        (entry for entry in entries if entry.status == EntryStatus.ALT),
        key=lambda entry: entry.alternate_position or 9999,
    )
    withdrawals = sorted(
        (entry for entry in entries if entry.status == EntryStatus.OUT),
        key=lambda entry: entry.withdrawn_at or entry_list.snapshot_at,
        reverse=True,
    )

    qualifier_slots = t.main_draw_qualifier_slots or 0
    known_qualifiers = sum(entry.status == EntryStatus.Q for entry in main_entries)
    qualifier_placeholders = max(0, qualifier_slots - known_qualifiers)
    open_other = max(
        0,
        (t.main_draw_size or len(main_entries)) - len(main_entries) - qualifier_placeholders,
    )
    confirmed = len(main_entries)
    cutoff_entries = [entry for entry in main_entries if entry.entry_rank is not None]
    cutoff = max(cutoff_entries, key=lambda entry: entry.entry_rank) if cutoff_entries else None

    main_rows = [_entry_row(entry) for entry in main_entries]
    main_rows.extend(
        _pending_row(f"Qualifier {index}", "Q", "player to be determined")
        for index in range(1, qualifier_placeholders + 1)
    )
    main_rows.extend(
        _pending_row(f"Unfilled main-draw place {index}", "TBD", "entry route not yet published")
        for index in range(1, open_other + 1)
    )

    alternate_rows = "".join(
        '<tr>'
        f'<td class="num">{entry.alternate_position}</td>'
        f'<td class="player">{html.escape(entry.player.name)}</td>'
        f'<td>{html.escape(entry.player.nationality or "—")}</td>'
        f'<td class="num">{_rank(entry.current_rank)}</td>'
        f'<td class="num">{_rank(entry.entry_rank)}</td></tr>'
        for entry in alternates
    )
    if not alternate_rows:
        alternate_rows = '<tr class="empty"><td colspan="5">No official alternate list has been published by the selected source.</td></tr>'

    withdrawal_rows = "".join(
        '<tr>'
        f'<td>{entry.withdrawn_at.date().isoformat() if entry.withdrawn_at else "—"}</td>'
        f'<td class="player">{html.escape(entry.player.name)}</td>'
        f'<td>{html.escape(entry.player.nationality or "—")}</td>'
        f'<td>{entry.previous_status.value if entry.previous_status else "—"}</td>'
        f'<td class="num">{_rank(entry.entry_rank)}</td></tr>'
        for entry in withdrawals
    )
    if not withdrawal_rows:
        withdrawal_rows = '<tr class="empty"><td colspan="5">No withdrawals are identified in the selected official source.</td></tr>'

    source_urls = sorted({entry.source.url for entry in entries})
    sources = "".join(
        f'<li><a href="{html.escape(url, quote=True)}">Official entry-list announcement</a></li>'
        for url in source_urls
    )
    cutoff_text = f"#{cutoff.entry_rank} · {html.escape(cutoff.player.name)}" if cutoff else "Not known"
    draw_phase = "PRE-DRAW · ENTRY LIST" if t.draw_published is False else "ENTRY LIST"
    sample_notice = ""
    if t.tournament_id == "sample-open-2026":
        sample_notice = '<p class="notice"><strong>Sample data:</strong> This fictional tournament demonstrates the MVP.</p>'

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t.name)} ATP Entry List | Tennis Entry Watch</title>
<style>
:root{{--nav:#11263d;--blue:#185f8d;--ink:#17212b;--muted:#66727e;--line:#d6dde3;--soft:#f3f6f8;--paper:#fff;--green:#16734f;--amber:#9a6300;--red:#a32b32}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf1f4;color:var(--ink);font:14px/1.4 Arial,Helvetica,sans-serif}}
.topbar{{background:var(--nav);border-bottom:4px solid #2b91c9;color:#fff}}.nav{{max-width:1160px;margin:auto;display:flex;align-items:center;gap:22px;padding:10px 18px}}
.brand{{font-size:17px;font-weight:800;letter-spacing:.04em;color:#fff;text-decoration:none}}.navlinks{{display:flex;gap:16px;margin-left:auto}}.navlinks a{{color:#dce8f1;text-decoration:none}}
main{{max-width:1160px;margin:18px auto 44px;background:var(--paper);border:1px solid var(--line);padding:20px 22px}}h1{{font-size:27px;margin:0 0 4px}}h2{{font-size:19px;margin:28px 0 8px;border-bottom:2px solid var(--blue);padding-bottom:5px}}
.phase{{display:inline-block;background:#e7f2f8;color:#0e557e;border:1px solid #afd3e6;border-radius:3px;padding:3px 7px;font-size:11px;font-weight:800;letter-spacing:.06em}}
.subhead{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}}.meta{{margin:7px 0;color:var(--muted)}}.updated{{text-align:right;color:var(--muted);font-size:12px}}
.summary{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);margin:18px 0 8px}}.metric{{padding:11px 13px;border-right:1px solid var(--line)}}.metric:last-child{{border:0}}.metric strong{{display:block;font-size:19px}}.metric span{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
.notice{{background:#fff8dd;border:1px solid #ecd78a;padding:9px 11px;margin:12px 0}}.explain{{color:var(--muted);margin:6px 0 9px}}
.scroll{{overflow-x:auto;border:1px solid var(--line)}}table{{width:100%;border-collapse:collapse;background:#fff}}caption{{text-align:left;font-weight:bold;padding:8px;background:var(--soft)}}th,td{{padding:6px 9px;border-bottom:1px solid #e2e7eb;text-align:left;white-space:nowrap}}th{{background:#e9eef2;color:#344553;font-size:11px;text-transform:uppercase;letter-spacing:.04em}}tbody tr:nth-child(even){{background:#f8fafb}}tbody tr:hover{{background:#eef6fa}}td.num,th.num{{text-align:right}}td.player{{font-weight:600;min-width:220px}}td small{{display:block;color:var(--muted);font-weight:400}}
.status{{display:inline-block;min-width:38px;text-align:center;border-radius:2px;padding:2px 5px;background:#dfe8ee;color:#314553;font-size:11px;font-weight:800}}.status-da{{background:#dcefe7;color:#115b3e}}.status-alt{{background:#fff0c2;color:#775000}}.status-out{{background:#f6d8da;color:#822128}}.status-pending{{background:#eceff2;color:#68737c}}
.pending td{{color:#66727e}}.empty td{{text-align:center;padding:17px;color:var(--muted);font-style:italic}}.legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:8px;color:var(--muted);font-size:12px}}
.sources{{background:var(--soft);border:1px solid var(--line);padding:11px 14px}}.sources ul{{margin:4px 0;padding-left:20px}}a{{color:var(--blue)}}
@media(max-width:760px){{main{{margin:0;border-width:0;padding:15px}}.navlinks{{display:none}}.subhead{{display:block}}.updated{{text-align:left;margin-top:8px}}.summary{{grid-template-columns:1fr 1fr}}.metric:nth-child(2){{border-right:0}}.metric:nth-child(-n+2){{border-bottom:1px solid var(--line)}}}}
</style></head><body>
<header class="topbar"><nav class="nav"><a class="brand" href="index.html">TENNIS ENTRY WATCH</a><div class="navlinks"><a href="#main-draw">Main draw</a><a href="#alternates">Alternates</a><a href="#withdrawals">Withdrawals</a><a href="#sources">Sources</a></div></nav></header>
<main>{sample_notice}<div class="subhead"><div><span class="phase">{draw_phase}</span><h1>{html.escape(t.name)}</h1><p class="meta">{t.start_date:%d %b}–{t.end_date:%d %b %Y} · {html.escape(t.category)} · {t.surface.value} · {html.escape(t.location.city)}, {html.escape(t.location.country)}</p></div><div class="updated">Entry-list snapshot<br><strong>{entry_list.snapshot_at:%Y-%m-%d %H:%M UTC}</strong></div></div>
<div class="summary"><div class="metric"><strong>{confirmed}/{t.main_draw_size or '—'}</strong><span>confirmed names</span></div><div class="metric"><strong>{qualifier_placeholders}</strong><span>qualifier places pending</span></div><div class="metric"><strong>{open_other}</strong><span>entry route pending</span></div><div class="metric"><strong>{cutoff_text}</strong><span>initial direct cutoff</span></div></div>
<p class="notice"><strong>The draw has not been published.</strong> This page tracks the official entry list before the draw. A listed player is entered, but participation remains subject to withdrawal and ATP rules.</p>
<section id="main-draw"><h2>Main Draw — entry list</h2><p class="explain">Confirmed names plus known unfilled places. Projected seeds remain blank until the applicable seeding ranking is collected.</p><div class="scroll"><table aria-label="Main draw entry list"><thead><tr><th class="num">Proj. seed</th><th>Player / place</th><th>Nation</th><th class="num">Current rank</th><th class="num">Entry rank</th><th>Status</th></tr></thead><tbody>{''.join(main_rows)}</tbody></table></div><div class="legend"><span><b>DA</b> Direct acceptance</span><span><b>Q</b> Qualifier</span><span><b>TBD</b> Entry route not published</span></div></section>
<section id="alternates"><h2>Alternates</h2><div class="scroll"><table aria-label="Alternates"><thead><tr><th class="num">Alt</th><th>Player</th><th>Nation</th><th class="num">Current rank</th><th class="num">Entry rank</th></tr></thead><tbody>{alternate_rows}</tbody></table></div></section>
<section id="withdrawals"><h2>Withdrawals</h2><div class="scroll"><table aria-label="Withdrawals"><thead><tr><th>Date</th><th>Player</th><th>Nation</th><th>Previous status</th><th class="num">Entry rank</th></tr></thead><tbody>{withdrawal_rows}</tbody></table></div></section>
<section id="sources"><h2>Sources and limitations</h2><div class="sources"><ul>{sources}</ul><p>Only facts explicitly supported by the selected source are shown as confirmed. No unofficial alternate names or speculative wild cards are presented as entries.</p></div></section>
</main></body></html>'''


def build(input_path: Path, output_dir: Path) -> Path:
    data = EntryList.model_validate_json(input_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "index.html"
    destination.write_text(build_page(data), encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the static tournament page")
    parser.add_argument("--input", type=Path, default=Path("data/entries/winston-salem-open-2026/current.json"))
    parser.add_argument("--output", type=Path, default=Path("site"))
    args = parser.parse_args()
    print(build(args.input, args.output))


if __name__ == "__main__":
    main()
