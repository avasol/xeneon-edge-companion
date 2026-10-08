"""Acceptance tests: Edge widget v1.3.41 turn recovery.

Problem: a long Edge turn finished server-side,
but the SSE stream hung without closing. The widget clock kept ticking, the
mirror went dark, the status sat on "WORKING..." forever, and the reply was
never shown. Reconciliation only ran on stream close or the idle watchdog.

Fix, widget side: the stream's first event names the turn id; every poll
carries edge_turns.done; a widget still waiting on a turn the server has
finished (for longer than a short grace) cancels the hung stream and loads
the reply from history, quietly (no "Tower offline" alarm). Coming back to a
visible panel polls at once.
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


def _vm(prelude, body):
    script = (
        "const { createContext, runInContext } = require('node:vm');\n"
        "const ctx = createContext({});\n"
        f"runInContext({json.dumps(prelude)}, ctx);\n"
        f"console.log(runInContext({json.dumps(body)}, ctx));\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _grace():
    m = re.search(r"const TURN_RECOVERY_GRACE_MS = (\d+);", HTML)
    assert m, "TURN_RECOVERY_GRACE_MS constant missing"
    return int(m.group(1))


def _prelude():
    return f"var TURN_RECOVERY_GRACE_MS = {_grace()};\n" + _fn("shouldRecoverTurn")


def test_grace_is_short_but_not_zero():
    assert 3000 <= _grace() <= 15000


def test_no_turn_or_unknown_id_never_recovers():
    out = _vm(_prelude(),
              "[shouldRecoverTurn(null, {latest: 1, done: [1]}, 1e6),"
              " shouldRecoverTurn({id: null, receivedDone: false, doneSeenAt: 0}, {latest: 1, done: [1]}, 1e6),"
              " shouldRecoverTurn({id: 2, receivedDone: false, doneSeenAt: 0}, {latest: 2, done: [1]}, 1e6),"
              " shouldRecoverTurn({id: 2, receivedDone: false, doneSeenAt: 0}, undefined, 1e6),"
              " shouldRecoverTurn({id: 2, receivedDone: false, doneSeenAt: 0}, {latest: 2}, 1e6)].join(',')")
    assert out == "false,false,false,false,false"


def test_first_sighting_starts_grace_then_recovers_after_it():
    g = _grace()
    out = _vm(_prelude(),
              "var t = {id: 7, receivedDone: false, doneSeenAt: 0};\n"
              "var e = {latest: 7, done: [5, 7]};\n"
              f"var a = shouldRecoverTurn(t, e, 100000);\n"
              f"var b = t.doneSeenAt;\n"
              f"var c = shouldRecoverTurn(t, e, 100000 + {g} - 1);\n"
              f"var d = shouldRecoverTurn(t, e, 100000 + {g});\n"
              "[a, b, c, d].join(',')")
    assert out == "false,100000,false,true"


def test_received_done_never_recovers():
    out = _vm(_prelude(),
              "var t = {id: 7, receivedDone: true, doneSeenAt: 1};\n"
              "String(shouldRecoverTurn(t, {latest: 7, done: [7]}, 1e9))")
    assert out == "false"


def _send():
    return _fn("sendMessage")


def test_turn_event_records_the_id():
    m = re.search(r"evt\.t === 'turn'\) \{(.*?)\n        \} else if", _send(), re.S)
    assert m, "turn branch missing in sendMessage"
    assert "myTurn.id = evt.v" in m.group(1)


def test_send_registers_current_turn_and_recover_cancels_reader():
    s = _send()
    assert "currentTurn = myTurn" in s
    assert re.search(r"myTurn\.recover = \(\) => \{[^}]*recovered = true[^}]*reader\.cancel\(\)", s, re.S)
    assert "myTurn.receivedDone = true" in s
    assert "if (currentTurn === myTurn) currentTurn = null" in s


def test_recovered_close_is_quiet_and_reconciles():
    s = _send()
    m = re.search(r"if \(!receivedDone\) \{\s*if \(recovered\) \{(.*?)\} else \{(.*?)\n    \}", s, re.S)
    assert m, "close-without-done branch must split on recovered"
    quiet, loud = m.group(1), m.group(2)
    assert "reconcileOrFail(" in quiet
    assert "renderError" not in quiet and "TOWER OFFLINE" not in quiet
    assert "setThinking(false)" in quiet and "TOWER ONLINE" in quiet
    assert "renderError" in loud   # the honest failure path is unchanged


def test_poll_asks_whether_to_recover():
    p = _fn("poll")
    assert "shouldRecoverTurn(currentTurn, data.edge_turns, Date.now())" in p
    assert "currentTurn.recover()" in p


def test_visible_again_polls_at_once():
    assert re.search(r"addEventListener\('visibilitychange', \(\) => \{\s*if \(!document\.hidden\) poll\(\);\s*\}\);", HTML)


def test_current_turn_global():
    assert re.search(r"^let currentTurn = null;", HTML, re.M)


def test_version():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split('.'))) >= (1, 3, 41)
    mv = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert tuple(map(int, mv.split('.'))) >= (1, 3, 41)
