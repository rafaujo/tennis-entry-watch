from datetime import timedelta
from pathlib import Path

from tennis_entry_watch.collectors.live_tennis import (
    LiveTennisSnapshot,
    parse_rankings,
    parse_schedules,
    write_snapshot_if_changed,
)


def _table(rows: str) -> str:
    return f'<table id="u868"><tbody>{rows}</tbody></table>'


def test_parses_live_ranking_rows_from_direct_player_cells():
    html = _table(
        '<tr><td class="rk">1</td><td></td><td></td><td class="pn">Félix Example</td>'
        '<td>24</td><td class="sm" p="2">CAN</td><td>1,234</td></tr>'
    )
    rows = parse_rankings(html)
    assert rows[0].name == "Félix Example"
    assert rows[0].nation == "CAN"
    assert rows[0].points == 1234
    assert rows[0].rank == 1


def test_parses_schedule_events_without_age_or_national_rank():
    html = _table(
        '<tr><td class="rk">7</td><td></td><td class="pn">Player Name</td>'
        '<td>25</td><td class="sm" p="4">USA</td>'
        '<td class="ctr">Winston Salem</td><td class="ctr sd">Qual. US Open</td></tr>'
    )
    rows = parse_schedules(html)
    assert rows[0].events == ["Winston Salem", "Qual. US Open"]


def test_unchanged_snapshot_does_not_rewrite_retrieval_timestamp(tmp_path):
    source = Path("data/rankings/atp-live-current.json")
    output = tmp_path / "snapshot.json"
    output.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")
    snapshot = LiveTennisSnapshot.model_validate_json(output.read_text(encoding="utf-8"))
    later = snapshot.model_copy(update={"retrieved_at": snapshot.retrieved_at + timedelta(hours=1)})
    assert write_snapshot_if_changed(later, output) is False
    unchanged = LiveTennisSnapshot.model_validate_json(output.read_text(encoding="utf-8"))
    assert unchanged.retrieved_at == snapshot.retrieved_at
