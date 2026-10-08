# Edge Protocol v1.1

**A lightweight HTTP/SSE protocol for peripheral AI agent displays.**

The Edge Protocol is a contract between an AI agent backend (the *Tower*) and a peripheral display surface (the *Widget*). It is designed for secondary screens, desktop panels, Stream Deck layouts, e-ink status displays, and any hardware that benefits from a live window into a persistent agent.

This document is the canonical specification. It is implementation-agnostic — nothing here depends on iCUE, Corsair, or any specific widget UI.

---

## 1. Transport

- **Protocol:** HTTPS (production) or HTTP (localhost development)
- **Event streaming:** Server-Sent Events (`text/event-stream`)
- **Other requests:** JSON over HTTP, standard `Content-Type: application/json`

All responses carry `X-Protocol-Version: 1.1` (servers that only implement v1.0 send `1.0`).

---

## 2. Authentication

Every request from the widget includes:

```http
X-Edge-Token: <pre-shared token>
```

The Tower validates this token on every endpoint. Requests with a missing or invalid token receive `401 Unauthorized` with body:

```json
{ "error": "unauthorized", "detail": "Missing or invalid X-Edge-Token" }
```

The token is configured on both sides (Tower `.env` as `EDGE_TOKEN`, widget as a configuration property) and never rotated by the protocol itself. Rotation is a manual administrative action.

### 2.1 CORS — every sent header must be allowed

The widget runs in a browser (QtWebEngine/Chromium), so the Tower is a
cross-origin service. Before any non-simple request, the browser sends a CORS
preflight (`OPTIONS`) and the Tower must list every request header the widget
attaches in `Access-Control-Allow-Headers`. A header the widget sends but the
Tower omits is rejected **before the request is sent** — the fetch fails with
"Failed to fetch" and the feature dies silently.

**Rule:** `Access-Control-Allow-Headers` is a contract that must move in
lock-step with the widget's `headers()`. When you add a request header
widget-side, add it here in the same change. Single-source the allow-list on
the Tower (one constant, both the generic CORS helper and any SSE response
point at it) so the two declarations cannot drift.

> Worked example: a `X-Edge-Boot` header added widget-side for instance
> diagnostics was not mirrored into `Access-Control-Allow-Headers`, and every
> panel that used `fetch` (Status, Logs, Media) broke at the preflight while
> direct `curl` and stubbed tests stayed green — neither exercises the browser
> boundary.`


### 2.2 Errors must be readable too

Every refusal (`403` for a wrong token, `503` when the agent loop is down) must
carry `Access-Control-Allow-Origin` exactly like a success. Without it the
browser hides the status code and the widget sees only "Failed to fetch", so a
rejected token is indistinguishable from an unreachable Tower. Since v1.3.35 the
widget's SETTINGS row probes `GET /api/edge/status` and reports `conn ✓`,
`conn ✗` (rejected, 403) or `conn ✗` (unreachable); that diagnosis is only as
honest as the Tower's CORS on its error responses.

---

## 3. Endpoints

### 3.1 `GET /api/edge/status`

Returns live telemetry for the status instruments panel.

**Response:**
```json
{
  "status": "healthy",
  "active_model": "claude-sonnet-5",
  "active_provider": "anthropic",
  "active_project": "aedelgard",
  "daily_cost": "$0.42",
  "cache_hit_rate": "89.4%",
  "session_number": 142,
  "uptime_seconds": 34823,
  "tower_version": "0.25.56-mind"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `healthy`, `degraded`, or `offline` |
| `active_model` | string | Current model ID (e.g. `claude-sonnet-5`, `deepseek-ai/DeepSeek-V4-Pro`) |
| `active_provider` | string | Provider brand (e.g. `anthropic`, `nebius`) |
| `active_project` | string | Active project heading |
| `daily_cost` | string | Human-readable cost since midnight UTC |
| `cache_hit_rate` | string | Prompt cache hit rate as percentage |
| `session_number` | integer | Monotonic session counter |
| `uptime_seconds` | integer | Seconds since Tower process start |
| `tower_version` | string | Tower/agent version string |

The widget polls this endpoint periodically (configurable, default 5 seconds).

### 3.2 `GET /api/edge/history`

Returns recent conversation messages for state restoration on widget launch or reload.

**Response:**
```json
{
  "messages": [
    { "role": "usr", "text": "What's the cache hit rate today?" },
    { "role": "gal", "text": "89.4% over 142 calls. Here's the breakdown..." },
    { "role": "usr", "text": "Thanks." },
    { "role": "gal", "text": "Of course." }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `messages` | array | Ordered list, oldest first |
| `messages[].role` | string | `usr` (user) or `gal` (agent) |
| `messages[].text` | string | Plain text (markdown not rendered here — the widget renders it) |

The widget requests this once on load and caches it. A full history replay is not the intent — this is a warm-start buffer for the visible conversation surface.

### 3.3 `POST /api/edge/send`

Sends a user message to the agent for processing. The Tower accepts the message, queues it for the agent loop, and the response is delivered via the SSE stream.

**Request:**
```json
{
  "message": "What's the status of the Reddit campaign?",
  "images": []
}
```

| Field | Type | Description |
|---|---|---|
| `message` | string | The user's text prompt |
| `images` | array of string | Base64-encoded image data URIs (optional, empty array if none) |

**Response (immediate):**
```json
{ "accepted": true, "message_id": "msg_abc123" }
```

The actual agent response streams via SSE (see §4). This endpoint returns immediately — it does not block on agent processing.

**Errors:**
- `429 Too Many Requests` — rate limit, retry after `Retry-After` seconds
- `503 Service Unavailable` — Tower is starting or in a restart cycle

### 3.4 `GET /api/edge/stream`

Opens a long-lived SSE connection. The Tower pushes events as the agent processes the turn.

**Connection:** The widget opens this once and holds it open. The stream remains connected across multiple turns — the widget does not reconnect between messages.

**Reconnection:** If the stream drops, the widget reconnects after a 2-second backoff (doubling to 30s max). On reconnect, the widget calls `/api/edge/history` to catch any messages delivered during the gap.

### 3.5 `GET /api/edge/logs`

Returns recent system journal lines for diagnostic inspection.

**Response:**
```json
{
  "lines": [
    "[14:32:01] palace_search: 'reddit campaign status' → 3 results (0 tokens)",
    "[14:32:02] agent loop begin — model: claude-sonnet-5, provider: anthropic",
    "[14:32:15] turn complete — 1 tool call, 2345 input tokens, 456 output tokens"
  ]
}
```

### 3.6 `POST /api/edge/approve`

Responds to an interactive approval card. Sent when the user clicks Approve or Refuse on a tool invocation request.

**Request:**
```json
{
  "id": "appr_xyz789",
  "decision": "allow"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Approval ID from the `approval` SSE event |
| `decision` | string | `allow` or `deny` |

**Response:**
```json
{ "acknowledged": true }
```

### 3.7 `GET /api/edge/media/{id}`

Fetches an agent-generated media artifact (image, audio) by ID.

**Response:** Binary content with appropriate `Content-Type` header (`image/png`, `audio/mpeg`, etc.) and ETag for caching.

**Errors:**
- `404 Not Found` — media ID does not exist or has been garbage-collected
- `403 Forbidden` — media exists but is not accessible to this edge token (multi-tenant deployments)

### 3.8 Approval registry (OPTIONAL)

A server MAY include an approval registry on **every** `GET /api/edge/poll` response, non-destructively (the same pending cards are served to every webview until they are settled):

| Field | Type | Description |
|---|---|---|
| `approvals` | array | Pending approvals. Each entry carries `id` and the `tool`/`summary` fields the widget reads to render the card. |
| `approvals_closed` | object | Map of `{ id: outcome }` for cards that have since been settled. |

A server MAY also accept `POST /api/edge/approval/{id}/seen` (responds `204 No Content`) as a visibility receipt, sent once by a visible, non-preview panel. Servers that only send the `approval` SSE event keep working unchanged.

### 3.9 Turn tracking (OPTIONAL, v1.1)

A long turn can outlive its stream: a connection drops, a webview is suspended or
respawned, and the reply finishes on the server while the widget never sees `done`.
Turn tracking lets the widget notice and fetch the reply from history, which is
always the source of truth.

1. **The stream names its turn.** The first SSE event of a turn is
   `{ "t": "turn", "v": <integer> }` (see §4.0).
2. **Polls report finished turns.** Every `GET /api/edge/poll` response MAY carry:

   ```json
   "edge_turns": { "latest": 9, "done": [7, 8, 9], "unacked": [9], "epoch": "3f2a9c1b7d0e" }
   ```

   | Field | Type | Description |
   |---|---|---|
   | `latest` | integer | The newest turn id the server has started |
   | `done` | array of integer | Recently finished turn ids (a server keeps at least the last 20) |
   | `unacked` | array of integer | Finished turns no widget has acknowledged yet |
   | `epoch` | string | Changes when the server restarts, so ids from different runs never collide |

   A server with turn tracking returns `200` (not `204`) while it has any turn to report.
3. **The widget acknowledges.** `POST /api/edge/turn/{id}/ack` once the turn's reply is
   on screen: `200 {"status": "ok"}`, or `404` if the id is unknown or still running.

**Widget rules (what makes recovery safe):**
- A widget still waiting on a turn listed in `done` (after a short grace) cancels the
  hung stream and loads the reply from history, quietly.
- A **visible, idle** widget that sees a turn in `unacked` past the grace reloads from
  history and then acknowledges it. A hidden or preview webview never acknowledges:
  it must not swallow a reply the real panel never showed.
- The reload **fetches first** and only replaces what is on screen when the fetch
  succeeds. It acknowledges only after a successful render; on failure the turn stays
  unacknowledged and the next poll retries. A failed reload never blanks the panel.

### 3.10 `POST /api/edge/trace` (OPTIONAL, v1.1)

The widget's own event log, so a failure on the display can be diagnosed from the server.

```json
{ "boot": "b-1696761234-x7", "version": "1.3.44",
  "events": [ { "ev": "unacked-due", "ids": "9", "ts": 1696761234567 } ] }
```

- The widget keeps a bounded buffer and sends at most 100 events per request, about
  every 30 seconds; it keeps them for the next try if the request fails.
- Events never contain the token or message text.
- A server bounds what it stores (count, key count, string length) and answers
  `200 {"written": <n>}`. A server without this route can ignore it: the widget treats
  any failure as "try later" and drops the oldest events past its buffer limit.

### 3.11 Message titles (OPTIONAL, v1.1)

A queued poll message MAY carry `title` (plain text), e.g. `"Morning"`; the widget shows
it above the message.

---

## 4. SSE Event Types

The `/api/edge/stream` endpoint emits the following event types. All events carry a JSON payload as the `data` field.

### 4.0 `turn` (v1.1)

The first event of a turn, naming it for turn tracking (§3.9).

```json
{ "t": "turn", "v": 9 }
```

A v1.0 widget ignores it.

### 4.1 `token`

Streaming text content. The widget appends these chunks to the in-flight response bubble.

```json
{ "t": "token", "v": "The Reddit campaign is currently running" }
```

Multiple `token` events arrive per turn. The widget concatenates them in order and renders the full markdown when the turn is complete (`done` event).

### 4.2 `progress`

A tool or background process has started running. The widget displays a status indicator.

```json
{ "t": "progress", "v": "palace_search" }
```

`v` is the tool name. The widget shows "Working…" or the tool name while the tool runs. No user action required.

### 4.3 `approval`

The agent requests permission to execute an action. The widget renders an interactive approval card.

```json
{
  "t": "approval",
  "v": {
    "id": "appr_xyz789",
    "action": "run_shell",
    "details": "git status"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique approval ID — sent back in the `/api/edge/approve` request |
| `action` | string | Tool name (e.g. `run_shell`, `write_file`) |
| `details` | string | Human-readable summary of what the tool will do |

The widget shows Approve and Refuse buttons. The user's decision is sent via `POST /api/edge/approve`. The agent awaits this response — the stream remains open but the turn is paused until a decision arrives.

### 4.4 `done`

The agent has completed its turn. No more events for this message.

```json
{ "t": "done", "v": "" }
```

The widget finalizes the response bubble (renders accumulated markdown) and re-enables the input field.

### 4.5 `error`

The turn encountered an error.

```json
{ "t": "error", "v": "Provider rate limit exceeded. Retry in 12 seconds." }
```

The widget displays the error message inline and re-enables the input. The stream remains open for the next turn.

---

## 5. Widget lifecycle

```
[Widget launch]
  │
  ├─ GET /api/edge/status   ──► populate instruments panel
  ├─ GET /api/edge/history  ──► restore recent messages
  ├─ GET /api/edge/stream   ──► open SSE (held open)
  │
  [User sends message]
  │
  ├─ POST /api/edge/send    ──► { accepted: true }
  │
  [SSE events arrive]
  │
  ├─ progress              ──► "Working…"
  ├─ token × N             ──► append chunks
  ├─ approval              ──► show approve/refuse card
  │    └─ POST /api/edge/approve
  ├─ done                  ──► finalize bubble, render markdown
  │
  [Polling loop, every 5s]
  │
  └─ GET /api/edge/status   ──► update instruments
```

---

## 6. Versioning

This document is versioned independently of the widget and the Tower.

| Protocol version | Minimum Tower version | Minimum Widget version | Notes |
|---|---|---|---|
| **1.0** | — (initial) | v1.3.32 | Initial protocol extraction |
| **1.1** | — | v1.3.44 | Turn tracking (`turn` event, `edge_turns`, ack), widget trace, message titles. All additions are optional: a v1.1 widget works with a v1.0 server, and a v1.0 widget with a v1.1 server. |

**Compatibility:** A widget implementing protocol v1.0 works with any Tower implementing v1.0, regardless of widget UI version or Tower backend. New protocol versions are additive — existing event types and endpoints are not removed within a major version.

---

## 7. Security considerations

1. **Token in transit:** The `X-Edge-Token` is a bearer token. Over HTTP (localhost), it is not encrypted in transit — acceptable because the network boundary is the loopback interface. Over HTTPS (LAN/remote), TLS protects the token.
2. **Token scope:** The edge token grants full access to the edge endpoints only. It does not grant access to administration endpoints (`/api/scheduler`, `/api/compass`).
3. **No credential forwarding:** The widget never receives API keys, provider credentials, or the agent's `.env` contents. The status endpoint reports model and provider names, not keys.
4. **Media access:** The `/api/edge/media/{id}` endpoint should validate that the requested media was generated in a conversation visible to this edge token. In single-tenant deployments, this is trivially true.