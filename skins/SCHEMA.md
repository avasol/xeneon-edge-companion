# Skins — schema v1

A skin decides how the widget looks. It never changes what the widget does.
A skin is **data only**: colours, fonts, pictures and a few short words. No
script, no CSS text, no links, no network. That is what makes a skin safe to
share, review and sign.

```
skins/<id>/
  skin.json        required
  portrait.png     optional (.png / .webp / .jpg) — the round picture
  icon.png         required (.png) — the widget's icon in iCUE
  fonts/*.woff2    optional
```

Build one package per skin:

```bash
python3 build.py --skin skins/aedelgard          # → dist/aedelgard_edge_v<version>.icuewidget
python3 build.py --skin /path/to/my-skin         # a skin can live anywhere
python3 build.py --skin skins/aedelgard --check  # validate only
```

`build.py` refuses a skin that breaks any rule below. It never edits the skin.

## skin.json

```json
{
  "schema": 1,
  "id": "aedelgard",
  "name": "Aedelgard",
  "version": "1.0.0",
  "author": "Avasol",
  "description": "A quiet window to your mind.",
  "palette": { "bg": "#100f0d", "pri": "#e4bf7f", "pri-rgb": "228,191,127" },
  "fonts":   { "font-body": "'Courier New', monospace" },
  "font_files": [],
  "images":  { "portrait": "portrait.png", "icon": "icon.png" },
  "strings": { "name": "AEDELGARD", "idle_title": "Nothing yet" }
}
```

| Field | Rule |
|---|---|
| `schema` | `1` |
| `id` | `^[a-z][a-z0-9-]{1,31}$`. The package id becomes `com.aedelgard.edge.<id>`. |
| `name` | plain text, 1–40 characters |
| `version` | `MAJOR.MINOR.PATCH` |
| `author`, `description` | plain text, ≤ 80 characters |
| `palette` | only the keys listed below; every value must match its kind |
| `fonts` | only `font-body`, `font-mono`, `font-ui`; a comma list of quoted family names (`'Name'`, letters, digits, spaces, hyphens, ≤ 40 chars each) or generic families (`serif`, `sans-serif`, `monospace`, `system-ui`, `cursive`) |
| `font_files` | bundled `fonts/<name>.woff2` files only, each ≤ 512 KB; declared as `{"family": "Name", "file": "fonts/x.woff2"}` |
| `images.portrait` | optional; `.png`, `.webp` or `.jpg`, ≤ 1 MB; the file's own bytes must match its extension |
| `images.icon` | required; `.png`, ≤ 256 KB |
| `strings` | only the keys listed below; plain text, no control characters, each ≤ 80 characters (glyphs ≤ 8) |

**No SVG, anywhere.** An SVG can carry script. The whole skin folder must stay
under 4 MB.

### Palette keys

Missing keys keep the widget's built-in default (the neutral reference look).
Warning and error tints inside messages are semantic and stay the same in every skin.

| Key | Kind | Used for |
|---|---|---|
| `bg`, `bg-deep`, `panel`, `panel2`, `topbar-bg` | colour | backgrounds |
| `shade-rgb` | triple | dark overlays (sheets, menus) as `r,g,b` |
| `pri`, `pri-dim`, `pri-mid`, `pri-glow` | colour | primary accent |
| `pri-rgb` | triple | the primary accent as `r,g,b` (for translucent tints) |
| `sec`, `sec-bright`, `sec-dim`, `sec-glow` | colour | secondary accent |
| `sec-rgb` | triple | the secondary accent as `r,g,b` |
| `text`, `text-dim`, `text-sec` | colour | text |
| `border`, `border-g`, `border-bright` | colour | borders |
| `ok`, `ok-rgb` | colour / triple | success, online |
| `status-offline`, `status-error` | colour | errors, offline |
| `radius` | length | corner radius |

**Kinds:** *colour* = `#rgb`, `#rrggbb`, `#rrggbbaa`, `rgb(r,g,b)` or
`rgba(r,g,b,a)` with plain numbers; *triple* = `r,g,b` with 0–255 integers;
*length* = a number with `px`, `rem` or `em`. Nothing else is accepted, so a
value can never smuggle in `;`, `}`, `url(` or `expression(`.

### String keys

| Key | Where it shows |
|---|---|
| `title` | the page title |
| `name`, `title_line` | the identity under the portrait |
| `terminal_label` | the centre of the top bar |
| `era`, `location` | the right of the top bar |
| `channel_label`, `channel_name` | the chat header |
| `new_session` | the new-session button |
| `idle_title`, `idle_text` | the empty conversation |
| `input_placeholder` | the message box |
| `portrait_alt` | the portrait's description |
| `status_title`, `logs_title`, `logs_follow` | the Status and Logs panels |
| `rune`, `assistant_glyph`, `user_glyph`, `side_glyphs` | small glyphs (≤ 8 characters each) |

Strings are placed with `textContent`, never as HTML, so `<b>` shows as the
four characters `<b>`.

## Signing and the catalogue

A skin is an extension of kind `skin` in an Aedelgard body: signed by its
author, countersigned after review, listed in the catalogue and recallable like
any other extension. The review is a picture-and-text review, because there is
nothing else in a skin to review.
