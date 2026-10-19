"""Edge widget v1.4.4: overnight socket starvation fix, self-healing reconnect, and live Diag probe.

Root causes fixed in 1.4.4:
  1. EDGE_BOOT was referenced in flushTrace() without being defined, throwing a
     ReferenceError every 30s and preventing trace flushes.
  2. apiFetch() and verifyConnection() had no AbortController timeout, and
     poll() / flushTrace() had no single-flight guard. When the Tower host stops
     overnight (blackholing TCP SYN), setInterval(poll, 3000) stacked thousands
     of overlapping pending fetches until QtWebEngine wedged the origin queue.
  3. loadHistory() set loaded = true even inside catch(e), and poll() never
     updated connState or retried loadHistory() upon recovery — leaving a widget
     that booted while offline stuck on 'conn ✗' and an empty thread even after
     the Tower came back online. Also reloadConfig() did not call loadHistory()
     when towerUrl changed after edgeToken was already present.
  4. collectDiag() / openDiag() did not report live connection state (connState,
     pollFailures, lastConnError) or re-probe the Tower when Diag was opened.
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


def _vm_async(prelude, body, wait_ms=60):
    return _node(
        "const { createContext, runInContext } = require('node:vm');\n"
        "const ctx = createContext({ console, setTimeout, clearTimeout, Date, Math });\n"
        "runInContext('var window = globalThis;', ctx);\n"
        f"runInContext({json.dumps(prelude)}, ctx);\n"
        f"runInContext({json.dumps(body)}, ctx);\n"
        f"setTimeout(() => console.log(runInContext('JSON.stringify(globalThis.__r)', ctx)), {wait_ms});\n"
    )


def test_edge_boot_is_defined_and_in_headers():
    assert re.search(r"^const EDGE_BOOT = ", HTML, re.M), "EDGE_BOOT must be defined at top level"
    hdr = _fn("headers")
    assert "'X-Edge-Boot': EDGE_BOOT" in hdr


def test_api_fetch_has_abort_timeout():
    src = _fn("apiFetch")
    assert "AbortController" in src
    assert "clearTimeout" in src


def test_poll_is_single_flight_and_heals_conn_state_and_history():
    poll_src = _fn("poll")
    assert "pollInFlight" in poll_src, "poll() must guard against overlapping in-flight requests"
    assert "finally" in poll_src

    pre = (
        "var pollInFlight = false, pollFailures = 2, connState = 'unreachable', loaded = false;\n"
        "var diagRendered = 0, historyLoads = 0, fetchCalls = 0;\n"
        "var sending = false, currentTurn = null, unackedSeen = {}, lastMsgId = null;\n"
        "var $dot = { className: 'offline' }, $stTxt = { textContent: 'TOWER OFFLINE' };\n"
        "function renderCfgDiag(){ diagRendered++; }\n"
        "function loadHistory(){ historyLoads++; loaded = true; return Promise.resolve(); }\n"
        "function setStatus(s, t){ $dot.className = s; $stTxt.textContent = t; }\n"
        "function syncApprovals(){}\n"
        "function shouldRecoverTurn(){ return false; }\n"
        "function dueUnackedTurns(){ return []; }\n"
        "function panelVisible(){ return true; }\n"
        "var resolveFetch;\n"
        "function apiFetch(path){\n"
        "  fetchCalls++;\n"
        "  return new Promise(r => { resolveFetch = r; });\n"
        "}\n"
        + _fn("poll")
    )
    body = (
        "var p1 = poll();\n"
        "var p2 = poll();\n"  # second call while p1 is in flight must be a no-op
        "var callsDuringFlight = fetchCalls;\n"
        "resolveFetch({});\n"
        "p1.then(() => {\n"
        "  globalThis.__r = { callsDuringFlight, pollInFlight, connState, diagRendered, historyLoads, pollFailures };\n"
        "});\n"
    )
    res = json.loads(_vm_async(pre, body))
    assert res["callsDuringFlight"] == 1
    assert res["pollInFlight"] is False
    assert res["connState"] == "ok"
    assert res["diagRendered"] >= 1
    assert res["historyLoads"] == 1
    assert res["pollFailures"] == 0


def test_load_history_stays_unloaded_on_failure():
    src = _fn("loadHistory")
    pre = (
        "var loaded = false, statusState = '', lastConnError = '';\n"
        "var document = { getElementById(){ return null; } };\n"
        "var WIDGET_VERSION = '1.4.4';\n"
        "function setStatus(s){ statusState = s; }\n"
        "async function apiFetch(){ throw new Error('timeout'); }\n"
        + src
    )
    res = json.loads(_vm_async(
        pre,
        "loadHistory().then(() => { globalThis.__r = { loaded, statusState, lastConnError }; });"
    ))
    assert res["loaded"] is False, "loadHistory() must leave loaded=false on error so poll() retries"
    assert res["statusState"] == "offline"
    assert "timeout" in res["lastConnError"]


def test_reload_config_loads_history_when_url_changes_with_existing_token():
    src = _fn("reloadConfig")
    pre = (
        "var CFG = { url: 'http://localhost:8080', token: 'tok123', poll: 3 };\n"
        "function readConfig(){ return { url: 'http://10.0.129.49:8080', token: 'tok123', poll: 3 }; }\n"
        "var restarted = 0, verified = 0, historyLoaded = 0;\n"
        "function renderCfgDiag(){}\n"
        "function restartPolling(){ restarted++; }\n"
        "function verifyConnection(){ verified++; }\n"
        "function loadHistory(){ historyLoaded++; }\n"
        + src
    )
    res = json.loads(_vm_async(
        pre,
        "reloadConfig(); globalThis.__r = { restarted, verified, historyLoaded, url: CFG.url };"
    ))
    assert res["restarted"] == 1
    assert res["verified"] == 1
    assert res["historyLoaded"] == 1


def test_diag_includes_live_connection_state_and_reprobes():
    diag_src = _fn("collectDiag")
    assert "connState" in diag_src
    assert "pollFailures" in diag_src
    assert "lastConnError" in diag_src
    open_src = _fn("openDiag")
    assert "verifyConnection()" in open_src


def test_version_1_4_4():
    ver = re.search(r"const WIDGET_VERSION = '([0-9.]+)';", HTML).group(1)
    assert tuple(map(int, ver.split("."))) >= (1, 4, 4)
    assert json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"] == ver
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.4.4]" in log
