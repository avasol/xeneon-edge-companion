"""1.4.1: a setting changed in iCUE after the token arrived must still reach the widget.

iCUE can update a property's global without firing onDataUpdated. The 1.4.0 hedge
re-read settings only while the token was missing, so a Tower URL edited later
stayed at the default forever (seen live 2026-10-09: diag showed a 23-char
towerUrl delivered while the widget still used http://localhost:8080).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _fn(name):
    m = re.search(r"function " + name + r"\s*\([^)]*\)\s*\{", HTML)
    assert m, name + " not found"
    i, depth = m.end(), 1
    while depth:
        depth += {"{": 1, "}": -1}.get(HTML[i], 0)
        i += 1
    return HTML[m.end():i - 1]


def test_ensure_config_rereads_always():
    body = _fn("ensureConfig")
    assert "reloadConfig()" in body
    assert "CFG.token" not in body, "the re-read must not stop once a token is present"


def test_ensure_config_still_scheduled():
    assert re.search(r"setInterval\(\s*ensureConfig\s*,\s*\d+\s*\)", HTML)


def test_diag_reports_fresh_config():
    body = _fn("collectDiag")
    first_cfg = body.find("CFG.url")
    reload_at = body.find("reloadConfig()")
    assert reload_at != -1 and reload_at < first_cfg, "diag must re-read settings before printing them"


def test_version_at_least_1_4_1():
    m = re.search(r"WIDGET_VERSION\s*=\s*['\"](\d+)\.(\d+)\.(\d+)['\"]", HTML)
    assert m and tuple(map(int, m.groups())) >= (1, 4, 1)
    v = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert tuple(map(int, v.split("."))) >= (1, 4, 1)
