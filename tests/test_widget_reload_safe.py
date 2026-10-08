"""Edge widget v1.3.44: a recovery reload never blanks the panel.

Problem (v1.3.43): a turn's stream died with a network error;
the poll saw the finished turn unacknowledged and called reloadFromHistory(),
which CLEARED the messages first and then fetched history. The fetch failed in
the same network blip (loadHistory swallows errors), so the panel stayed
empty, and the poll acknowledged the turn anyway, so nothing ever retried.

Contract:
  * reloadFromHistory() fetches /api/edge/history FIRST; only when the fetch
    succeeds does it clear $msgs + renderedApprovals and render the messages;
    it returns true. On any failure it leaves the panel untouched and returns
    false.
  * poll(): marks due turns handled and acknowledges them ONLY when the reload
    returned true; otherwise it traces 'reload-failed' and the turns stay due,
    so the next poll retries.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _fn(name):
    m = re.search(r"((?:async )?function " + re.escape(name) + r"\([^)]*\) \{.*?\n\})", HTML, re.S)
    assert m, name + " not found"
    return m.group(1)


def _run(fetch_impl):
    prelude = (
        "var $msgs = { innerHTML: 'OLD' };\n"
        "var rendered = [];\n"
        "var renderedApprovals = { cleared: false, clear() { this.cleared = true; } };\n"
        "function renderMsg(role, text, time) { rendered.push(role + ':' + text); }\n"
        "function setStatus() {}\n"
        "var document = { getElementById() { return null; } };\n"
        "var loaded = false;\n"
        f"async function apiFetch(path) {{ {fetch_impl} }}\n"
        + _fn("reloadFromHistory") + "\n"
    )
    script = (
        "const { createContext, runInContext } = require('node:vm');\n"
        "const ctx = createContext({ console });\n"
        f"runInContext({json.dumps(prelude)}, ctx);\n"
        "runInContext('reloadFromHistory()', ctx).then(r => {\n"
        "  console.log(JSON.stringify({ r: r, msgs: ctx.$msgs.innerHTML, rendered: ctx.rendered,"
        " cleared: ctx.renderedApprovals.cleared }));\n"
        "});\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_failed_fetch_leaves_panel_untouched_and_returns_false():
    res = _run("throw new Error('network error');")
    assert res["r"] is False
    assert res["msgs"] == "OLD"
    assert res["rendered"] == []
    assert res["cleared"] is False


def test_malformed_response_leaves_panel_untouched():
    res = _run("return { error: 'Forbidden' };")
    assert res["r"] is False
    assert res["msgs"] == "OLD"


def test_successful_fetch_replaces_panel_and_returns_true():
    res = _run("return { messages: [{ role: 'usr', text: 'hi', time: '' }, { role: 'gal', text: 'reply', time: '' }] };")
    assert res["r"] is True
    assert res["msgs"] == ""
    assert res["cleared"] is True
    assert res["rendered"] == ["usr:hi", "gal:reply"]


def test_empty_history_is_a_success():
    res = _run("return { messages: [] };")
    assert res["r"] is True


def test_poll_acks_only_after_successful_reload():
    p = _fn("poll")
    i = p.index("dueUnackedTurns(")
    rest = p[i:]
    m = re.search(r"const (\w+) = await reloadFromHistory\(\);", rest)
    assert m, "poll must keep the reload result"
    ok = m.group(1)
    after = rest[m.end():]
    assert re.search(r"if \(" + ok + r"\)", after)
    assert after.index(".handled = true") > 0
    assert after.index("ackTurn(") > 0
    assert "trace('reload-failed'" in after
    # handled must not be set before the reload any more
    before = rest[:m.start()]
    assert ".handled = true" not in before


def test_version_bumped():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split('.'))) >= (1, 3, 44)
    man = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert man["version"] == v
