"""THE PILLS on the Edge widget — aedelgard-body docs/SPEC_pills.md P5.

The fixture is a verbatim copy of aedelgard-body tests/fixtures/pills_cases.json:
one grammar, every surface.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CASES = json.loads((ROOT / "tests" / "fixtures" / "pills_cases.json").read_text(encoding="utf-8"))


def _block():
    m = re.search(r"/\* pills:begin \*/(.*?)/\* pills:end \*/", HTML, re.S)
    assert m, "pills:begin/end markers not found"
    assert "function parsePills(" in m.group(1)
    return m.group(1)


def _node(src):
    out = subprocess.run(["node", "-e", src], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _fn(name):
    m = re.search(r"(function " + re.escape(name) + r"\([^)]*\) \{.*?\n\})", HTML, re.S)
    assert m, name + " not found"
    return m.group(1)


def test_parse_pills_matches_fixture():
    script = (_block() + "\nconst cases = " + json.dumps(CASES) + ";\n"
              "console.log(JSON.stringify(cases.map(c => parsePills(c.text))));\n")
    got = json.loads(_node(script))
    for case, res in zip(CASES, got):
        assert res["text"] == case["clean"], case["name"]
        assert res["options"] == case["options"], case["name"]


def test_parse_pills_tolerates_non_string():
    got = json.loads(_node(_block() + "\nconsole.log(JSON.stringify(parsePills(undefined)));"))
    assert got["options"] == []


def test_render_msg_strips_the_line_for_replies():
    assert "parsePills(" in _fn("renderMsg")


def test_render_pills_uses_textcontent_and_sends():
    body = _fn("renderPills")
    assert "textContent" in body
    assert "innerHTML" not in body
    assert "pill" in body
    assert "Send: " in body
    assert "$input.value" in body and "sendMessage()" in body


def test_send_clears_pills():
    assert re.search(r"querySelectorAll\(['\"]\.pills['\"]\)", _fn("sendMessage"))
