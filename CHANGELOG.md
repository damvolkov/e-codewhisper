# Changelog

All notable changes to ECodeWhisper will be documented in this file.

## [0.3.2] - 2026-02-04

### Changed

- Simplified README focused on extension usage
- Cleaner documentation

## [0.3.1] - 2026-02-04

### Added

- WebSocket streaming for real-time transcription
- Text appears as you speak (on the fly)
- `streamingInsert` setting for real-time text insertion
- `make test-websocket` and `make test-websocket-es` commands

### Changed

- Default endpoint now uses WebSocket (`ws://`) instead of HTTP
- Default language changed to Spanish (`es`)
- Model setting now accepts any model string (server default if empty)
- VAD silence threshold maximum increased to 10 seconds
- Replaced `httpx` with `websockets` library

### Fixed

- Streaming partial results now update in-place in editor

## [0.3.0] - 2026-02-04

### Added

- Initial stable release with HTTP API

## [0.1.0] - 2026-02-02

### Added

- Initial release
- TEN VAD integration for automatic silence detection
- Status bar with recording state indicators
- Keyboard shortcuts (`Ctrl+Shift+E` to toggle, `Escape` to cancel)
- Auto-insert transcription at cursor position
- Docker-based faster-whisper server installation script
