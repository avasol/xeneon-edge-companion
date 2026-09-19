# Xeneon Edge Companion (Galadriel HUD)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/avasol/xeneon-edge-companion?color=teal)](https://github.com/avasol/xeneon-edge-companion/releases)
[![Protocol](https://img.shields.io/badge/Protocol-v1.0-teal)](PROTOCOL.md)
[![Form Factor](https://img.shields.io/badge/Form%20Factor-2560x720%20Ultrawide-purple)](#overview)

> A dedicated, hardware-accelerated **2560×720 ultrawide AI companion terminal and HUD** engineered for Corsair iCUE and the Corsair Xeneon Flex / Edge display.

---

## Overview

The **Xeneon Edge Companion** turns the Corsair Xeneon ultrawide panel into a dedicated, ambient workstation interface for persistent AI agents. Originally designed for the [Galadriel](https://github.com/avasol/galadriel-public) persistent intelligence architecture, this widget operates as a self-contained Corsair iCUE dashboard widget (`.icuewidget`) that connects to any backend implementing the Edge HTTP/SSE protocol.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [● TOWER ONLINE] ~~~~~     ✦ AI COMMUNICATIONS TERMINAL ✦    T.A. 3021 · LÓRIEN | 13:18│
├────────────────────┬───────────────────────────────────────────────────┬───────────────┤
│                    │                                                   │ [INSTRUMENTS] │
│      (MIRROR)      │  [Agent Response Stream]                          │  • Status     │
│   Avatar Portrait  │  Live Markdown • Code Blocks • Tables             │  • System Log │
│   Thinking Rings   │                                                   │  • Media Hub  │
│                    │  [Interactive Tool Approvals]                     │               │
│  LÓRIEN TELEMETRY  │  [ Approve Execution ] [ Refuse ]                 │  COMPASS:     │
│  Session • Model   │                                                   │  Active Focus │
├────────────────────┴───────────────────────────────────────────────────┴───────────────┤
│ [ > Enter prompt or instruction...                                ] [ ATTACH ] [ SEND ]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Native 2560×720 Layout**: Crafted specifically for ultrawide secondary displays and desk-mounted companion screens, utilizing a 3-column command deck.
- **Still Water GPU Isolation**: Uses explicit CSS layer containment (`contain: layout style`, `transform: translateZ(0)`, and `backface-visibility: hidden`). Eliminates webview redraw stutter and buffer invalidations caused by Windows Desktop Window Manager (DWM) when playing hardware-accelerated video on primary monitors.
- **Buffered SSE Token Streaming**: Server-Sent Events stream seamlessly into in-flight bubbles. Mid-stream layout thrash is suppressed with a sleek blinking cursor, rendering rich formatted markdown upon completion.
- **Interactive Tool Approval Cards**: When an autonomous agent requests permission to run critical operations (shell commands, file modifications, code execution), interactive approval cards render chronologically in the stream for one-click human-in-the-loop authorization.
- **Real-Time System Log & Telemetry**: Dedicated slide-out drawer providing live journal tailing, harness health status, and prompt-cache efficiency tracking without issuing model calls.
- **Media Deck**: Integrated browser for agent-generated visual and auditory artifacts.

---

## Quick Start (iCUE Installation)

### 1. Download
Grab the latest pre-compiled **`galadriel_edge_v*.icuewidget`** file from the [Releases](https://github.com/avasol/xeneon-edge-companion/releases) page.

### 2. Import into Corsair iCUE
1. Open **Corsair iCUE**.
2. Navigate to your **Xeneon Flex / Edge Dashboard** or screen configuration.
3. Click **Add Widget / Import** and select the downloaded `.icuewidget` file.
4. Position the widget across your 2560×720 display canvas.

### 3. Configure Properties
In iCUE, open the widget settings:
- **Tower URL**: The HTTP base URL of your agent server (e.g. `http://localhost:8080` or your LAN address).
- **Edge Token**: The authentication token matching your backend's `EDGE_TOKEN`.
- **Poll Interval**: Background telemetry polling frequency (default: `5s`).

---

## Backend Protocol Contract

> 📋 **Canonical specification:** [PROTOCOL.md](PROTOCOL.md) — the full, versioned protocol document. What follows is a quick-reference summary.

Any custom AI service or agent harness can drive the Xeneon Edge Companion by exposing the following lightweight endpoints:

### Authentication
All requests from the widget supply the configured token in the HTTP header:
```http
X-Edge-Token: <configured_token>
```

### Core Endpoints

#### `GET /api/edge/history`
Returns recent conversation history to restore state on widget launch or reload.
```json
{
  "messages": [
    { "role": "usr", "text": "Synthesize the recent benchmarks." },
    { "role": "gal", "text": "Here are the compiled findings..." }
  ]
}
```

#### `POST /api/edge/stream`
Accepts a JSON payload `{ "message": "User prompt", "images": [] }` and streams Server-Sent Events (`text/event-stream`):
- `data: {"t": "progress", "v": "tool_name"}` — Signals that a tool or background process is running.
- `data: {"t": "token", "v": "text chunk"}` — Emits streaming text response.
- `data: {"t": "approval", "v": { "id": "123", "action": "run_shell", "details": "git status" }}` — Displays an in-line approval card.
- `data: {"t": "done", "v": ""}` — Concludes the reply.
- `data: {"t": "error", "v": "Error description"}` — Flags a turn failure.

#### `GET /api/edge/status`
Returns agent telemetry for the status drawer.
```json
{
  "status": "healthy",
  "active_model": "claude-sonnet-5",
  "active_project": "aedelgard",
  "daily_cost": "$0.42",
  "cache_hit_rate": "89.4%"
}
```

#### `GET /api/edge/logs`
Returns the recent raw system journal lines for diagnostic inspection.

#### `POST /api/edge/approve`
Receives `{ "id": "<approval_id>", "decision": "allow" | "deny" }` when the user clicks an approval card.

---

## Building from Source

To package the widget manually from source:

```bash
# Clone the repository
git clone https://github.com/avasol/xeneon-edge-companion.git
cd xeneon-edge-companion

# Build the .icuewidget package
bash build.sh
```

The output artifact will be placed in `./dist/galadriel_edge_v<version>.icuewidget`.

---

## Customization

The widget is pure HTML5, CSS3, and modern vanilla JavaScript:
- **Portrait Avatar**: Replace `resources/mirror.png` with your desired agent icon or scrying portrait.
- **Theme Accents**: Modify CSS variables in `index.html` under `:root` (`--pri`, `--sec`, `--teal`, `--bg`) to align with your setup's color palette.
- **Header Badges**: Customize `#topbar-era` and `#topbar-loc` in `index.html` to reflect your persona's setting or fictional realm.

---

## Kinship & Ecosystem

The Xeneon Edge Companion was developed within the **Galadriel** persistent agent ecosystem. For the open-source autonomous agent engine and long-term memory architecture, visit:

- [galadriel-public](https://github.com/avasol/galadriel-public) — Open-source persistent agent engine.
- [Aedelgard](https://aedelgard.com) — Sovereign personal intelligence.

---

## License

This project is licensed under the [MIT License](LICENSE).
