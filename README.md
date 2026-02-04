# ECodeWhisper

Real-time voice-to-text for VS Code and Cursor. Speak and see your words appear instantly as you talk.

Uses [WhisperLive](https://github.com/collabora/WhisperLive) as the speech-to-text backend with [TEN VAD](https://github.com/TEN-framework/ten-vad) for automatic silence detection.

## Quick Start

1. Install the extension
2. Start your WhisperLive server (see [Server Setup](#server-setup))
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
| `ecodewhisper.whisperEndpoint` | `ws://localhost:9090` | WhisperLive WebSocket server URL |
| `ecodewhisper.language` | `en` | Language code (`en`, `es`, `fr`, etc.) |
| `ecodewhisper.model` | `small` | Whisper model (`tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`) |
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
    "ecodewhisper.whisperEndpoint": "ws://localhost:9090",
    "ecodewhisper.language": "es",
    "ecodewhisper.model": "large-v3"
}
```

## Requirements

- **Linux** (Ubuntu 22.04+)
- **Python 3.12+** with dependencies (auto-installed)
- **ALSA** audio (`sudo apt install alsa-utils`)
- **WhisperLive server** running with NVIDIA GPU (see below)

## Server Setup

You need a running WhisperLive server. The extension includes an installer:

```bash
# From extension directory
./stt/install.sh --model small --language en --port 9090
```

Or manually with Docker:

```bash
docker run -d --gpus all -p 9090:9090 \
  ghcr.io/collabora/whisperlive-gpu:latest
```

For a specific model:

```bash
docker run -d --gpus all -p 9090:9090 \
  -e WHISPER_MODEL=large-v3 \
  ghcr.io/collabora/whisperlive-gpu:latest
```

Verify it's running:

```bash
docker ps | grep stt
docker logs stt
```

## Troubleshooting

**"Cannot connect to server"**
```bash
docker ps | grep stt                # Check if container running
docker logs stt                     # Check server logs
python -c "import socket; s=socket.socket(); s.connect(('localhost', 9090)); print('OK')"
```

**"No speech detected"**
- Test microphone: `arecord -d 3 test.wav && aplay test.wav`
- Lower `vadThreshold` for quiet voices
- Check `alsamixer` for input levels

**"Server timeout"**
- First connection downloads the model (~3GB for large-v3)
- Wait for model download to complete
- Check logs: `docker logs -f stt`

**Text not appearing**
- Check Output panel: View → Output → ECodeWhisper
- Verify Python path in settings

## License

MIT

## Credits

- [WhisperLive](https://github.com/collabora/WhisperLive) by Collabora
- [TEN VAD](https://github.com/TEN-framework/ten-vad)
