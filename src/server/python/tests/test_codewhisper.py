"""Tests for codewhisper module (WhisperLive protocol)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.server.python.codewhisper import (
    AudioRecorder,
    Config,
    audio_int16_to_float32,
    build_whisperlive_config,
    build_ws_url,
    emit,
)


# --- Config tests ---


def test_config_defaults() -> None:
    """Test Config with default values."""
    config = Config(
        endpoint="ws://localhost:9090",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
    )
    assert config.hop_size == 256
    assert config.endpoint == "ws://localhost:9090"
    assert config.model == "small"
    assert config.use_server_vad is True


def test_config_custom_values() -> None:
    """Test Config with custom values."""
    config = Config(
        endpoint="ws://localhost:9090",
        model="large-v3",
        language="es",
        vad_silence_threshold=2.0,
        vad_threshold=0.6,
        sample_rate=16000,
        min_recording_time=1.0,
        use_server_vad=False,
        hop_size=160,
    )
    assert config.hop_size == 160
    assert config.use_server_vad is False


def test_config_immutable() -> None:
    """Test that Config is immutable (frozen)."""
    config = Config(
        endpoint="ws://localhost:9090",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
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


# --- build_ws_url tests ---


@pytest.mark.parametrize(
    ("input_url", "expected"),
    [
        ("ws://localhost:9090", "ws://localhost:9090"),
        ("wss://localhost:9090", "wss://localhost:9090"),
        ("http://localhost:9090", "ws://localhost:9090"),
        ("https://localhost:9090", "wss://localhost:9090"),
        ("localhost:9090", "ws://localhost:9090"),
        ("ws://localhost:9090/v1/audio", "ws://localhost:9090"),  # Path stripped
    ],
)
def test_build_ws_url(input_url: str, expected: str) -> None:
    """Test WebSocket URL building."""
    config = Config(
        endpoint=input_url,
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
    )
    assert build_ws_url(config) == expected


# --- build_whisperlive_config tests ---


def test_build_whisperlive_config() -> None:
    """Test WhisperLive config message building."""
    config = Config(
        endpoint="ws://localhost:9090",
        model="large-v3",
        language="es",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
        use_server_vad=True,
    )
    ws_config = build_whisperlive_config(config)
    
    assert "uid" in ws_config
    assert ws_config["language"] == "es"
    assert ws_config["task"] == "transcribe"
    assert ws_config["model"] == "large-v3"
    assert ws_config["use_vad"] is True


def test_build_whisperlive_config_no_language() -> None:
    """Test WhisperLive config without language."""
    config = Config(
        endpoint="ws://localhost:9090",
        model="small",
        language="",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
    )
    ws_config = build_whisperlive_config(config)
    
    assert ws_config["language"] is None
    assert ws_config["model"] == "small"


# --- audio_int16_to_float32 tests ---


def test_audio_int16_to_float32() -> None:
    """Test audio format conversion."""
    # Create int16 samples
    samples_int16 = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
    audio_bytes = samples_int16.tobytes()
    
    result = audio_int16_to_float32(audio_bytes)
    result_array = np.frombuffer(result, dtype=np.float32)
    
    np.testing.assert_array_almost_equal(
        result_array,
        [0.0, 0.5, -0.5, 0.999969, -1.0],
        decimal=4,
    )


def test_audio_int16_to_float32_empty() -> None:
    """Test audio conversion with empty input."""
    result = audio_int16_to_float32(b"")
    assert result == b""


# --- VoiceActivityDetector tests (with mocked TenVad) ---


@pytest.fixture
def vad_config() -> Config:
    """Create config for VAD tests."""
    return Config(
        endpoint="ws://localhost:9090",
        model="small",
        language="en",
        vad_silence_threshold=1.0,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
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
        mock_vad_instance.process.return_value = (0.1, 0)
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        vad._has_speech = True
        vad._silence_frames = 61
        vad._start_time = 0  # Bypass min_recording_time
        
        audio = np.zeros(256, dtype=np.int16)
        is_voice, should_stop = vad.process(audio)
        
        assert is_voice is False
        assert should_stop is True
        assert vad._silence_frames == 62


def test_vad_no_stop_without_prior_speech(vad_config: Config) -> None:
    """Test VAD doesn't stop on silence without prior speech."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        mock_vad_instance = MagicMock()
        mock_vad_instance.process.return_value = (0.1, 0)
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        vad._silence_frames = 100
        vad._start_time = 0
        
        audio = np.zeros(256, dtype=np.int16)
        is_voice, should_stop = vad.process(audio)
        
        assert is_voice is False
        assert should_stop is False
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
        endpoint="ws://localhost:9090",
        model="small",
        language="en",
        vad_silence_threshold=1.5,
        vad_threshold=0.5,
        sample_rate=16000,
        min_recording_time=1.0,
        hop_size=256,
    )


def test_recorder_init(recorder_config: Config) -> None:
    """Test AudioRecorder initialization."""
    recorder = AudioRecorder(recorder_config)
    assert recorder._process is None
    assert recorder._buffer == b""


# --- VAD integration-style tests (with mocked TenVad) ---


@pytest.mark.asyncio
async def test_vad_full_sequence(vad_config: Config) -> None:
    """Test complete VAD sequence: silence -> speech -> silence -> stop."""
    with patch("src.server.python.codewhisper.TenVad") as MockTenVad:
        mock_vad_instance = MagicMock()
        MockTenVad.return_value = mock_vad_instance
        
        from src.server.python.codewhisper import VoiceActivityDetector
        vad = VoiceActivityDetector(vad_config)
        vad._start_time = 0  # Bypass min_recording_time
        audio = np.zeros(256, dtype=np.int16)
        
        # Initial silence - no speech yet
        mock_vad_instance.process.return_value = (0.1, 0)
        for _ in range(10):
            _, should_stop = vad.process(audio)
            assert should_stop is False
        
        # Speech detected
        mock_vad_instance.process.return_value = (0.9, 1)
        is_voice, should_stop = vad.process(audio)
        assert is_voice is True
        assert should_stop is False
        assert vad._has_speech is True
        
        # Post-speech silence until stop
        mock_vad_instance.process.return_value = (0.1, 0)
        for i in range(62):
            _, should_stop = vad.process(audio)
            if i < 61:
                assert should_stop is False
            else:
                assert should_stop is True
