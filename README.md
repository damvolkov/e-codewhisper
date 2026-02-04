# ECodeWhisper

Real-time voice-to-text for VS Code and Cursor. Speak and see your words appear instantly as you talk.

Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) via WebSocket streaming with [TEN VAD](https://github.com/TEN-framework/ten-vad) for automatic silence detection.

## Quick Start

1. Install the extension
2. Start your faster-whisper server (see [Server Setup](#server-setup))
3. Press `Ctrl+Shift+E` and start speaking
4. Text appears in real-time as you talk

## Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Toggle Recording | `Ctrl+Shift+E` | `Cmd+Shift+E` |
| Cancel Recording | `Escape` | `Escape` |

## How It Works

1. Press `Ctrl+Shift+E` to start
2. Speak naturally
3. Recording stops automatically when you pause (VAD silence detection)
4. Or press `Ctrl+Shift+E` again to stop manually
5. Text is inserted at cursor position

## Status Bar

| Icon | State |
|------|-------|
| 🎤 ECodeWhisper | Ready |
| ⏺️ 0:05 | Recording (with timer) |
| 🔄 Finishing... | Processing final transcription |

## Settings

Open Settings (`Ctrl+,`) and search for "ecodewhisper":

| Setting | Default | Description |
|---------|---------|-------------|
| `ecodewhisper.whisperEndpoint` | `ws://localhost:4445/v1/audio/transcriptions` | WebSocket server URL |
| `ecodewhisper.language` | `es` | Language code (`en`, `es`, `fr`, etc.) |
| `ecodewhisper.model` | `` | Whisper model (leave empty for server default) |
| `ecodewhisper.vadSilenceThreshold` | `1.5` | Seconds of silence before auto-stop (0.3-10) |
| `ecodewhisper.vadThreshold` | `0.5` | Voice detection sensitivity (0.1-0.9) |
| `ecodewhisper.minRecordingTime` | `1.0` | Minimum recording time before VAD can stop |
| `ecodewhisper.autoInsert` | `true` | Insert text at cursor position |
| `ecodewhisper.streamingInsert` | `true` | Show text in real-time while speaking |
| `ecodewhisper.showPartialResults` | `true` | Show partial transcriptions in status bar |
| `ecodewhisper.pythonPath` | `python3` | Python 3.12+ interpreter path |

### Example Configuration

```json
{
    "ecodewhisper.language": "en",
    "ecodewhisper.vadSilenceThreshold": 2.0,
    "ecodewhisper.streamingInsert": true
}
```

## Requirements

- **Linux** (Ubuntu 22.04+)
- **Python 3.12+** with dependencies (auto-installed)
- **ALSA** audio (`sudo apt install alsa-utils`)
- **faster-whisper server** running (see below)

## Server Setup

You need a running faster-whisper server. The extension includes an installer:

```bash
# From extension directory
./stt/install.sh --model large-v3 --language es --port 4445
```

Or manually with Docker:

```bash
docker run -d --gpus all -p 4445:8000 \
  -e WHISPER__MODEL=Systran/faster-whisper-large-v3 \
  -e WHISPER__LANGUAGE=es \
  fedirz/faster-whisper-server:latest-cuda
```

Verify it's running:

```bash
curl http://localhost:4445/health
```

## Troubleshooting

**"Cannot connect to server"**
```bash
curl http://localhost:4445/health  # Should return OK
docker ps | grep stt               # Check if container running
```

**"No speech detected"**
- Test microphone: `arecord -d 3 test.wav && aplay test.wav`
- Lower `vadThreshold` for quiet voices
- Check `alsamixer` for input levels

**Text not appearing**
- Check Output panel: View → Output → ECodeWhisper
- Verify Python path in settings

## License

MIT

## Credits

- [faster-whisper-server](https://github.com/fedirz/faster-whisper-server) (speaches)
- [TEN VAD](https://github.com/TEN-framework/ten-vad)
