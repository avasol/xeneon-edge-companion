"""Acceptance tests: Edge widget v1.3.43, reply order + folded cards.

Problem: after a turn that raised approval cards,
the last thing in the thread was a settled card; the final reply sat ABOVE
the cards (its bubble was created early by a 'status' event and filled in
place on 'done'). Order: the finished reply moves to the bottom of the
thread (still above any card that is pending), and a settled card folds to
one line that expands on click.
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


# A thread whose insert/append MOVE an existing node, as the real DOM does.
_THREAD = (
    "var $msgs = { kids: [], scrollTop: 0, scrollHeight: 999,\n"
    "  _rm: function(d){ var i = this.kids.indexOf(d); if (i >= 0) this.kids.splice(i, 1); },\n"
    "  querySelector: function(sel){ return this.kids.find(function(k){ return k.pending; }) || null; },\n"
    "  insertBefore: function(d, ref){ this._rm(d); this.kids.splice(this.kids.indexOf(ref), 0, d); },\n"
    "  appendChild: function(d){ this._rm(d); this.kids.push(d); } };\n"
)


def _order(setup, call):
    return _vm(_THREAD + _fn("placeInThread"),
               setup + call + "; $msgs.kids.map(function(k){return k.n}).join(',')")


def test_reply_moves_below_settled_cards():
    out = _order("var reply = {n:'reply'}; $msgs.kids = [{n:'you'}, reply, {n:'card1'}, {n:'card2'}];",
                 "placeInThread(reply)")
    assert out == "you,card1,card2,reply"


def test_reply_still_stays_above_a_pending_card():
    out = _order("var reply = {n:'reply'}; $msgs.kids = [{n:'you'}, reply, {n:'card1'}, {n:'card2', pending:true}];",
                 "placeInThread(reply)")
    assert out == "you,card1,reply,card2"


def test_done_reorders_the_streamed_bubble():
    m = re.search(r"\} else if \(evt\.t === 'done'\) \{(.*?)\} else if \(evt\.t === 'error'\)", HTML, re.S)
    assert m, "done branch not found"
    assert "placeInThread(bubbleDiv.closest('.msg'))" in m.group(1)


def test_settle_folds_the_card():
    stub = (
        "function CL(){ this.s = new Set(['msg','approval','pending']); }\n"
        "CL.prototype.remove=function(c){this.s.delete(c)}; CL.prototype.add=function(c){this.s.add(c)};\n"
        "CL.prototype.contains=function(c){return this.s.has(c)};\n"
        "var actions = { innerHTML: 'buttons' };\n"
        "var card = { classList: new CL(), querySelector: function(){ return actions; } };\n"
        "var $msgs = { querySelector: function(sel){ return sel.indexOf('f1') >= 0 && card.classList.contains('pending') ? card : null; } };\n"
        "function escapeHtml(s){ return s; }\n"
    )
    m = re.search(r"(const APPROVAL_OUTCOME_TEXT = \{.*?\};)", HTML, re.S)
    out = _vm(stub + m.group(1) + "\n" + _fn("settleApprovalCard"),
              "settleApprovalCard('f1', 'approved');"
              "[card.classList.contains('pending'), card.classList.contains('folded')].join('|') + '|' + actions.innerHTML")
    assert out.startswith("false|true|") and "approved" in out


def test_folded_card_has_style_and_expands_on_click():
    assert ".msg.approval.folded" in HTML
    assert ".msg.approval.folded.expanded" in HTML
    f = _fn("renderApproval")
    assert "classList.toggle('expanded')" in f
    assert "folded" in f   # only a folded card toggles; a pending one does not


def test_version():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split("."))) >= (1, 3, 43)
    mv = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert mv == v
