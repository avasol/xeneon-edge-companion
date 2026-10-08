"""Edge widget v1.3.42: acknowledged turns + its own trace.

Problem: a long Edge turn finished on the Tower,
but the widget (v1.3.41) showed nothing and sat idle. v1.3.41's recovery lives
in the in-flight turn object, so a respawned webview or a reset turn can never
use it; and the widget left no trace of what it did.

Fix, widget side:
  * after a stream's 'done', the widget acknowledges the turn;
  * every poll, finished turns that no widget acknowledged become due after a
    short grace; a VISIBLE, idle widget then reloads its messages from
    history (the source of truth) and acknowledges them. A hidden webview
    never acts (it must not swallow a reply the real panel never showed);
  * the widget keeps a bounded event log and ships it to /api/edge/trace.
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
    assert m
    return int(m.group(1))


def _prelude():
    return f"var TURN_RECOVERY_GRACE_MS = {_grace()};\n" + _fn("dueUnackedTurns")


# ── dueUnackedTurns: pure ────────────────────────────────────────────────

def test_nothing_due_without_unacked():
    out = _vm(_prelude(),
              "var s = {};\n"
              "[dueUnackedTurns(undefined, s, 1e6, false, null).length,"
              " dueUnackedTurns({done: [1]}, s, 1e6, false, null).length,"
              " dueUnackedTurns({done: [1], unacked: [], epoch: 'e'}, s, 1e6, false, null).length].join(',')")
    assert out == "0,0,0"


def test_first_sighting_starts_grace_then_due():
    g = _grace()
    out = _vm(_prelude(),
              "var s = {}; var t = {done: [4, 5], unacked: [5], epoch: 'ep1'};\n"
              "var a = dueUnackedTurns(t, s, 100000, false, null).length;\n"
              "var first = s['ep1:5'] && s['ep1:5'].first;\n"
              f"var b = dueUnackedTurns(t, s, 100000 + {g} - 1, false, null).length;\n"
              f"var c = dueUnackedTurns(t, s, 100000 + {g}, false, null).join('|');\n"
              "[a, first, b, c].join(',')")
    assert out == "0,100000,0,5"


def test_hidden_webview_never_acts():
    g = _grace()
    out = _vm(_prelude(),
              "var s = {}; var t = {done: [5], unacked: [5], epoch: 'e'};\n"
              "dueUnackedTurns(t, s, 1000, false, null);\n"
              f"String(dueUnackedTurns(t, s, 1000 + {g} * 10, true, null).length)")
    assert out == "0"


def test_inflight_turn_is_left_to_its_own_stream():
    g = _grace()
    out = _vm(_prelude(),
              "var s = {}; var t = {done: [5, 6], unacked: [5, 6], epoch: 'e'};\n"
              "dueUnackedTurns(t, s, 1000, false, 6);\n"
              f"dueUnackedTurns(t, s, 1000 + {g}, false, 6).join('|')")
    assert out == "5"


def test_handled_turn_is_not_due_again():
    g = _grace()
    out = _vm(_prelude(),
              "var s = {}; var t = {done: [5], unacked: [5], epoch: 'e'};\n"
              "dueUnackedTurns(t, s, 1000, false, null);\n"
              "s['e:5'].handled = true;\n"
              f"String(dueUnackedTurns(t, s, 1000 + {g} * 3, false, null).length)")
    assert out == "0"


def test_epoch_separates_restarted_tower_ids():
    g = _grace()
    out = _vm(_prelude(),
              "var s = {};\n"
              "dueUnackedTurns({done: [1], unacked: [1], epoch: 'old'}, s, 1000, false, null);\n"
              "s['old:1'].handled = true;\n"
              "var t = {done: [1], unacked: [1], epoch: 'new'};\n"
              "dueUnackedTurns(t, s, 2000, false, null);\n"
              f"dueUnackedTurns(t, s, 2000 + {g}, false, null).join('|')")
    assert out == "1"


# ── wiring ───────────────────────────────────────────────────────────────

def test_stream_done_acknowledges_the_turn():
    s = _fn("sendMessage")
    m = re.search(r"myTurn\.receivedDone = true;(.{0,400})", s, re.S)
    assert m
    assert "ackTurn(myTurn.id)" in m.group(1)


def test_ack_posts_to_the_tower():
    a = _fn("ackTurn")
    assert "/api/edge/turn/" in a and "/ack" in a and "POST" in a


def test_poll_reloads_history_for_due_turns_when_idle_and_acks():
    p = _fn("poll")
    assert "dueUnackedTurns(data.edge_turns, unackedSeen" in p
    assert "panelVisible()" in p
    assert "!sending" in p
    i_due = p.index("dueUnackedTurns(")
    rest = p[i_due:]
    assert "reloadFromHistory()" in rest and "ackTurn(" in rest
    assert rest.index("reloadFromHistory()") < rest.index("ackTurn(")
    assert ".handled = true" in rest
    # v1.3.44: handled + ack only AFTER a successful reload (see test_edge_widget_reload_safe.py)
    assert rest.index("reloadFromHistory()") < rest.index(".handled = true")


def test_reload_from_history_resets_messages_and_approval_cards():
    r = _fn("reloadFromHistory")
    assert "$msgs.innerHTML = ''" in r
    assert "renderedApprovals.clear()" in r
    assert "/api/edge/history" in r


def test_globals():
    assert re.search(r"^const unackedSeen = \{\};", HTML, re.M)


# ── trace ────────────────────────────────────────────────────────────────

def test_trace_buffer_is_bounded():
    pre = "var traceBuf = []; var TRACE_MAX = 200;\n" + _fn("trace")
    out = _vm(pre, "for (var i = 0; i < 1000; i++) trace('e', {i: i});\n"
                   "[traceBuf.length, traceBuf[0].ev, traceBuf[traceBuf.length-1].i, typeof traceBuf[0].ts].join(',')")
    assert out == "200,e,999,number"
    assert re.search(r"^const TRACE_MAX = \d+;", HTML, re.M)
    assert re.search(r"^const traceBuf = \[\];", HTML, re.M)


def test_trace_flush_posts_boot_version_events():
    f = _fn("flushTrace")
    assert "/api/edge/trace" in f and "POST" in f
    assert "EDGE_BOOT" in f and "WIDGET_VERSION" in f
    assert "setInterval(flushTrace" in HTML


def test_key_moments_are_traced():
    s = _fn("sendMessage")
    for ev in ("'send'", "'turn'", "'done'"):
        assert "trace(" + ev in s, ev
    assert "trace('unacked-due'" in _fn("poll")
    assert "trace('watchdog'" in HTML


def test_version():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split('.'))) >= (1, 3, 42)
    mv = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert tuple(map(int, mv.split('.'))) >= (1, 3, 42)
