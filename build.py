#!/usr/bin/env python3
"""Build one .icuewidget package from a skin (see skins/SCHEMA.md).

A skin is data only: palette values, bundled fonts, PNG/WebP/JPG pictures and a
few short strings. This script validates a skin folder and packs it together
with the widget template (index.html, manifest.json, translation.json).
"""
import argparse
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MAX_SKIN_BYTES = 4 * 1024 * 1024
MAX_ICON_BYTES = 256 * 1024
MAX_PORTRAIT_BYTES = 1024 * 1024
MAX_FONT_BYTES = 512 * 1024

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class SkinError(Exception):
    """A skin broke a rule; the message starts with the offending field."""


# ── palette ──────────────────────────────────────────────────────────────

COLOUR_KEYS = {
    "bg", "bg-deep", "panel", "panel2", "topbar-bg",
    "pri", "pri-dim", "pri-mid", "pri-glow",
    "sec", "sec-bright", "sec-dim", "sec-glow",
    "text", "text-dim", "text-sec",
    "border", "border-g", "border-bright",
    "ok", "status-offline", "status-error",
}
TRIPLE_KEYS = {"pri-rgb", "sec-rgb", "ok-rgb", "shade-rgb"}
LENGTH_KEYS = {"radius"}

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_RGB_RE = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_RGBA_RE = re.compile(
    r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(0|1|0?\.\d+|1\.0+)\s*\)"
)
_TRIPLE_RE = re.compile(r"\d{1,3},\d{1,3},\d{1,3}")
_LENGTH_RE = re.compile(r"\d+(\.\d+)?(px|rem|em)")


def _is_colour(value):
    if not isinstance(value, str):
        return False
    if _HEX_RE.fullmatch(value):
        return True
    m = _RGB_RE.fullmatch(value)
    if m:
        return all(int(n) <= 255 for n in m.groups())
    m = _RGBA_RE.fullmatch(value)
    if m:
        return all(int(n) <= 255 for n in m.groups()[:3])
    return False


def _is_triple(value):
    if not isinstance(value, str) or not _TRIPLE_RE.fullmatch(value):
        return False
    return all(int(n) <= 255 for n in value.split(","))


def _is_length(value):
    return isinstance(value, str) and bool(_LENGTH_RE.fullmatch(value))


def _validate_palette(palette):
    if not isinstance(palette, dict):
        raise SkinError("palette: must be an object")
    for key, value in palette.items():
        if key in COLOUR_KEYS:
            if not _is_colour(value):
                raise SkinError("palette.%s: not a colour" % key)
        elif key in TRIPLE_KEYS:
            if not _is_triple(value):
                raise SkinError("palette.%s: not a triple" % key)
        elif key in LENGTH_KEYS:
            if not _is_length(value):
                raise SkinError("palette.%s: not a length" % key)
        else:
            raise SkinError("palette.%s: unknown palette key" % key)


# ── fonts ────────────────────────────────────────────────────────────────

FONT_KEYS = {"font-body", "font-mono", "font-ui"}
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "system-ui", "cursive"}
_QUOTED_FAMILY_RE = re.compile(r"'[A-Za-z0-9 -]{1,40}'")
_FAMILY_RE = re.compile(r"[A-Za-z0-9 -]{1,40}")


def _validate_fonts(fonts):
    if not isinstance(fonts, dict):
        raise SkinError("fonts: must be an object")
    for key, value in fonts.items():
        if key not in FONT_KEYS:
            raise SkinError("fonts.%s: unknown font key" % key)
        if not isinstance(value, str):
            raise SkinError("fonts.%s: must be a string" % key)
        for part in value.split(","):
            part = part.strip()
            if part in GENERIC_FAMILIES:
                continue
            if not _QUOTED_FAMILY_RE.fullmatch(part):
                raise SkinError("fonts.%s: bad font family %r" % (key, part))


# ── strings ──────────────────────────────────────────────────────────────

STRING_KEYS = {
    "title", "name", "title_line", "terminal_label", "era", "location",
    "channel_label", "channel_name", "new_session", "idle_title", "idle_text",
    "input_placeholder", "portrait_alt", "status_title", "logs_title",
    "logs_follow", "rune", "assistant_glyph", "user_glyph", "side_glyphs",
}
GLYPH_KEYS = {"rune", "assistant_glyph", "user_glyph", "side_glyphs"}


def _has_control(value):
    for ch in value:
        if ch in ("\u2028", "\u2029"):
            return True
        if unicodedata.category(ch) == "Cc":
            return True
    return False


def _validate_strings(strings):
    if not isinstance(strings, dict):
        raise SkinError("strings: must be an object")
    for key, value in strings.items():
        if key not in STRING_KEYS:
            raise SkinError("strings.%s: unknown string key" % key)
        if not isinstance(value, str):
            raise SkinError("strings.%s: must be a string" % key)
        if _has_control(value):
            raise SkinError("strings.%s: contains a control character" % key)
        limit = 8 if key in GLYPH_KEYS else 80
        if len(value) > limit:
            raise SkinError("strings.%s: longer than %d characters" % (key, limit))


# ── paths and files ──────────────────────────────────────────────────────

def _resolve_inside(base, rel, field):
    if not isinstance(rel, str) or not rel:
        raise SkinError("%s: must be a path string" % field)
    path = (base / rel).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        raise SkinError("%s: escapes the skin folder" % field)
    return path


def _validate_font_files(skin_dir, font_files):
    if not isinstance(font_files, list):
        raise SkinError("font_files: must be a list")
    for i, entry in enumerate(font_files):
        field = "font_files[%d]" % i
        if not isinstance(entry, dict):
            raise SkinError("%s: must be an object" % field)
        family = entry.get("family")
        if not isinstance(family, str) or not _FAMILY_RE.fullmatch(family):
            raise SkinError("%s.family: bad family name" % field)
        rel = entry.get("file")
        if not isinstance(rel, str) or not rel.startswith("fonts/") or not rel.endswith(".woff2"):
            raise SkinError("%s.file: must be a fonts/*.woff2 file" % field)
        path = _resolve_inside(skin_dir, rel, field + ".file")
        if not path.is_file():
            raise SkinError("%s.file: not a file" % field)
        if path.stat().st_size > MAX_FONT_BYTES:
            raise SkinError("%s.file: larger than 512 KB" % field)
        if path.read_bytes()[:4] != b"wOF2":
            raise SkinError("%s.file: not a woff2 font" % field)


def _validate_images(skin_dir, images):
    if not isinstance(images, dict):
        raise SkinError("images: must be an object")
    icon = images.get("icon")
    if not isinstance(icon, str) or not icon.endswith(".png"):
        raise SkinError("images.icon: must be a .png file")
    icon_path = _resolve_inside(skin_dir, icon, "images.icon")
    if not icon_path.is_file():
        raise SkinError("images.icon: not a file")
    if icon_path.stat().st_size > MAX_ICON_BYTES:
        raise SkinError("images.icon: larger than 256 KB")
    if icon_path.read_bytes()[:8] != PNG_MAGIC:
        raise SkinError("images.icon: not a PNG")

    portrait = images.get("portrait")
    if portrait is None:
        return
    if not isinstance(portrait, str):
        raise SkinError("images.portrait: must be a path string")
    ext = Path(portrait).suffix.lower()
    if ext not in (".png", ".webp", ".jpg", ".jpeg"):
        raise SkinError("images.portrait: unsupported image type")
    path = _resolve_inside(skin_dir, portrait, "images.portrait")
    if not path.is_file():
        raise SkinError("images.portrait: not a file")
    if path.stat().st_size > MAX_PORTRAIT_BYTES:
        raise SkinError("images.portrait: larger than 1 MB")
    data = path.read_bytes()
    if ext == ".png":
        ok = data[:8] == PNG_MAGIC
    elif ext == ".webp":
        ok = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    else:
        ok = data[:3] == b"\xff\xd8\xff"
    if not ok:
        raise SkinError("images.portrait: bytes do not match the extension")


def _validate_total_size(skin_dir):
    total = 0
    for path in skin_dir.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    if total > MAX_SKIN_BYTES:
        raise SkinError("skin: folder larger than 4 MB")


# ── meta ─────────────────────────────────────────────────────────────────

_ID_RE = re.compile(r"[a-z][a-z0-9-]{1,31}")
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def _plain_text(value, field, limit):
    if not isinstance(value, str):
        raise SkinError("%s: must be a string" % field)
    if _has_control(value):
        raise SkinError("%s: contains a control character" % field)
    if len(value) > limit:
        raise SkinError("%s: longer than %d characters" % (field, limit))


def _validate_meta(data, skin_dir):
    if data.get("schema") != 1:
        raise SkinError("schema: must be 1")
    skin_id = data.get("id")
    if not isinstance(skin_id, str) or not _ID_RE.fullmatch(skin_id):
        raise SkinError("id: must match [a-z][a-z0-9-]{1,31}")
    name = data.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 40) or _has_control(name):
        raise SkinError("name: must be 1-40 plain characters")
    version = data.get("version")
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise SkinError("version: must be MAJOR.MINOR.PATCH")
    if "author" in data:
        _plain_text(data["author"], "author", 80)
    if "description" in data:
        _plain_text(data["description"], "description", 80)
    if "palette" not in data:
        raise SkinError("palette: required")
    _validate_palette(data["palette"])
    _validate_fonts(data.get("fonts", {}))
    _validate_font_files(skin_dir, data.get("font_files", []))
    _validate_strings(data.get("strings", {}))
    _validate_images(skin_dir, data.get("images"))


# ── public API ───────────────────────────────────────────────────────────

def load_skin(path):
    """Validate a skin folder and return its data plus 'dir'."""
    skin_dir = Path(path).resolve()
    skin_json = skin_dir / "skin.json"
    try:
        raw = skin_json.read_text(encoding="utf-8")
    except OSError:
        raise SkinError("skin.json: missing or unreadable")
    try:
        data = json.loads(raw)
    except ValueError:
        raise SkinError("skin.json: not valid JSON")
    if not isinstance(data, dict):
        raise SkinError("skin.json: must be an object")
    _validate_meta(data, skin_dir)
    _validate_total_size(skin_dir)
    data["dir"] = skin_dir
    return data


def render_palette(skin):
    """Return the CSS for the skin's @font-face rules and :root variables."""
    parts = []
    for entry in skin.get("font_files", []):
        parts.append(
            "@font-face{font-family:'%s';src:url('resources/fonts/%s') format('woff2');}"
            % (entry["family"], Path(entry["file"]).name)
        )
    parts.append(":root{")
    for key, value in skin.get("palette", {}).items():
        parts.append("--%s:%s;" % (key, value))
    for key, value in skin.get("fonts", {}).items():
        parts.append("--%s:%s;" % (key, value))
    parts.append("}")
    return "".join(parts)


def skin_data(skin):
    """Return the JSON payload for the skin-data script block."""
    portrait = skin.get("images", {}).get("portrait")
    portrait_ref = None
    if portrait:
        portrait_ref = "resources/portrait" + Path(portrait).suffix.lower()
    payload = json.dumps(
        {"strings": skin.get("strings", {}), "portrait": portrait_ref},
        ensure_ascii=False,
    )
    return payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build(skin_dir, out_dir=None):
    """Validate a skin and write its .icuewidget package. Return the path."""
    skin = load_skin(skin_dir)
    if out_dir is None:
        out_dir = ROOT / "dist"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    translation = json.loads((ROOT / "translation.json").read_text(encoding="utf-8"))

    palette_marker = '<style id="skin-palette"></style>'
    data_marker = '<script id="skin-data" type="application/json">{}</script>'
    if palette_marker not in index:
        raise SkinError("index.html: skin-palette marker missing")
    if data_marker not in index:
        raise SkinError("index.html: skin-data marker missing")
    index = index.replace(
        palette_marker,
        '<style id="skin-palette">' + render_palette(skin) + "</style>",
        1,
    )
    index = index.replace(
        data_marker,
        '<script id="skin-data" type="application/json">' + skin_data(skin) + "</script>",
        1,
    )

    manifest["id"] = "com.aedelgard.edge." + skin["id"]
    manifest["name"] = skin["name"]
    if "description" in skin:
        manifest["description"] = skin["description"]
    manifest["preview_icon"] = "resources/icon.png"

    translation["en"]["widget_name"] = skin["name"]

    version = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
    out_path = out_dir / ("%s_edge_v%s.icuewidget" % (skin["id"], version))

    skin_root = skin["dir"]
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", index)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr("translation.json", json.dumps(translation, indent=2, ensure_ascii=False))
        zf.write(skin_root / skin["images"]["icon"], "resources/icon.png")
        portrait = skin.get("images", {}).get("portrait")
        if portrait:
            zf.write(
                skin_root / portrait,
                "resources/portrait" + Path(portrait).suffix.lower(),
            )
        for entry in skin.get("font_files", []):
            zf.write(
                skin_root / entry["file"],
                "resources/fonts/" + Path(entry["file"]).name,
            )
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a .icuewidget from a skin.")
    parser.add_argument("--skin", required=True, help="path to the skin folder")
    parser.add_argument("--out", default=None, help="output directory (default: dist/)")
    parser.add_argument("--check", action="store_true", help="validate only")
    args = parser.parse_args(argv)

    try:
        if args.check:
            skin = load_skin(args.skin)
            print("ok: " + skin["id"])
        else:
            print(build(args.skin, args.out))
    except SkinError as exc:
        print("skin refused: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
