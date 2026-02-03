#!/usr/bin/env bash
#
# Test script for CodeWhisper Python backend
# Tests audio recording and VAD without the VS Code extension
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== CodeWhisper Test Script ==="
echo ""

# Check dependencies
echo "1. Checking dependencies..."
echo ""

check_dep() {
    if command -v "$1" &>/dev/null; then
        echo "   ✓ $1"
        return 0
    else
        echo "   ✗ $1 NOT FOUND"
        return 1
    fi
}

check_dep python3
check_dep arecord

echo ""
echo "   Checking libc++1..."
if dpkg -l 2>/dev/null | grep -q libc++1; then
    echo "   ✓ libc++1"
else
    echo "   ✗ libc++1 NOT INSTALLED"
    echo "     Run: sudo apt install libc++1"
fi

echo ""
echo "   Checking faster-whisper server..."
if curl -s http://localhost:4445/health &>/dev/null; then
    echo "   ✓ Server running at localhost:4445"
else
    echo "   ✗ Server NOT running at localhost:4445"
    echo "     Run: ./resources/install-stt-service.sh"
fi

echo ""
echo "2. Testing Python imports..."
uv run python -c "
from src.server.python.codewhisper import Config, emit, AudioRecorder
print('   ✓ Core imports OK')
"

echo ""
echo "3. Testing TEN VAD import..."
uv run python -c "
try:
    from ten_vad import TenVad
    print('   ✓ TEN VAD import OK')
except OSError as e:
    print(f'   ✗ TEN VAD failed: {e}')
    print('     Run: sudo apt install libc++1')
"

echo ""
echo "4. Testing audio recording (3 seconds)..."
echo "   Speak into your microphone..."
timeout 3 arecord -f S16_LE -c 1 -r 16000 -t wav /tmp/codewhisper-test.wav 2>/dev/null || true

if [[ -f /tmp/codewhisper-test.wav ]]; then
    SIZE=$(stat -c%s /tmp/codewhisper-test.wav)
    echo "   ✓ Recorded ${SIZE} bytes to /tmp/codewhisper-test.wav"
    echo "   Play back with: aplay /tmp/codewhisper-test.wav"
else
    echo "   ✗ Recording failed"
fi

echo ""
echo "5. Full integration test (speak and transcribe)..."
echo "   This will record until you stop speaking (VAD)"
echo "   Press Ctrl+C to cancel"
echo ""
read -p "   Press Enter to start recording..." 

echo ""
echo "   Recording... (speak now, stops on silence)"
uv run python src/server/python/codewhisper.py \
    --endpoint http://localhost:4445/v1/audio/transcriptions \
    --model small \
    --language es \
    --vad-silence 1.5 \
    --vad-threshold 0.5

echo ""
echo "=== Test complete ==="
