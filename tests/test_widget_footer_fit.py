"""1.4.2: the footer's left stats never push the bottom bar out of its 140 px row.

Seen live 2026-10-09: the SETTINGS readout ('tok ✓ · url ✓ · conn ✓ · 3s') wrapped
inside a half-width cell, the stats grew to ~230 px tall, and the whole footer
slid down and right, cutting off SEND and the command column.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _rule(selector):
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", HTML)
    assert m, selector + " rule not found"
    return re.sub(r"\s+", " ", m.group(1))


def test_settings_row_spans_both_columns():
    assert re.search(r'<div class="stat-row stat-build stat-cfg-row">\s*<span>SETTINGS</span>', HTML)
    body = _rule(".stat-row.stat-cfg-row")
    assert re.search(r"grid-column:\s*1\s*/\s*-1", body)


def test_stat_values_never_wrap():
    body = _rule(".stat-row .val")
    assert "white-space: nowrap" in body
    assert "overflow: hidden" in body
    assert "text-overflow: ellipsis" in body
    assert "min-width: 0" in body


def test_stat_grid_cells_can_shrink():
    body = _rule("#stats")
    assert re.search(r"grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)", body)
    row = _rule(".stat-row")
    assert "min-width: 0" in row
    assert "gap: 10px" in row


def test_footer_left_is_clipped_to_its_row():
    body = _rule("#footer-left")
    assert "overflow: hidden" in body
    assert "min-width: 0" in body
    assert "padding: 8px 26px" in body


def test_footer_children_cannot_widen_the_grid():
    assert "min-width: 0" in _rule("#footer-right")


def test_version_1_4_2():
    assert re.search(r"WIDGET_VERSION\s*=\s*['\"]1\.4\.2['\"]", HTML)
    assert json.loads((ROOT / "manifest.json").read_text())["version"] == "1.4.2"
