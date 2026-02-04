.PHONY: all install dev lint format typecheck test build clean package help

# Default target
all: install lint typecheck test build

# Install dependencies
install:
	uv sync

# Install with dev dependencies
dev:
	uv sync --group dev

# Lint Python code
lint:
	uv run ruff check src/server/

# Format Python code
format:
	uv run ruff format src/server/
	uv run ruff check --fix src/server/

# Type check Python code
typecheck:
	uv run ty check src/server/python/

# Run Python tests
test:
	uv run pytest src/server/python/tests/ -v

# Run TypeScript/Extension tests
test-client:
	npm run pretest && npm test

# Test recording and transcription interactively
test-recording:
	./scripts/test-recording.sh

# Quick extension integration test
test-extension:
	./scripts/test-extension.sh

# Test WebSocket streaming transcription (requires ffmpeg, websocat, running STT server)
test-websocket:
	@echo "Testing WebSocket streaming transcription..."
	@echo "Speak into microphone. Press Ctrl+C to stop."
	@ffmpeg -loglevel quiet -f alsa -i default -ac 1 -ar 16000 -f s16le - | websocat --binary ws://localhost:4445/v1/audio/transcriptions

# Test WebSocket with Spanish language
test-websocket-es:
	@echo "Testing WebSocket streaming (Spanish)..."
	@echo "Habla al micrófono. Pulsa Ctrl+C para parar."
	@ffmpeg -loglevel quiet -f alsa -i default -ac 1 -ar 16000 -f s16le - | websocat --binary "ws://localhost:4445/v1/audio/transcriptions?language=es"

# Compile TypeScript extension
build:
	npm run compile

# Build production package
package: build
	npm run vsce:package

# Watch mode for development
watch:
	npm run watch

# Clean build artifacts
clean:
	rm -rf out/
	rm -rf .venv/
	rm -rf node_modules/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf *.vsix
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Check system dependencies
check-deps:
	@echo "Checking system dependencies..."
	@dpkg -l | grep -q libc++1 && echo "✓ libc++1 installed" || echo "✗ libc++1 NOT installed - run: sudo apt install libc++1"
	@command -v arecord >/dev/null && echo "✓ arecord installed" || echo "✗ arecord NOT installed - run: sudo apt install alsa-utils"
	@command -v docker >/dev/null && echo "✓ docker installed" || echo "✗ docker NOT installed"
	@curl -s http://localhost:4445/health >/dev/null 2>&1 && echo "✓ faster-whisper server running" || echo "✗ faster-whisper server NOT running"

# Install system dependencies (requires sudo)
install-deps:
	sudo apt update && sudo apt install -y libc++1 alsa-utils

# Install STT service (requires sudo)
install-stt:
	./resources/install-stt-service.sh

# Uninstall STT service
uninstall-stt:
	./resources/install-stt-service.sh --uninstall

# Show help
help:
	@echo "CodeWhisper - Voice-to-text extension with WebSocket streaming"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install         Install production dependencies"
	@echo "  dev             Install with dev dependencies"
	@echo "  lint            Run ruff linter"
	@echo "  format          Format code with ruff"
	@echo "  typecheck       Run ty type checker"
	@echo "  test            Run pytest tests"
	@echo "  test-client     Run TypeScript extension tests"
	@echo "  test-recording  Test microphone recording and transcription"
	@echo "  test-websocket  Test WebSocket streaming (requires ffmpeg, websocat)"
	@echo "  test-websocket-es  Test WebSocket streaming in Spanish"
	@echo "  build           Compile TypeScript extension"
	@echo "  package         Build VSIX package"
	@echo "  watch           Watch mode for development"
	@echo "  clean           Remove build artifacts"
	@echo "  install-stt     Install faster-whisper Docker service"
	@echo "  uninstall-stt   Uninstall faster-whisper service"
	@echo "  help            Show this help"
