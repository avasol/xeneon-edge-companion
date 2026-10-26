"""Edge widget v1.4.6: STILL WATER restored -- an idle widget writes nothing.

The flicker came back in the 1.4.x line. STILL WATER (2026-09-06) settled that the
widget must be still when idle: iCUE streams this webview to the Edge over a shared
GPU, so every repaint competes with the other monitors and shows up as flicker.

Two idle writers had crept back in:
  1. renderCfgDiag() runs every 2 s (ensureConfig -> reloadConfig) and rewrote the
     SETTINGS row's text, colour and title each time, even when nothing changed.
  2. tickClock() ran every second, rewriting the glowing clock and the session
     counter once a second, forever.

Rules guarded here:
  - renderCfgDiag writes to the DOM only when its output changes.
  - The clock shows HH:MM and the session counter changes at most once a minute;
    no timer drives the clock faster than once a minute (a single alignment
    setTimeout to the next minute boundary is allowed).
  - Every infinite CSS animation is gated on a state class, so nothing loops idle.
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
        "const ctx = createContext({ console, Math, JSON });\n"
        "runInContext('var window = globalThis;', ctx);\n"
        f"runInContext({json.dumps(prelude)}, ctx);\n"
        f"runInContext({json.dumps(body)}, ctx);\n"
        "console.log(runInContext('JSON.stringify(globalThis.__r)', ctx));\n"
    )


# A fake element that counts every write to textContent, title and style.color.
_FAKE_EL = (
    "function FakeEl(){ this.writes = 0; this._t=''; this._title=''; var self=this;"
    " this.style = {}; var c='';"
    " Object.defineProperty(this.style,'color',{get(){return c;},set(v){c=v; self.writes++;}}); }\n"
    "Object.defineProperty(FakeEl.prototype,'textContent',{get(){return this._t;},set(v){this._t=String(v); this.writes++;}});\n"
    "Object.defineProperty(FakeEl.prototype,'title',{get(){return this._title;},set(v){this._title=String(v); this.writes++;}});\n"
)


# 1 -- the SETTINGS row ----------------------------------------------------

def _cfg_prelude():
    return (
        _FAKE_EL
        + "var cfgEl = new FakeEl();\n"
        "var document = { getElementById: function(id){ return id === 'stat-cfg' ? cfgEl : null; } };\n"
        "var CFG = { token: 't', url: 'http://x', poll: 3 };\n"
        "var connState = 'ok';\n"
        + _fn("renderCfgDiag")
    )


def test_settings_row_rewrites_nothing_when_unchanged():
    body = (
        "renderCfgDiag(); var first = cfgEl.writes;"
        " renderCfgDiag(); renderCfgDiag(); renderCfgDiag();"
        " globalThis.__r = { first: first, extra: cfgEl.writes - first, text: cfgEl.textContent };"
    )
    r = json.loads(_vm(_cfg_prelude(), body))
    assert r["first"] > 0, "the first render must write the row"
    assert "conn" in r["text"]
    assert r["extra"] == 0, f"idle re-renders wrote to the DOM {r['extra']} times; must be 0"


def test_settings_row_still_updates_when_state_changes():
    body = (
        "renderCfgDiag(); var before = cfgEl.writes;"
        " connState = 'unreachable'; renderCfgDiag();"
        " globalThis.__r = { changed: cfgEl.writes > before, text: cfgEl.textContent,"
        " color: cfgEl.style.color };"
    )
    r = json.loads(_vm(_cfg_prelude(), body))
    assert r["changed"]
    assert "conn \u2717" in r["text"]
    assert r["color"], "a broken connection must still colour the row"


# 2 -- the clock -----------------------------------------------------------

def _clock_section():
    start = HTML.index("/* ── Clock ── */")
    end = HTML.index("function setStatus", start)
    return HTML[start:end]


def _clock_prelude(t0_iso):
    return (
        _FAKE_EL
        + "var __now = Date.parse(" + json.dumps(t0_iso) + ");\n"
        "var RealDate = Date;\n"
        "function FakeDate(a){ return a === undefined ? new RealDate(__now) : new RealDate(a); }\n"
        "FakeDate.now = function(){ return __now; }; FakeDate.parse = RealDate.parse;\n"
        "var Date = FakeDate;\n"
        "var timers = [];\n"
        "function setInterval(fn, ms){ timers.push({kind:'interval', ms: ms}); return timers.length; }\n"
        "function setTimeout(fn, ms){ timers.push({kind:'timeout', ms: ms}); return timers.length; }\n"
        "function clearTimeout(){} function clearInterval(){}\n"
        "var $time = new FakeEl(); var $statSess = new FakeEl();\n"
        "var sessionStart = __now;\n"
    )


def test_clock_has_no_sub_minute_interval():
    sec = _clock_section()
    assert "function tickClock" in sec
    pre = _clock_prelude("2026-10-25T20:00:05") + sec
    r = json.loads(_vm(pre, "globalThis.__r = timers;"))
    intervals = [t["ms"] for t in r if t["kind"] == "interval"]
    assert intervals, "the clock must still be driven by a timer"
    assert all(ms >= 60000 for ms in intervals), f"clock interval(s) {intervals} ms repaint faster than once a minute"
    assert not re.search(r"setInterval\(\s*tickClock\s*,\s*1000\s*\)", HTML)


def test_clock_and_session_write_at_most_once_a_minute():
    sec = _clock_section()
    pre = _clock_prelude("2026-10-25T20:00:05") + sec
    body = (
        "var t0 = $time.writes, s0 = $statSess.writes, txt0 = $time.textContent;"
        " for (var i = 1; i <= 50; i++) { __now += 1000; tickClock(); }"  # 20:00:55
        " var t1 = $time.writes, s1 = $statSess.writes;"
        " __now += 10000; tickClock();"  # 20:01:05
        " globalThis.__r = { txt0: txt0, sameMinuteTime: t1 - t0, sameMinuteSess: s1 - s0,"
        " nextMinuteTime: $time.writes - t1, txt1: $time.textContent };"
    )
    r = json.loads(_vm(pre, body))
    assert re.fullmatch(r"\d\d:\d\d", r["txt0"]), f"clock must read HH:MM, got {r['txt0']!r}"
    assert r["sameMinuteTime"] == 0, "the clock repainted within the same minute"
    assert r["sameMinuteSess"] == 0, "the session counter repainted within the same minute"
    assert r["nextMinuteTime"] == 1, "the clock must update once when the minute turns"
    assert r["txt1"] != r["txt0"]


# 3 -- no idle animation ---------------------------------------------------

_STATE_CLASSES = (".thinking", ".active", ".sending", ".visible", ".streaming-bubble")


def _css():
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", HTML, re.S))


def test_every_infinite_animation_is_gated_on_a_state_class():
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    offenders = []
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        for m in re.finditer(r"animation\s*:([^;]*)", decl):
            if "infinite" not in m.group(1):
                continue
            for one in sel.split(","):
                one = one.strip()
                if not any(c in one for c in _STATE_CLASSES):
                    offenders.append(one)
    assert not offenders, f"infinite animations with no state gate (loop while idle): {offenders}"


# 4 -- version -------------------------------------------------------------

def test_version_is_1_4_6_everywhere():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split("."))) >= (1, 4, 6)
    assert json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"] == v
    assert "## [1.4.6]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


# 2b -- the clock stays on the minute (review of drone e3234b0e6989) --------
# A 60 s interval started at load drifts: loaded at 20:00:05 it fires at
# 20:01:05, 20:02:05 ... so after the first boundary the clock shows the old
# minute for up to 59 s. The repaint cadence must be aligned to the minute edge.

def _clock_sim_prelude(t0_iso):
    return (
        _FAKE_EL
        + "var __now = Date.parse(" + json.dumps(t0_iso) + ");\n"
        "var RealDate = Date;\n"
        "function FakeDate(a){ return a === undefined ? new RealDate(__now) : new RealDate(a); }\n"
        "FakeDate.now = function(){ return __now; }; FakeDate.parse = RealDate.parse;\n"
        "var Date = FakeDate;\n"
        "var timers = {}, nextId = 1;\n"
        "function setInterval(fn, ms){ var id = nextId++; timers[id] = {fn: fn, ms: ms, at: __now + ms, rep: true}; return id; }\n"
        "function setTimeout(fn, ms){ var id = nextId++; timers[id] = {fn: fn, ms: ms, at: __now + ms, rep: false}; return id; }\n"
        "function clearTimeout(id){ delete timers[id]; } function clearInterval(id){ delete timers[id]; }\n"
        "function advanceTo(t){ for(;;){ var best = null, bid = null;"
        " for (var k in timers){ if (timers[k].at <= t && (best === null || timers[k].at < best.at)) { best = timers[k]; bid = k; } }"
        " if (best === null) break; __now = best.at;"
        " if (best.rep) best.at += best.ms; else delete timers[bid]; best.fn(); }"
        " __now = t; }\n"
        "var $time = new FakeEl(); var $statSess = new FakeEl();\n"
        "var sessionStart = __now;\n"
    )


def test_clock_shows_the_current_minute_within_a_second_of_each_boundary():
    sec = _clock_section()
    pre = _clock_sim_prelude("2026-10-25T20:00:05") + sec
    body = (
        "var seen = [];"
        " for (var m = 1; m <= 4; m++) {"
        "   var edge = Date.parse('2026-10-25T20:00:00') + m * 60000;"
        "   advanceTo(edge + 1000);"
        "   seen.push([new RealDate(__now).toTimeString().slice(0,5), $time.textContent]);"
        " }"
        " globalThis.__r = seen;"
    )
    r = json.loads(_vm(pre, body))
    for want, got in r:
        assert got == want, f"clock reads {got!r} one second after the {want} boundary"
