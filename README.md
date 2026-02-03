# ECodeWhisper

Eager Code Whisper - Voice-to-text extension for VS Code and Cursor using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with [TEN VAD](https://github.com/TEN-framework/ten-vad) for automatic silence detection.

## Features

- **Real-time transcription**: Stream audio to faster-whisper server via HTTP API
- **Smart silence detection**: TEN VAD automatically stops recording after configurable silence duration
- **Low latency**: Optimized Python backend with async I/O
- **Local processing**: All transcription happens on your machine - no cloud services
- **Partial results**: See transcription as you speak (configurable)
- **Auto-insert**: Automatically insert transcription at cursor position

## Project Structure

```
e-codewhisper/
├── src/
│   ├── client/
│   │   └── extension.ts          # TypeScript VS Code extension
│   └── server/
│       └── python/
│           └── codewhisper.py    # Python backend with TEN VAD
├── resources/
│   ├── compose.yml               # Docker compose for faster-whisper
│   └── install-stt-service.sh    # Systemd service installer
├── images/
│   └── codewhisper.svg           # Extension icon
├── out/                          # Compiled extension (generated)
├── package.json                  # VS Code extension manifest
├── pyproject.toml                # Python dependencies (uv)
├── tsconfig.json                 # TypeScript config
└── README.md                     # Documentation
```

## Requirements

### System Requirements

- **OS**: Linux (Ubuntu 22.04+ recommended)
- **Python**: 3.12 or higher
- **Audio**: ALSA (`arecord` command available)
- **GPU**: NVIDIA GPU with CUDA support (for faster-whisper server)

### Dependencies

- [faster-whisper-server](https://github.com/fedirz/faster-whisper-server) (Docker)
- [TEN VAD](https://github.com/TEN-framework/ten-vad) (Python package)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

### 1. Install Python Dependencies

Using uv (recommended):

```bash
cd ~/.vscode/extensions/codewhisper-*  # or ~/.cursor/extensions/codewhisper-*
uv sync
```

Or using pip:

```bash
pip install numpy httpx
pip install git+https://github.com/TEN-framework/ten-vad.git
```

### 2. Install faster-whisper Server (Optional - Automated)

The extension includes an automated installer for the faster-whisper Docker service:

```bash
# Make script executable
chmod +x resources/install-stt-service.sh

# Install with defaults (small model, English)
./resources/install-stt-service.sh

# Or customize installation
./resources/install-stt-service.sh \
    --model large-v3 \
    --language es \
    --port 4445 \
    --device cuda
```

This will:
1. Create `~/.automation/stt/compose.yml`
2. Create systemd service `automation-stt`
3. Start the service automatically on boot

#### Manual Installation

If you prefer manual installation:

```bash
# Create directory
mkdir -p ~/.automation/stt/models
cd ~/.automation/stt

# Copy compose file
cp /path/to/codewhisper/resources/compose.yml .

# Start service
docker compose up -d

# Check logs
docker logs -f codewhisper-stt
```

#### Systemd Service (Manual)

Create `/etc/systemd/system/automation-stt.service`:

```ini
[Unit]
Description=Faster Whisper for IDEs
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/.automation/stt
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

Then enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable automation-stt
sudo systemctl start automation-stt
```

### 3. Verify Installation

```bash
# Check service health
curl http://localhost:4445/health

# Test transcription endpoint
curl http://localhost:4445/v1/models
```

## Usage

### Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|--------------|-------|
| Toggle Recording | `Ctrl+Shift+Space` | `Cmd+Shift+Space` |
| Cancel Recording | `Escape` | `Escape` |

### Recording Flow

1. Press `Ctrl+Shift+Space` to start recording
2. Speak your text
3. Recording stops automatically when:
   - VAD detects silence (configurable duration)
   - You press `Ctrl+Shift+Space` again
   - You press `Escape` to cancel
4. Transcription is inserted at cursor position (or copied to clipboard)

### Status Bar

The status bar shows the current state:
- 🎤 **CodeWhisper** - Ready to record
- ⏺️ **Recording...** - Actively recording
- 🔄 **Transcribing...** - Processing audio
- 🔄 **Connecting...** - Connecting to server

## Configuration

Open VS Code/Cursor settings and search for "CodeWhisper":

| Setting | Default | Description |
|---------|---------|-------------|
| `codewhisper.pythonPath` | `python3` | Path to Python 3.12+ interpreter |
| `codewhisper.whisperEndpoint` | `http://localhost:4445/v1/audio/transcriptions` | HTTP API endpoint |
| `codewhisper.model` | `small` | Whisper model (tiny, base, small, medium, large-v2, large-v3) |
| `codewhisper.language` | `en` | Language code (en, es, fr, etc.) |
| `codewhisper.vadSilenceThreshold` | `1.5` | Seconds of silence before auto-stop (0.3-5.0) |
| `codewhisper.vadThreshold` | `0.5` | VAD probability threshold (0.1-0.9) |
| `codewhisper.autoInsert` | `true` | Auto-insert at cursor position |
| `codewhisper.showPartialResults` | `true` | Show partial transcriptions |

### Example settings.json

```json
{
    "codewhisper.model": "large-v3",
    "codewhisper.language": "es",
    "codewhisper.vadSilenceThreshold": 2.0,
    "codewhisper.autoInsert": true
}
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   VS Code/      │     │   Python Backend │     │  faster-whisper     │
│   Cursor        │────▶│   (codewhisper)  │────▶│  Server (Docker)    │
│   Extension     │     │   + TEN VAD      │     │  HTTP API           │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
       │                        │
       │ spawn process          │ audio capture
       │ JSON messages          │ VAD processing
       └────────────────────────┘
```

### Components

1. **TypeScript Extension** (`src/client/extension.ts`)
   - VS Code integration
   - Status bar management
   - Configuration handling
   - Spawns Python process

2. **Python Backend** (`src/server/python/codewhisper.py`)
   - Audio capture via `arecord`
   - TEN VAD for voice activity detection
   - HTTP API client for faster-whisper server (OpenAI-compatible)
   - JSON message protocol with extension

3. **faster-whisper Server** (Docker)
   - GPU-accelerated transcription
   - OpenAI-compatible API

## Troubleshooting

### "Cannot connect to faster-whisper server"

```bash
# Check if container is running
docker ps | grep codewhisper-stt

# Check logs
docker logs codewhisper-stt

# Restart service
sudo systemctl restart automation-stt
```

### "ten-vad not installed"

```bash
pip install git+https://github.com/TEN-framework/ten-vad.git
```

### "arecord: command not found"

```bash
sudo apt install alsa-utils
```

### "No speech detected"

- Check microphone permissions
- Increase `vadThreshold` if getting false negatives
- Decrease `vadThreshold` if not detecting quiet speech
- Test microphone: `arecord -d 3 test.wav && aplay test.wav`

### High latency

- Use smaller model (`tiny` or `base`)
- Ensure GPU is being used (check `WHISPER_DEVICE=cuda`)
- Check GPU memory with `nvidia-smi`

## Development

Use `make` for common tasks:

```bash
make help          # Show all available commands
make dev           # Install with dev dependencies
make build         # Compile TypeScript extension
make test          # Run Python tests
make lint          # Run ruff linter
make format        # Format code with ruff
make typecheck     # Run ty type checker
make package       # Build VSIX package
make clean         # Remove build artifacts
```

### Manual Commands

```bash
# Install Node.js dependencies
npm install

# Compile TypeScript
npm run compile

# Package extension
npm run vsce:package
```

### Python Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run pytest src/server/python/tests/ -v

# Type checking
uv run ty check src/server/python/

# Linting
uv run ruff check src/server/python/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) - CTranslate2-based Whisper implementation
- [faster-whisper-server](https://github.com/fedirz/faster-whisper-server) - OpenAI-compatible API server
- [TEN VAD](https://github.com/TEN-framework/ten-vad) - Low-latency voice activity detector
- [WhisperX Assistant](https://github.com/mwhesse/whisperx-assistant-vscode) - Inspiration for VS Code integration
