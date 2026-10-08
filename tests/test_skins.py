"""Skins (skins/SCHEMA.md): the widget takes its look only from a skin.
Planner-written, protected.

A skin is data only: palette values that must match their kind, bundled fonts,
PNG/WebP/JPG pictures checked by their bytes (never SVG), and short plain
strings placed with textContent. build.py validates and packs one
.icuewidget per skin. The template itself carries no identity of any skin.
"""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build  # noqa: E402

HTML = (ROOT / "index.html").read_text(encoding="utf-8")
AED = ROOT / "skins" / "aedelgard"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WOFF2 = b"wOF2" + b"\x00" * 64

BRAND = re.compile(r"galadriel|isildur|lothl|amon s|lady of|speak to the lady|t\.a\. 3021", re.I)


def _skin(tmp_path, **over):
    d = tmp_path / "s"
    d.mkdir(exist_ok=True)
    (d / "icon.png").write_bytes(PNG)
    data = {
        "schema": 1, "id": "test-skin", "name": "Test", "version": "1.0.0",
        "author": "A", "description": "d",
        "palette": {"pri": "#112233", "pri-rgb": "17,34,51", "radius": "6px"},
        "fonts": {}, "font_files": [], "images": {"icon": "icon.png"},
        "strings": {"name": "TEST", "idle_title": "Quiet"},
    }
    for k, v in over.items():
        if v is None:
            data.pop(k, None)
        else:
            data[k] = v
    (d / "skin.json").write_text(json.dumps(data), encoding="utf-8")
    return d


def _built(tmp_path, skin_dir):
    out = build.build(skin_dir, tmp_path / "dist")
    z = zipfile.ZipFile(out)
    return out, z, {n: z.read(n) for n in z.namelist()}


def _skin_data(index_html):
    m = re.search(r'<script id="skin-data" type="application/json">(.*?)</script>', index_html, re.S)
    assert m, "skin-data block missing"
    return json.loads(m.group(1))


# ── validation ───────────────────────────────────────────────────────

def test_the_aedelgard_skin_is_valid():
    build.load_skin(AED)


@pytest.mark.parametrize("value", [
    "#123456; background:url(x)", "url(http://x)", "red}body{", "expression(alert(1))",
    "#12345", "rgb(1,2)", "blue", "", "rgba(1,2,3,0.5) !important", "<b>",
])
def test_bad_colour_refused(tmp_path, value):
    with pytest.raises(build.SkinError):
        build.load_skin(_skin(tmp_path, palette={"pri": value}))


@pytest.mark.parametrize("key,value", [
    ("pri-rgb", "256,0,0"), ("pri-rgb", "1,2"), ("pri-rgb", "1, 2, 3; x"),
    ("radius", "8"), ("radius", "8px;"), ("radius", "calc(1px)"),
    ("not-a-key", "#fff"), ("w-left", "100px"),
])
def test_bad_palette_entry_refused(tmp_path, key, value):
    with pytest.raises(build.SkinError):
        build.load_skin(_skin(tmp_path, palette={key: value}))


@pytest.mark.parametrize("value", ["#abc", "#aabbcc", "#aabbccdd", "rgb(1, 2, 3)", "rgba(1,2,3,0.5)", "rgba(10,20,30,.25)"])
def test_good_colours_accepted(tmp_path, value):
    build.load_skin(_skin(tmp_path, palette={"pri": value}))


@pytest.mark.parametrize("fonts", [
    {"font-body": "url(x)"}, {"font-body": "'A';}"}, {"font-title": "serif"},
    {"font-body": "'" + "x" * 41 + "'"}, {"font-body": "Comic Sans"},
])
def test_bad_fonts_refused(tmp_path, fonts):
    with pytest.raises(build.SkinError):
        build.load_skin(_skin(tmp_path, fonts=fonts))


def test_good_fonts_accepted(tmp_path):
    build.load_skin(_skin(tmp_path, fonts={"font-body": "'Courier New', 'Segoe UI', monospace", "font-ui": "system-ui"}))


@pytest.mark.parametrize("strings", [
    {"name": "x" * 81}, {"name": "a\nb"}, {"name": "a\x00b"}, {"rune": "123456789"},
    {"unknown_key": "x"}, {"name": 5},
])
def test_bad_strings_refused(tmp_path, strings):
    with pytest.raises(build.SkinError):
        build.load_skin(_skin(tmp_path, strings=strings))


@pytest.mark.parametrize("over", [
    {"id": "Bad Id"}, {"id": "../x"}, {"schema": 2}, {"version": "1.0"}, {"name": ""},
    {"images": {}}, {"palette": "nope"},
])
def test_bad_meta_refused(tmp_path, over):
    with pytest.raises(build.SkinError):
        build.load_skin(_skin(tmp_path, **over))


def test_svg_refused_by_name_and_by_bytes(tmp_path):
    d = _skin(tmp_path, images={"icon": "icon.png", "portrait": "p.svg"})
    (d / "p.svg").write_bytes(b"<svg onload='alert(1)'/>")
    with pytest.raises(build.SkinError):
        build.load_skin(d)
    d = _skin(tmp_path, images={"icon": "icon.png", "portrait": "p.png"})
    (d / "p.png").write_bytes(b"<svg onload='alert(1)'/>")
    with pytest.raises(build.SkinError):
        build.load_skin(d)


@pytest.mark.parametrize("name,data", [("p.png", PNG), ("p.webp", WEBP), ("p.jpg", JPG)])
def test_portrait_kinds_accepted(tmp_path, name, data):
    d = _skin(tmp_path, images={"icon": "icon.png", "portrait": name})
    (d / name).write_bytes(data)
    build.load_skin(d)


def test_image_paths_must_stay_inside(tmp_path):
    (tmp_path / "outside.png").write_bytes(PNG)
    with pytest.raises(build.SkinError):
        build.load_skin(_skin(tmp_path, images={"icon": "../outside.png"}))


def test_size_caps(tmp_path):
    d = _skin(tmp_path, images={"icon": "icon.png", "portrait": "p.png"})
    (d / "p.png").write_bytes(PNG + b"\x00" * (1024 * 1024 + 1))
    with pytest.raises(build.SkinError):
        build.load_skin(d)
    d2 = _skin(tmp_path)
    (d2 / "icon.png").write_bytes(PNG + b"\x00" * (256 * 1024 + 1))
    with pytest.raises(build.SkinError):
        build.load_skin(d2)


def test_whole_skin_cap(tmp_path):
    d = _skin(tmp_path)
    (d / "filler.bin").write_bytes(b"\x00" * (4 * 1024 * 1024 + 1))
    with pytest.raises(build.SkinError):
        build.load_skin(d)


def test_font_files_only_woff2(tmp_path):
    d = _skin(tmp_path, font_files=[{"family": "Mine", "file": "fonts/m.woff2"}], fonts={"font-body": "'Mine', monospace"})
    (d / "fonts").mkdir()
    (d / "fonts" / "m.woff2").write_bytes(WOFF2)
    build.load_skin(d)
    d2 = _skin(tmp_path, font_files=[{"family": "Mine", "file": "fonts/m.ttf"}])
    (d2 / "fonts").mkdir(exist_ok=True)
    (d2 / "fonts" / "m.ttf").write_bytes(b"\x00\x01\x00\x00")
    with pytest.raises(build.SkinError):
        build.load_skin(d2)


# ── building ─────────────────────────────────────────────────────────

def test_build_aedelgard_package(tmp_path):
    out, z, files = _built(tmp_path, AED)
    ver = json.loads((ROOT / "manifest.json").read_text())["version"]
    assert out.name == f"aedelgard_edge_v{ver}.icuewidget"
    names = set(files)
    assert {"index.html", "manifest.json", "translation.json", "resources/icon.png", "resources/portrait.png"} <= names
    assert not any(n.lower().endswith(".svg") for n in names)
    man = json.loads(files["manifest.json"])
    assert man["id"] == "com.aedelgard.edge.aedelgard" and man["name"] == "Aedelgard"
    assert man["preview_icon"] == "resources/icon.png" and man["version"] == ver
    tr = json.loads(files["translation.json"])
    assert tr["en"]["widget_name"] == "Aedelgard"
    html = files["index.html"].decode("utf-8")
    assert "--pri:#e4bf7f" in html.replace(" ", "")
    sd = _skin_data(html)
    skin = json.loads((AED / "skin.json").read_text(encoding="utf-8"))
    assert sd["strings"] == skin["strings"] and sd["portrait"] == "resources/portrait.png"


def test_built_aedelgard_carries_no_other_identity(tmp_path):
    _, _, files = _built(tmp_path, AED)
    for name, data in files.items():
        if name.endswith((".html", ".json")):
            assert not BRAND.search(data.decode("utf-8")), name


def test_missing_palette_keys_keep_defaults(tmp_path):
    _, _, files = _built(tmp_path, _skin(tmp_path))
    html = files["index.html"].decode("utf-8")
    pal = re.search(r'<style id="skin-palette">(.*?)</style>', html, re.S).group(1)
    assert "--pri:#112233" in pal.replace(" ", "")
    assert "--bg:" not in pal.replace(" ", "")


def test_no_portrait_means_no_portrait_file(tmp_path):
    _, _, files = _built(tmp_path, _skin(tmp_path))
    assert not any(n.startswith("resources/portrait") for n in files)
    assert _skin_data(files["index.html"].decode("utf-8"))["portrait"] is None


def test_strings_cannot_break_out_of_the_data_block(tmp_path):
    evil = "</script><img src=x onerror=alert(1)>"[:80]
    _, _, files = _built(tmp_path, _skin(tmp_path, strings={"name": evil}))
    html = files["index.html"].decode("utf-8")
    assert "</script><img" not in html and "<img src=x" not in html
    assert _skin_data(html)["strings"]["name"] == evil


def test_font_files_are_bundled_with_face_rules(tmp_path):
    d = _skin(tmp_path, font_files=[{"family": "Mine", "file": "fonts/m.woff2"}], fonts={"font-body": "'Mine', monospace"})
    (d / "fonts").mkdir()
    (d / "fonts" / "m.woff2").write_bytes(WOFF2)
    _, _, files = _built(tmp_path, d)
    assert "resources/fonts/m.woff2" in files
    pal = re.search(r'<style id="skin-palette">(.*?)</style>', files["index.html"].decode("utf-8"), re.S).group(1)
    assert "@font-face" in pal and "font-family:'Mine'" in pal.replace(" ", "") and "resources/fonts/m.woff2" in pal


def test_a_skin_can_live_outside_the_repo(tmp_path):
    ext = tmp_path / "elsewhere" / "mine"
    shutil.copytree(_skin(tmp_path), ext)
    out, _, _ = _built(tmp_path, ext)
    assert out.name.startswith("test-skin_edge_v")


def test_build_never_writes_into_the_repo_template(tmp_path):
    before = (ROOT / "index.html").read_bytes(), (ROOT / "manifest.json").read_bytes(), (ROOT / "translation.json").read_bytes()
    _built(tmp_path, AED)
    assert before == ((ROOT / "index.html").read_bytes(), (ROOT / "manifest.json").read_bytes(), (ROOT / "translation.json").read_bytes())


def test_cli_check_and_build(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "build.py"), "--skin", str(AED), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    bad = _skin(tmp_path, palette={"pri": "url(x)"})
    r = subprocess.run([sys.executable, str(ROOT / "build.py"), "--skin", str(bad), "--check"], capture_output=True, text=True)
    assert r.returncode != 0 and "pri" in (r.stdout + r.stderr)
    r = subprocess.run([sys.executable, str(ROOT / "build.py"), "--skin", str(AED), "--out", str(tmp_path / "o")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert list((tmp_path / "o").glob("aedelgard_edge_v*.icuewidget"))


# ── the template ─────────────────────────────────────────────────────

def test_template_carries_no_identity():
    assert not BRAND.search(HTML)
    for f in ("manifest.json", "translation.json"):
        assert not BRAND.search((ROOT / f).read_text(encoding="utf-8")), f
    assert not (ROOT / "resources" / "mirror.png").exists()


def test_template_has_the_skin_blocks():
    assert '<style id="skin-palette"></style>' in HTML
    assert '<script id="skin-data" type="application/json">{}</script>' in HTML


def test_tinted_colours_live_only_in_the_root_block():
    root_end = HTML.index("}", HTML.index(":root {"))
    rest = HTML[root_end:]
    for lit in ("184,204,224", "221,224,236", "#4fd1c5", "79,209,197", "#050609", "4,4,8", "#b8cce0", "#dde0ec"):
        assert lit not in rest.replace(" ", ""), lit
    head = HTML[:root_end]
    for var in ("--bg-deep:", "--shade-rgb:", "--ok:", "--ok-rgb:"):
        assert var in head.replace(" ", ""), var


def _fn(name):
    m = re.search(r"(function " + re.escape(name) + r"\([^)]*\) \{.*?\n\})", HTML, re.S)
    assert m, name + " not found"
    return m.group(1)


def test_apply_skin_uses_text_only():
    f = _fn("applySkin")
    assert "innerHTML" not in f
    script = (
        "const { createContext, runInContext } = require('node:vm');\n"
        "const els = [{dataset:{skin:'name'}, textContent:''}, {dataset:{skin:'idle_title'}, textContent:''}];\n"
        "const input = {placeholder:''}; const img = {src:'', alt:'', style:{}};\n"
        "const ctx = createContext({ document: { title:'', querySelectorAll: () => els,\n"
        "  getElementById: (id) => id === 'msg-input' ? input : (id === 'mirror-img' ? img : null) } });\n"
        f"runInContext({json.dumps(f)}, ctx);\n"
        "runInContext(\"applySkin({strings:{name:'<b>N</b>', idle_title:'Q', input_placeholder:'P', title:'T', portrait_alt:'A'}, portrait:'resources/portrait.png'})\", ctx);\n"
        "console.log(JSON.stringify([els[0].textContent, els[1].textContent, input.placeholder, ctx.document.title, img.src, img.alt]));\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["<b>N</b>", "Q", "P", "T", "resources/portrait.png", "A"]


def test_skin_strings_have_neutral_defaults():
    m = re.search(r"const DEFAULT_SKIN_STRINGS = (\{.*?\});", HTML, re.S)
    assert m
    keys = set(re.findall(r"(\w+)\s*:", m.group(1)))
    assert {"name", "idle_title", "idle_text", "input_placeholder", "rune", "assistant_glyph", "user_glyph"} <= keys


def test_version_is_1_4():
    v = re.search(r"const WIDGET_VERSION = '([\d.]+)';", HTML).group(1)
    assert tuple(map(int, v.split("."))) >= (1, 4, 0)
    assert json.loads((ROOT / "manifest.json").read_text())["version"] == v


# ── the skins shipped here ───────────────────────────────────────────

PERSONAL = re.compile(r"isildur|thomas|avasol\.|deodour|10\.0\.\d|\.service\b", re.I)


@pytest.mark.parametrize("skin", ["aedelgard", "galadriel"])
def test_shipped_skins_are_valid_and_carry_nothing_personal(tmp_path, skin):
    d = ROOT / "skins" / skin
    build.load_skin(d)
    assert not PERSONAL.search((d / "skin.json").read_text(encoding="utf-8"))
    _, _, files = _built(tmp_path, d)
    for name, data in files.items():
        if name.endswith((".html", ".json")):
            assert not PERSONAL.search(data.decode("utf-8")), name
