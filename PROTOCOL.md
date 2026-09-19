# Edge Protocol v1.0

**A lightweight HTTP/SSE protocol for peripheral AI agent displays.**

The Edge Protocol is a contract between an AI agent backend (the *Tower*) and a peripheral display surface (the *Widget*). It is designed for secondary screens, desktop panels, Stream Deck layouts, e-ink status displays, and any hardware that benefits from a live window into a persistent agent.

This document is the canonical specification. It is implementation-agnostic — nothing here depends on iCUE, Corsair, or any specific widget UI.

---

## 1. Transport

- **Protocol:** HTTPS (production) or HTTP (localhost development)
- **Event streaming:** Server-Sent Events (`text/event-stream`)
- **Other requests:** JSON over HTTP, standard `Content-Type: application/json`

All responses carry `X-Protocol-Version: 1.0`.

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

---

## 4. SSE Event Types

The `/api/edge/stream` endpoint emits the following event types. All events carry a JSON payload as the `data` field.

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

**Compatibility:** A widget implementing protocol v1.0 works with any Tower implementing v1.0, regardless of widget UI version or Tower backend. New protocol versions are additive — existing event types and endpoints are not removed within a major version.

---

## 7. Security considerations

1. **Token in transit:** The `X-Edge-Token` is a bearer token. Over HTTP (localhost), it is not encrypted in transit — acceptable because the network boundary is the loopback interface. Over HTTPS (LAN/remote), TLS protects the token.
2. **Token scope:** The edge token grants full access to the edge endpoints only. It does not grant access to administration endpoints (`/api/scheduler`, `/api/compass`).
3. **No credential forwarding:** The widget never receives API keys, provider credentials, or the agent's `.env` contents. The status endpoint reports model and provider names, not keys.
4. **Media access:** The `/api/edge/media/{id}` endpoint should validate that the requested media was generated in a conversation visible to this edge token. In single-tenant deployments, this is trivially true.