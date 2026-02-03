#!/usr/bin/env bash
#
# Quick test for CodeWhisper extension without opening VS Code
# Tests the Python backend integration
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== ECodeWhisper Extension Quick Test ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }

# 1. Check extension is installed
echo "1. Checking extension installation..."
EXT_DIR=$(ls -d ~/.cursor/extensions/damvolkov.ecodewhisper-* 2>/dev/null | head -1)
if [[ -d "$EXT_DIR" ]]; then
    pass "Extension installed in Cursor: $(basename "$EXT_DIR")"
else
    fail "Extension NOT installed"
    echo "   Run: make package && cursor --install-extension ecodewhisper-*.vsix"
fi

# 2. Check Python script in installed extension
echo ""
echo "2. Checking Python script..."
INSTALLED_SCRIPT="$EXT_DIR/src/server/python/codewhisper.py"
if [[ -n "$EXT_DIR" && -f "$INSTALLED_SCRIPT" ]]; then
    pass "Python script exists"
else
    fail "Python script NOT found"
fi

# 3. Check compiled extension.js
echo ""
echo "3. Checking compiled extension..."
if [[ -n "$EXT_DIR" && -f "$EXT_DIR/out/extension.js" ]]; then
    pass "extension.js exists"
else
    fail "extension.js NOT found"
fi

# 4. Test Python with project venv
echo ""
echo "4. Testing Python with project venv..."
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ -f "$VENV_PYTHON" ]]; then
    if $VENV_PYTHON -c "from src.server.python.codewhisper import Config, emit; print('OK')" 2>/dev/null; then
        pass "Python imports work with venv"
    else
        fail "Python imports failed"
    fi
else
    fail "Venv not found at $VENV_PYTHON"
fi

# 5. Test Python with system python
echo ""
echo "5. Testing Python with system python3..."
if python3 -c "import numpy" 2>/dev/null; then
    pass "System Python has numpy"
else
    warn "System Python missing numpy (need to configure pythonPath)"
fi

# 6. Check settings recommendation
echo ""
echo "6. Recommended Cursor settings:"
echo ""
echo '   Add to settings.json:'
echo '   {'
echo "       \"ecodewhisper.pythonPath\": \"$VENV_PYTHON\""
echo '   }'
echo ""

# 7. Test faster-whisper server
echo "7. Checking faster-whisper server..."
if curl -s http://localhost:4445/health >/dev/null 2>&1; then
    pass "Server running at localhost:4445"
else
    fail "Server NOT running"
    echo "   Run: make install-stt"
fi

# 8. Simulate what the extension does
echo ""
echo "8. Simulating extension Python call..."
echo "   (This is what happens when you press Ctrl+Shift+Space)"
echo ""

timeout 3 $VENV_PYTHON "$PROJECT_DIR/src/server/python/codewhisper.py" \
    --endpoint http://localhost:4445/v1/audio/transcriptions \
    --model small \
    --language es \
    --vad-silence 0.5 \
    --vad-threshold 0.5 2>&1 &

PID=$!
sleep 0.5

# Check if it started
if kill -0 $PID 2>/dev/null; then
    pass "Python process started successfully"
    echo ""
    echo "   Output (first 2 seconds):"
    sleep 2
    kill $PID 2>/dev/null || true
else
    fail "Python process failed to start"
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "If tests pass but extension doesn't work:"
echo "1. Reload Cursor: Ctrl+Shift+P -> 'Developer: Reload Window'"
echo "2. Check Output panel: View -> Output -> Select 'CodeWhisper'"
echo "3. Ensure pythonPath is configured correctly"
