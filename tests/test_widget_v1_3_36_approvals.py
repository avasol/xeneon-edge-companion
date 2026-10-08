"""Acceptance tests: approval cards (planner-written, protected).

A pending approval card is always the last thing in the thread; replies, dead drops and
knocks render above it. Opening a card closes any overlay. Servers MAY serve pending
approvals on every poll (non-destructive) and accept a seen-receipt from a visible panel;
the widget renders each card once, acks once, and settles closed cards with an honest
outcome (a timeout is never called "denied").
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _fn(name):
    m = re.search(r"(function " + re.escape(name) + r"\([^)]*\) \{.*?\n\})", HTML, re.S)
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


_THREAD = (
    "var $msgs = { kids: [], scrollTop: 0, scrollHeight: 999,\n"
    "  querySelector: function(sel){ return this.kids.find(function(k){ return k.pending; }) || null; },\n"
    "  insertBefore: function(d, ref){ this.kids.splice(this.kids.indexOf(ref), 0, d); },\n"
    "  appendChild: function(d){ this.kids.push(d); } };\n"
)


# ── the pinned card ──────────────────────────────────────────────────────

def test_place_in_thread_lands_above_a_pending_card():
    out = _vm(_THREAD + _fn("placeInThread"),
              "$msgs.kids = [{n:'old'}, {n:'card', pending:true}];"
              "placeInThread({n:'knock'}); placeInThread({n:'reply'});"
              "$msgs.kids.map(function(k){return k.n}).join(',') + '|' + $msgs.scrollTop")
    assert out == "old,knock,reply,card|999"


def test_place_in_thread_appends_when_nothing_pending():
    out = _vm(_THREAD + _fn("placeInThread"),
              "$msgs.kids = [{n:'a'}]; placeInThread({n:'b'});"
              "$msgs.kids.map(function(k){return k.n}).join(',')")
    assert out == "a,b"


def test_place_in_thread_looks_for_the_pending_card():
    assert ".msg.approval.pending" in _fn("placeInThread")


def test_every_renderer_goes_through_place_in_thread():
    # messages (incl. dead drops / knocks via poll), errors, the streaming bubble
    assert "placeInThread(div)" in _fn("renderMsg")
    assert "placeInThread(div)" in _fn("renderError")
    assert "placeInThread(wrap)" in HTML
    # only placeInThread and renderApproval may touch the thread directly
    assert HTML.count("$msgs.appendChild(") == 2
    assert HTML.count("$msgs.insertBefore(") == 1


def test_approval_card_always_goes_to_the_bottom_and_is_marked_pending():
    f = _fn("renderApproval")
    assert "msg approval pending" in f
    assert "data-approval-id" in f or "dataset.approvalId" in f
    assert "$msgs.appendChild(div)" in f
    assert "streaming-bubble" not in f          # no more inserting above the stream


def test_approval_card_is_never_hidden_behind_an_open_panel():
    assert "closeOverlaysForApproval()" in _fn("renderApproval")
    f = _fn("closeOverlaysForApproval")
    for close in ("closeInspect", "closeMediaPanel", "closeLinkSheet"):
        assert close in f


# ── the non-destructive registry + the receipt ───────────────────────────

_SYNC = (
    "var rendered = []; var posts = []; var settled = [];\n"
    "var document = { hidden: false };\n"
    "var renderedApprovals = new Set(); var ackedApprovals = new Set();\n"
    "function renderApproval(id, cmd){ rendered.push(id); }\n"
    "function settleApprovalCard(id, o){ settled.push(id + ':' + o); }\n"
    "function apiFetch(url, opts){ posts.push(url + ' ' + (opts && opts.method)); return Promise.resolve({}); }\n"
)


def test_sync_renders_each_card_once_and_acks_once():
    out = _vm(_SYNC + _fn("panelVisible") + _fn("syncApprovals"),
              "var p=[{id:'ab12', command:'x'}]; syncApprovals(p, []); syncApprovals(p, []);"
              "rendered.join(',') + '|' + posts.join(',')")
    assert out == "ab12|/api/edge/approval/ab12/seen POST"


def test_hidden_or_preview_panel_does_not_ack():
    out = _vm(_SYNC + _fn("panelVisible") + _fn("syncApprovals"),
              "document.hidden = true; syncApprovals([{id:'c1', command:'x'}], []);"
              "var a = posts.length; document.hidden = false;"
              "var iCUE = { isPreview: true }; this.iCUE = iCUE; syncApprovals([{id:'c1', command:'x'}], []);"
              "var b = posts.length; this.iCUE = { isPreview: false }; syncApprovals([{id:'c1', command:'x'}], []);"
              "a + ',' + b + ',' + posts.length + ',' + rendered.length")
    assert out == "0,0,1,1"


def test_sync_settles_closed_cards():
    out = _vm(_SYNC + _fn("panelVisible") + _fn("syncApprovals"),
              "syncApprovals([], [{id:'d1', outcome:'timed_out'}]); settled.join(',')")
    assert out == "d1:timed_out"


def test_timeout_is_never_called_denied():
    m = re.search(r"const APPROVAL_OUTCOME_TEXT = \{(.*?)\};", HTML, re.S)
    assert m, "APPROVAL_OUTCOME_TEXT not found"
    table = m.group(1)
    t = re.search(r"timed_out\s*:\s*'([^']*)'", table).group(1)
    assert "timed out" in t and "nothing ran" in t and "denied" not in t.lower()
    assert "answered_elsewhere" in table
    assert "discord" not in table.lower()


def test_settle_unpins_the_card():
    stub = (
        "function CL(){ this.s = new Set(['msg','approval','pending']); }\n"
        "CL.prototype.remove=function(c){this.s.delete(c)}; CL.prototype.add=function(c){this.s.add(c)}; CL.prototype.contains=function(c){return this.s.has(c)};\n"
        "var actions = { innerHTML: 'buttons' };\n"
        "var card = { classList: new CL(), querySelector: function(){ return actions; } };\n"
        "var $msgs = { querySelector: function(sel){ return sel.indexOf('e5') >= 0 && card.classList.contains('pending') ? card : null; } };\n"
        "function escapeHtml(s){ return s; }\n"
    )
    m = re.search(r"(const APPROVAL_OUTCOME_TEXT = \{.*?\};)", HTML, re.S)
    out = _vm(stub + m.group(1) + "\n" + _fn("settleApprovalCard"),
              "settleApprovalCard('e5', 'timed_out');"
              "String(card.classList.contains('pending')) + '|' + actions.innerHTML")
    assert out.startswith("false|") and "timed out" in out


def test_poll_handles_approvals_and_a_message_in_one_response():
    f = _fn("poll")
    assert "syncApprovals(data.approvals" in f
    assert "} else if (data && data.message)" not in f   # both, not either/or


def test_a_click_unpins_through_settle():
    assert "settleApprovalCard(" in _fn("resolveApproval")


def test_version_floor():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split("."))) >= (1, 3, 36)
    mv = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert tuple(map(int, mv.split("."))) >= (1, 3, 36)


def test_changelog_names_the_release():
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.3.36]" in log


def test_protocol_documents_the_optional_registry():
    doc = (ROOT / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "approvals" in doc and "/seen" in doc and "approvals_closed" in doc
