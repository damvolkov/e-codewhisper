"""Tests for codewhisper module."""

from __future__ import annotations

import io
import json
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.server.python.codewhisper import (
    AudioRecorder,
    Config,
    emit,
    transcribe_audio,
)


# --- Config tests ---


def test_config_defaults() -> None:
    """Test Config with default hop_size."""
    config = Config(
        endpoint="http://localhost:4445",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
    )
    assert config.hop_size == 256
    assert config.endpoint == "http://localhost:4445"
    assert config.model == "small"


def test_config_custom_hop_size() -> None:
    """Test Config with custom hop_size."""
    config = Config(
        endpoint="http://localhost:4445",
        model="large-v3",
        language="es",
        vad_silence_threshold=2.0,
        vad_threshold=0.6,
        sample_rate=16000,
        hop_size=160,
    )
    assert config.hop_size == 160


def test_config_immutable() -> None:
    """Test that Config is immutable (frozen)."""
    config = Config(
        endpoint="http://localhost:4445",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
    )
    with pytest.raises(AttributeError):
        config.model = "base"  # type: ignore[misc]


# --- emit tests ---


def test_emit_basic(capsys: pytest.CaptureFixture[str]) -> None:
    """Test emit outputs valid JSON."""
    emit("ready")
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data == {"type": "ready"}


def test_emit_with_text(capsys: pytest.CaptureFixture[str]) -> None:
    """Test emit with text parameter."""
    emit("partial", text="hello world")
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data == {"type": "partial", "text": "hello world"}


def test_emit_filters_none(capsys: pytest.CaptureFixture[str]) -> None:
    """Test emit filters out None values."""
    emit("final", text="result", error=None)
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data == {"type": "final", "text": "result"}
    assert "error" not in data


def test_emit_unicode(capsys: pytest.CaptureFixture[str]) -> None:
    """Test emit handles unicode correctly."""
    emit("partial", text="こんにちは 你好 مرحبا")
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["text"] == "こんにちは 你好 مرحبا"


# --- VoiceActivityDetector tests (with mocked TenVad) ---


@pytest.fixture
def vad_config() -> Config:
    """Create config for VAD tests."""
    return Config(
        endpoint="http://localhost:4445",
        model="small",
        language="en",
        vad_silence_threshold=1.0,
        vad_threshold=0.5,
        sample_rate=16000,
        hop_size=256,
    )


def test_vad_init(vad_config: Config) -> None:
    """Test VAD initialization with mocked TenVad."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        MockTenVad.return_value = MagicMock()
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        
        # max_silence_frames = 1.0 * 16000 / 256 = 62.5 -> 62
        assert vad._max_silence_frames == 62
        assert vad._has_speech is False
        assert vad._silence_frames == 0
        MockTenVad.assert_called_once_with(hop_size=256, threshold=0.5)


def test_vad_process_voice_detected(vad_config: Config) -> None:
    """Test VAD when voice is detected."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        mock_vad_instance = MagicMock()
        # TenVad.process() returns (probability, flags) where flags=1 means speech
        mock_vad_instance.process.return_value = (0.8, 1)
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        
        audio = np.zeros(256, dtype=np.int16)
        is_voice, should_stop = vad.process(audio)
        
        assert is_voice is True
        assert should_stop is False
        assert vad._has_speech is True
        assert vad._silence_frames == 0


def test_vad_process_silence_after_speech(vad_config: Config) -> None:
    """Test VAD stops after silence following speech."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        mock_vad_instance = MagicMock()
        # flags=0 means no speech
        mock_vad_instance.process.return_value = (0.1, 0)
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        vad._has_speech = True
        vad._silence_frames = 61  # One frame before max
        
        audio = np.zeros(256, dtype=np.int16)
        is_voice, should_stop = vad.process(audio)
        
        assert is_voice is False
        assert should_stop is True  # Reached max silence frames
        assert vad._silence_frames == 62


def test_vad_no_stop_without_prior_speech(vad_config: Config) -> None:
    """Test VAD doesn't stop on silence without prior speech."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        mock_vad_instance = MagicMock()
        mock_vad_instance.process.return_value = (0.1, 0)
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        vad._silence_frames = 100  # Way over threshold but no speech yet
        
        audio = np.zeros(256, dtype=np.int16)
        is_voice, should_stop = vad.process(audio)
        
        assert is_voice is False
        assert should_stop is False  # No speech detected yet
        assert vad._has_speech is False


def test_vad_reset(vad_config: Config) -> None:
    """Test VAD reset."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        MockTenVad.return_value = MagicMock()
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        vad._has_speech = True
        vad._silence_frames = 50
        
        vad.reset()
        
        assert vad._has_speech is False
        assert vad._silence_frames == 0


# --- AudioRecorder tests ---


@pytest.fixture
def recorder_config() -> Config:
    """Create config for recorder tests."""
    return Config(
        endpoint="http://localhost:4445",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        hop_size=256,
    )


def test_recorder_get_wav_bytes(recorder_config: Config) -> None:
    """Test raw PCM to WAV conversion."""
    recorder = AudioRecorder(recorder_config)

    # Create 1 second of silence (16000 samples * 2 bytes)
    raw_audio = b"\x00" * 32000

    wav_bytes = recorder.get_wav_bytes(raw_audio)

    # Verify WAV header
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

    # Parse and verify WAV properties
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000  # 1 second of audio


def test_recorder_get_wav_bytes_empty(recorder_config: Config) -> None:
    """Test WAV conversion with empty audio."""
    recorder = AudioRecorder(recorder_config)

    wav_bytes = recorder.get_wav_bytes(b"")

    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, "rb") as wf:
        assert wf.getnframes() == 0


# --- transcribe_audio tests ---


@pytest.fixture
def transcribe_config() -> Config:
    """Create config for transcription tests."""
    return Config(
        endpoint="http://localhost:4445/v1/audio/transcriptions",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
    )


@pytest.mark.asyncio
async def test_transcribe_audio_success(transcribe_config: Config) -> None:
    """Test successful transcription."""
    wav_data = b"RIFF" + b"\x00" * 100  # Fake WAV

    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "hello world"}
    mock_response.raise_for_status = MagicMock()

    with patch("src.server.python.codewhisper.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        result = await transcribe_audio(transcribe_config, wav_data)

        assert result == "hello world"
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_audio_ws_to_http_conversion() -> None:
    """Test WebSocket URL conversion to HTTP."""
    config = Config(
        endpoint="ws://localhost:4445/v1/audio/transcriptions",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "test"}
    mock_response.raise_for_status = MagicMock()

    with patch("src.server.python.codewhisper.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        await transcribe_audio(config, b"fake")

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:4445/v1/audio/transcriptions"


@pytest.mark.asyncio
async def test_transcribe_audio_connection_error(
    transcribe_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test connection error handling."""
    with patch("src.server.python.codewhisper.httpx") as mock_httpx:
        mock_httpx.ConnectError = Exception
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        result = await transcribe_audio(transcribe_config, b"fake")

        assert result is None


@pytest.mark.asyncio
async def test_transcribe_audio_no_httpx(
    transcribe_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test error when httpx not installed."""
    with patch("src.server.python.codewhisper.httpx", None):
        result = await transcribe_audio(transcribe_config, b"fake")

        assert result is None
        captured = capsys.readouterr()
        assert "httpx not installed" in captured.out


# --- VAD integration-style tests (with mocked TenVad) ---


@pytest.mark.asyncio
async def test_vad_full_sequence(vad_config: Config) -> None:
    """Test complete VAD sequence: silence -> speech -> silence -> stop."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        mock_vad_instance = MagicMock()
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        audio = np.zeros(256, dtype=np.int16)
        
        # Initial silence - no speech yet (probability, flags=0)
        mock_vad_instance.process.return_value = (0.1, 0)
        for _ in range(10):
            _, should_stop = vad.process(audio)
            assert should_stop is False
        
        # Speech detected (probability, flags=1)
        mock_vad_instance.process.return_value = (0.9, 1)
        is_voice, should_stop = vad.process(audio)
        assert is_voice is True
        assert should_stop is False
        assert vad._has_speech is True
        
        # Post-speech silence until stop (probability, flags=0)
        mock_vad_instance.process.return_value = (0.1, 0)
        for i in range(62):
            _, should_stop = vad.process(audio)
            if i < 61:
                assert should_stop is False
            else:
                assert should_stop is True
