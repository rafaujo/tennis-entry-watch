import argparse
import html
import json
from pathlib import Path

from tennis_entry_watch.models import EntryList, EntryStatus


STATUS_LABELS = {
    EntryStatus.DA: "Direct acceptance", EntryStatus.PR: "Protected ranking",
    EntryStatus.WC: "Wild card", EntryStatus.Q: "Qualifier",
    EntryStatus.LL: "Lucky loser", EntryStatus.SE: "Special exempt",
    EntryStatus.ALT: "Alternate", EntryStatus.OUT: "Withdrawn",
}


def build_page(entry_list: EntryList) -> str:
    t = entry_list.tournament
    rows = []
    ordered = sorted(entry_list.entries, key=lambda e: (
        e.status == EntryStatus.OUT, e.status == EntryStatus.ALT,
        e.alternate_position or 9999, e.entry_rank or 9999, e.player.name,
    ))
    for entry in ordered:
        alt = str(entry.alternate_position) if entry.alternate_position else "—"
        rank = str(entry.entry_rank) if entry.entry_rank else "—"
        current = str(entry.current_rank) if entry.current_rank else "—"
        rows.append(
            f'<tr><td><span class="status status-{entry.status.value.lower()}">{entry.status.value}</span></td>'
            f'<td>{html.escape(entry.player.name)}</td><td>{html.escape(entry.player.nationality or "—")}</td>'
            f'<td>{rank}</td><td>{current}</td><td>{alt}</td>'
            f'<td>{html.escape(STATUS_LABELS[entry.status])}</td></tr>'
        )
    source_urls = sorted({entry.source.url for entry in entry_list.entries})
    sources = "".join(f'<li><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></li>' for url in source_urls)
    sample_notice = ""
    if t.tournament_id == "sample-open-2026":
        sample_notice = '<p class="note"><strong>Sample data:</strong> This fictional tournament demonstrates the MVP and is not an actual ATP entry list.</p>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t.name)} | Tennis Entry Watch</title>
<style>
:root{{--ink:#17212b;--muted:#65727f;--line:#d9e0e6;--paper:#fff;--accent:#176b4d}}
*{{box-sizing:border-box}}body{{margin:0;background:#f5f7f8;color:var(--ink);font:15px/1.45 system-ui,sans-serif}}
header,main{{max-width:1080px;margin:auto}}header{{padding:28px 20px 14px}}header a{{color:var(--accent);font-weight:750;text-decoration:none}}
main{{background:var(--paper);padding:22px;margin-bottom:40px;border:1px solid var(--line)}}h1{{margin:.15em 0;font-size:2rem}}.meta{{color:var(--muted);margin-bottom:24px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
.status{{display:inline-block;min-width:42px;text-align:center;padding:2px 7px;border-radius:3px;background:#e7edf1;font-size:.76rem;font-weight:800}}.status-alt{{background:#fff0c2}}.status-out{{background:#f8d7da;color:#842029}}
.note{{border-left:3px solid var(--accent);padding:8px 12px;background:#eef7f3}}@media(max-width:700px){{main{{border-width:1px 0;padding:14px}}.scroll{{overflow-x:auto}}th,td{{white-space:nowrap}}}}
</style></head><body><header><a href="index.html">TENNIS ENTRY WATCH</a></header><main>
{sample_notice}
<h1>{html.escape(t.name)}</h1><p class="meta">{t.start_date:%B %d, %Y} · {html.escape(t.category)} · {t.surface.value} · {html.escape(t.location.city)}, {html.escape(t.location.country)}<br>Snapshot: {entry_list.snapshot_at.isoformat()}</p>
<h2>Entries</h2><div class="scroll"><table><thead><tr><th>Status</th><th>Player</th><th>Nation</th><th>Entry rank</th><th>Current rank</th><th>Alt</th><th>Meaning</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Source information</h2><p>Every entry retains its source and retrieval time.</p><ul>{sources}</ul>
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
