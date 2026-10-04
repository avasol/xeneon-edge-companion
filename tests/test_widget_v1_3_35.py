"""Acceptance tests for widget v1.3.35.

Run: python -m pytest -q tests/   (requires Node.js on PATH)

Covers four fixes:
  1. Late settings injection: iCUE may inject edgeToken after every boot-time
     re-read and fire no event; the widget must keep re-reading while the token
     is missing, and trim pasted whitespace.
  2. Connection probe: the SETTINGS row tests the token against the Tower
     instead of only checking that one is present.
  3. Thinking state: any live stream event re-lights the thinking animation
     if an idle watchdog switched it off mid-turn. The animation is unchanged.
  4. Copy chip: iCUE swallows Ctrl+C, so marked text in the chat or in the
     Status/Diag/Logs panel gets a one-click copy chip.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _fn(name):
    m = re.search(r"((?:async )?function " + re.escape(name) + r"\([^)]*\) \{.*?\n\})", HTML, re.S)
    assert m, name + " not found in index.html"
    return m.group(1)


def _node(script):
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _vm(prelude, body):
    return _node(
        "const { createContext, runInContext } = require('node:vm');\n"
        "const ctx = createContext({});\n"
        "runInContext('var window = globalThis;', ctx);\n"
        f"runInContext({json.dumps(prelude)}, ctx);\n"
        f"console.log(runInContext({json.dumps(body)}, ctx));\n"
    )


def _vm_async(prelude, body):
    """Run `body` (which must set globalThis.__r), then print __r a tick later."""
    return _node(
        "const { createContext, runInContext } = require('node:vm');\n"
        "const ctx = createContext({});\n"
        f"runInContext({json.dumps(prelude)}, ctx);\n"
        f"runInContext({json.dumps(body)}, ctx);\n"
        "setTimeout(() => console.log(runInContext('String(globalThis.__r)', ctx)), 50);\n"
    )


def _config_src():
    return "\n".join(_fn(n) for n in ("getIcueProperty", "getSetting", "readConfig"))


# 1 -- late injection + trimming -------------------------------------------

def test_token_and_url_are_trimmed():
    pre = 'var edgeToken = "  ABC123 \\n"; var towerUrl = " http://x:8080 ";\n' + _config_src()
    assert _vm(pre, "JSON.stringify([readConfig().token, readConfig().url])") == '["ABC123","http://x:8080"]'


def test_whitespace_only_token_is_empty():
    pre = 'var edgeToken = "   ";\n' + _config_src()
    assert _vm(pre, "JSON.stringify(readConfig().token)") == '""'


def test_ensure_config_rereads_while_token_missing():
    pre = "var calls = 0; function reloadConfig(){ calls++; } var CFG = { token: '' };\n" + _fn("ensureConfig")
    assert _vm(pre, "ensureConfig(); ensureConfig(); String(calls)") == "2"


def test_ensure_config_idle_once_token_present():
    pre = "var calls = 0; function reloadConfig(){ calls++; } var CFG = { token: 'abc' };\n" + _fn("ensureConfig")
    assert _vm(pre, "ensureConfig(); String(calls)") == "0"


def test_ensure_config_runs_for_the_widget_lifetime():
    assert re.search(r"setInterval\(\s*ensureConfig\s*,\s*\d{3,5}\s*\)", HTML)


# 2 -- connection probe ----------------------------------------------------

_PROBE = ("var CFG = { token: 't', url: 'http://x/' }; var connState = 'unknown';"
          " function renderCfgDiag(){} function headers(){ return {}; }\n")


def test_verify_connection_classifies_the_door():
    for status, want in ((200, "ok"), (403, "rejected"), (500, "unreachable")):
        ok = "true" if status == 200 else "false"
        pre = _PROBE + f"var fetch = async () => ({{ ok: {ok}, status: {status} }});\n" + _fn("verifyConnection")
        got = _vm_async(pre, "verifyConnection().then(() => { globalThis.__r = connState; });")
        assert got == want, (status, got)


def test_unreachable_when_fetch_throws():
    pre = _PROBE + "var fetch = async () => { throw new Error('net'); };\n" + _fn("verifyConnection")
    assert _vm_async(pre, "verifyConnection().then(() => { globalThis.__r = connState; });") == "unreachable"


def test_settings_row_names_the_connection():
    src = _fn("renderCfgDiag")
    assert "connState" in src and "rejected" in src and "unreachable" in src


def test_probe_runs_on_change_and_at_boot():
    assert "verifyConnection()" in _fn("reloadConfig")
    assert re.search(r"^verifyConnection\(\);$", HTML, re.M)


# 3 -- thinking state ------------------------------------------------------

_MIRROR = (
    "function CL(){ this.s = new Set(); }"
    " CL.prototype.add=function(c){this.s.add(c)}; CL.prototype.remove=function(c){this.s.delete(c)};"
    " CL.prototype.contains=function(c){return this.s.has(c)};\n"
    "var calls = 0; var $mirror = { classList: new CL() };\n"
    "function setThinking(on){ calls++; if(on) $mirror.classList.add('thinking'); else $mirror.classList.remove('thinking'); }\n"
)


def test_reassert_lights_a_dark_mirror():
    out = _vm(_MIRROR + _fn("reassertThinking"),
              "reassertThinking(); String($mirror.classList.contains('thinking')) + ',' + calls")
    assert out == "true,1"


def test_reassert_is_idempotent():
    out = _vm(_MIRROR + _fn("reassertThinking"),
              "$mirror.classList.add('thinking'); reassertThinking(); reassertThinking(); String(calls)")
    assert out == "0"


def _branch(tag):
    m = re.search(r"evt\.t === '" + tag + r"'\) \{(.*?)\n        \} else if", HTML, re.S)
    assert m, tag + " branch not found"
    return m.group(1)


def test_progress_and_token_events_reassert():
    assert "reassertThinking()" in _branch("progress")
    assert "reassertThinking()" in _branch("token")


def test_animation_is_unchanged():
    assert "animation: mirror-breathe 1.4s ease-in-out infinite;" in HTML
    assert "#mirror-wrap.thinking #mirror-ring-outer { animation: spin-slow 32s linear infinite; }" in HTML


def test_diag_reports_reduced_motion():
    src = _fn("collectDiag")
    assert "prefers-reduced-motion: reduce" in src and "reduced motion" in src


# 4 -- copy chip -----------------------------------------------------------

def _sel(where):
    return (
        "function Box(n){ this.n=n; } Box.prototype.contains=function(x){ return !!x && x.box===this.n; };\n"
        "var $msgs = new Box('msgs'); var inspectContent = new Box('inspect');\n"
        f"var node = {{ box: {json.dumps(where)} }};\n"
        "window.getSelection = function(){ return { rangeCount:1, isCollapsed:false,"
        " anchorNode: node, focusNode: node, toString: function(){ return 'copied text'; } }; };\n"
        + _fn("selectionInMessages")
    )


def test_copy_chip_in_chat():
    assert _vm(_sel("msgs"), "String(selectionInMessages() && selectionInMessages().text)") == "copied text"


def test_copy_chip_in_inspect_panel():
    assert _vm(_sel("inspect"), "String(selectionInMessages() && selectionInMessages().text)") == "copied text"


def test_copy_chip_ignores_other_selections():
    assert _vm(_sel("sidebar"), "String(selectionInMessages())") == "null"


def test_copy_chip_is_styled_and_wired():
    assert "#sel-copy {" in HTML
    assert "$selCopy.id = 'sel-copy';" in HTML
    assert "function positionSelCopy()" in HTML


# release hygiene ----------------------------------------------------------

def test_version_and_changelog():
    ver = re.search(r"const WIDGET_VERSION = '([0-9.]+)';", HTML).group(1)
    assert tuple(map(int, ver.split("."))) >= (1, 3, 35)
    assert json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"] == ver
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for v in ("1.3.33", "1.3.34", "1.3.35"):
        assert f"## [{v}]" in log, v


def test_no_private_network_addresses():
    assert not re.search(r"\b10\.0\.\d+\.\d+\b", HTML)
