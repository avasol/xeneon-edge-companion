# Changelog

All notable changes to the Xeneon Edge Companion widget will be documented in this file.

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
