# Changelog

All notable changes to the Xeneon Edge Companion widget will be documented in this file.

## [1.4.1] - 2026-10-08
- Settings changed in iCUE after the token arrived now take effect (the Tower URL used to stay at its default).

## [1.4.0] - 2026-10-08
### Added
- **Skins**: the widget now takes its whole look from a skin: colours, fonts, the portrait, the icon and its words. A skin is data only (no script, no CSS text, no SVG), described in `skins/SCHEMA.md`. `build.py --skin <folder>` validates a skin and packs one `.icuewidget` per skin; a skin can live outside this repository.
- **Two skins ship here:** `aedelgard` (gold on dark, the keystone and its kept flame; JetBrains Mono and Schibsted Grotesk when installed, system fonts otherwise) and `galadriel` (the silver look the widget was born with, minus anything personal).
### Changed
- `index.html` is now a neutral template: every tinted colour goes through a skin variable, every name and phrase through a `data-skin` element filled with `textContent`. Rendered with a skin that carries the previous values, the widget is pixel-identical to 1.3.44 outside a recompressed portrait.
- `build.sh` is replaced by `build.py`. The package id is now `com.aedelgard.edge.<skin>`, so iCUE treats each skin as its own widget.

## [1.3.44] - 2026-10-08
Brings this repository level with the reference build (1.3.37–1.3.43 were not published separately). Implements Edge Protocol v1.1; every addition is optional, so v1.0 servers keep working.
### Fixed
- **Turn recovery**: a reply that finishes on the server while the stream hangs or drops (long tool-heavy turns, a suspended webview) is now fetched from history instead of never appearing. The stream names its turn; polls report finished turns.
- **A recovery never blanks the panel**: the reload fetches history first and only replaces the messages when the fetch succeeds; the turn is acknowledged only after a successful render, so a failed reload is retried on the next poll.
- **Reply order**: after a turn that raised approval cards, the finished reply moves below the settled cards (still above any pending card).
### Added
- **Acknowledged turns**: the widget acknowledges each reply it showed; a visible, idle widget picks up finished turns no widget acknowledged (e.g. after the webview was respawned). Hidden webviews never acknowledge.
- **Widget trace**: a bounded event log, sent to the Tower every 30 s (`POST /api/edge/trace`), never containing the token or message text.
- **Folded cards**: a settled approval card folds to one line; click to expand.
- **Message titles**: a queued message may carry a title, shown above it.
- **Tests**: turn recovery, acknowledgement, reload safety and card order.

## [1.3.36] - 2026-10-05
### Fixed
- **Approval cards pinned to the bottom**: a pending approval card now always sits at the end of the thread, so replies, streamed replies, dead drops and knocks render above it instead of hiding it. Opening a card closes any open overlay (Status/Logs/Diag, media, link sheet) so it is never hidden.
- **Non-destructive approval registry**: the widget now consumes the Tower's `approvals` / `approvals_closed` fields on every poll, renders each pending card once, sends a single seen-receipt from a visible (non-preview) panel, and settles closed cards with an honest outcome — a timeout is reported as "timed out, nothing ran", never as denied.

## [1.3.35] - 2026-10-04
### Fixed
- **Late settings injection**: iCUE can inject the Edge Token after every boot-time re-read without firing an event, leaving the widget with an empty token (every request refused). The widget now re-reads its settings every 2 s while the token is missing, and trims whitespace from the token and Tower URL.
- **Connection probe**: the SETTINGS row now probes the Tower (`/api/edge/status`) and reports `conn ✓`, `conn ✗` (rejected) or `conn ✗` (unreachable), instead of only checking that a token is present.
- **Thinking state**: every live stream event (tool progress, text) re-lights the thinking animation if an idle watchdog switched it off mid-turn. The animation itself is unchanged.
### Added
- **Selection copy chip**: iCUE swallows Ctrl+C. Mark text in the chat or in the Status/Diag/Logs panel and a copy chip appears; one click copies it.
- **Diag**: reports whether the OS reduced-motion setting is on.
- **Tests**: `tests/` (pytest + Node.js).

## [1.3.34] - 2026-10-01
### Fixed
- **iCUE delivery diagnostic**: a Diag panel reports exactly what iCUE injected (the token value is never printed); SDK-documented late-load guard; spec-exact single-line property metas; required `min_app_version`.

## [1.3.33] - 2026-10-01
### Fixed
- **Two-pass property read**: a value injected as a top-level lexical global is now found (window property first, then a bare-identifier lookup), with delayed boot re-reads and a visible SETTINGS readout.

## [1.3.32] - 2026-09-18
### Fixed
- **Topbar Clock Layout Containment**: Replaced `contain: strict` with `contain: layout style` and explicit dimensions (`width: 120px; height: 24px; line-height: 24px`) on `#topbar-time`. In Chromium, `contain: strict` enforces size containment without a default height, collapsing the element to 0px height and clipping it under paint containment. The timestamp now renders crisply while remaining isolated from surrounding layouts.

## [1.3.31] - 2026-09-17
### Performance & Stability
- **Multi-Monitor GPU Layer Isolation**: Implemented `contain: layout style`, `transform: translateZ(0)`, and `backface-visibility: hidden` across primary layout panels (`#main`, `#left-panel`, `#chat-panel`, `#footer`). Eliminates periodic webview stutter/flicker caused by Windows DWM and GPU video decode clock transitions when watching video on primary displays.
- **Debounced Textarea Auto-Resize**: Replaced per-keystroke height resets with thresholded recalculations to eliminate synchronous DOM reflows and chat stutter while typing.
- **Clock String Comparison**: Avoids touching DOM innerText if the current second has not rolled over.

## [1.3.30] - 2026-09-15
### Changed
- Enlarged status and log inspection typography for high-DPI ultrawide viewing.
- Restyled command buttons for enhanced visibility.

## [1.3.28] - 2026-09-12
### Added
- 1-click code block and snippet copying with themed notification pill.

## [1.3.27] - 2026-09-10
### Fixed
- Chronological ordering of interactive tool approval cards before in-flight assistant replies.

## [1.3.26] - 2026-09-08
### Fixed
- Streamlined streaming bubble cursor flow and prevented mid-stream poll races from interrupting active replies.

## [1.3.21] - 2026-09-06
### Added
- Text selection and marking enabled inside chat bubbles with themed copy handler.

## [1.3.20] - 2026-09-06
### Performance
- **Still Water**: Portrait breathing animation migrated from CSS drop-shadow filters to GPU opacity/transform; idle rings rest and spin only during active thinking/streaming.
