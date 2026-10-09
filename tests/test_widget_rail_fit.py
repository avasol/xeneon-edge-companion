"""1.4.3: the COMMANDS rail always fits its row, whatever fonts iCUE has.

Seen live 2026-10-09 on the Xeneon Edge: the rail started ~54 px down (aligned to
the chat header) and taller-than-expected glyphs pushed DIAG below the footer.
The buttons now share the rail's height instead of each taking a fixed size.
Also: stat labels never wrap ('LAST REPLY' broke onto two lines).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _rule(selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", HTML)
    assert m, selector + " rule not found"
    return re.sub(r"\s+", " ", m.group(1))


def test_rail_starts_near_the_top():
    body = _rule("#right-rail")
    assert "padding: 14px 14px 12px 14px" in body
    assert "header-h" not in body
    assert "gap: 8px" in body


def test_buttons_share_the_rail_height():
    body = _rule(".special-cmd-btn")
    assert "flex: 1 1 0" in body
    assert "min-height: 0" in body
    assert "justify-content: center" in body
    assert "padding: 6px 10px" in body
    assert "overflow: hidden" in body


def test_icons_are_bounded():
    body = _rule(".special-cmd-btn .cmd-icon")
    assert "font-size: 24px" in body
    assert "line-height: 1" in body


def test_title_never_shrinks():
    assert "flex-shrink: 0" in _rule("#right-rail-title")


def test_stat_labels_never_wrap():
    body = _rule(".stat-row > span:first-child")
    assert "white-space: nowrap" in body
    assert "flex-shrink: 0" in body


def test_version_1_4_3():
    assert re.search(r"WIDGET_VERSION\s*=\s*['\"]1\.4\.3['\"]", HTML)
    assert json.loads((ROOT / "manifest.json").read_text())["version"] == "1.4.3"
