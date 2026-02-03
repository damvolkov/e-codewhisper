# Changelog

All notable changes to CodeWhisper will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-02-02

### Added

- Initial release
- Real-time voice transcription with faster-whisper WebSocket API
- TEN VAD integration for automatic silence detection
- Configurable VAD silence threshold and sensitivity
- Status bar integration with recording state indicators
- Keyboard shortcuts (`Ctrl+Shift+Space` to toggle, `Escape` to cancel)
- Auto-insert transcription at cursor position
- Partial transcription display while speaking
- Docker-based faster-whisper server installation script
- Systemd service configuration for automatic startup
- Support for multiple Whisper models (tiny to large-v3)
- Multi-language transcription support

### Technical

- Async Python backend with WebSocket streaming
- Minimal TypeScript client based on WhisperX Assistant architecture
- TEN VAD for low-latency voice activity detection
- JSON message protocol between extension and Python process
