#!/usr/bin/env python3
"""ECodeWhisper: Real-time voice transcription with WebSocket streaming and TEN VAD."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

# TEN VAD import
try:
    from ten_vad import TenVad
except ImportError:
    sys.stderr.write("ERROR: ten-vad not installed. Run: pip install git+https://github.com/TEN-framework/ten-vad.git\n")
    sys.exit(1)

# WebSocket client
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    sys.stderr.write("ERROR: websockets not installed. Run: pip install websockets\n")
    sys.exit(1)


@dataclass(frozen=True, slots=True)
class Config:
    """Transcription configuration."""

    endpoint: str
    model: str
    language: str
    vad_silence_threshold: float
    vad_threshold: float
    sample_rate: int
    min_recording_time: float
    hop_size: int = 256  # 16ms at 16kHz, optimal for TEN VAD


def emit(msg_type: str, **kwargs: str | None) -> None:
    """Emit JSON message to stdout for extension."""
    msg = {"type": msg_type, **{k: v for k, v in kwargs.items() if v is not None}}
    print(json.dumps(msg, ensure_ascii=False), flush=True)


def log(message: str) -> None:
    """Log debug message to stderr."""
    sys.stderr.write(f"[ECodeWhisper] {message}\n")
    sys.stderr.flush()


class VoiceActivityDetector:
    """TEN VAD wrapper for voice activity detection."""

    __slots__ = (
        "_vad",
        "_threshold",
        "_silence_threshold",
        "_sample_rate",
        "_hop_size",
        "_silence_frames",
        "_max_silence_frames",
        "_has_speech",
        "_min_recording_time",
        "_start_time",
    )

    def __init__(self, config: Config) -> None:
        self._vad = TenVad(hop_size=config.hop_size, threshold=config.vad_threshold)
        self._threshold = config.vad_threshold
        self._silence_threshold = config.vad_silence_threshold
        self._sample_rate = config.sample_rate
        self._hop_size = config.hop_size
        self._silence_frames = 0
        self._max_silence_frames = int(config.vad_silence_threshold * config.sample_rate / config.hop_size)
        self._has_speech = False
        self._min_recording_time = config.min_recording_time
        self._start_time = time.time()

    def process(self, audio_chunk: NDArray[np.int16]) -> tuple[bool, bool]:
        """Process audio chunk and return (has_voice, should_stop)."""
        _probability, is_speech_flag = self._vad.process(audio_chunk)
        is_voice = is_speech_flag == 1

        if is_voice:
            self._has_speech = True
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        elapsed = time.time() - self._start_time
        if elapsed < self._min_recording_time:
            return is_voice, False

        should_stop = self._has_speech and self._silence_frames >= self._max_silence_frames
        return is_voice, should_stop

    def reset(self) -> None:
        """Reset state."""
        self._silence_frames = 0
        self._has_speech = False
        self._start_time = time.time()


class AudioRecorder:
    """Audio capture using arecord (Linux ALSA)."""

    __slots__ = ("_config", "_process", "_buffer")

    def __init__(self, config: Config) -> None:
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._buffer = b""

    async def start(self) -> None:
        """Start recording process."""
        cmd = [
            "arecord",
            "-f", "S16_LE",
            "-c", "1",
            "-r", str(self._config.sample_rate),
            "-t", "raw",
            "-q", "-",
        ]

        log(f"Starting arecord with: {' '.join(cmd)}")

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._buffer = b""
        log(f"arecord started with PID: {self._process.pid}")

    async def read_chunk(self) -> bytes | None:
        """Read exactly hop_size samples (buffered)."""
        if not self._process or not self._process.stdout:
            return None

        chunk_bytes = self._config.hop_size * 2  # 16-bit = 2 bytes per sample

        while len(self._buffer) < chunk_bytes:
            try:
                data = await asyncio.wait_for(
                    self._process.stdout.read(chunk_bytes - len(self._buffer)),
                    timeout=0.5
                )
                if not data:
                    log("arecord returned empty data")
                    return None
                self._buffer += data
            except asyncio.TimeoutError:
                log("Timeout waiting for audio data")
                return None

        chunk = self._buffer[:chunk_bytes]
        self._buffer = self._buffer[chunk_bytes:]
        return chunk

    async def stop(self) -> None:
        """Stop recording."""
        if self._process:
            log("Stopping arecord...")
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                log("Force killing arecord")
                self._process.kill()
                await self._process.wait()
            self._process = None


def build_ws_url(config: Config) -> str:
    """Build WebSocket URL from endpoint config."""
    endpoint = config.endpoint.strip()
    
    # Handle http:// -> ws:// conversion
    if endpoint.startswith("http://"):
        endpoint = "ws://" + endpoint[7:]
    elif endpoint.startswith("https://"):
        endpoint = "wss://" + endpoint[8:]
    elif not endpoint.startswith("ws://") and not endpoint.startswith("wss://"):
        endpoint = "ws://" + endpoint
    
    # Ensure path
    if "/v1/audio/transcriptions" not in endpoint:
        endpoint = endpoint.rstrip("/") + "/v1/audio/transcriptions"
    
    # Add query params for language/model if specified
    params = []
    if config.language:
        params.append(f"language={config.language}")
    if config.model:
        params.append(f"model={config.model}")
    
    if params:
        separator = "&" if "?" in endpoint else "?"
        endpoint += separator + "&".join(params)
    
    return endpoint


async def transcribe_stream(config: Config) -> None:
    """Main transcription loop with WebSocket streaming and VAD."""
    log(f"Starting with config: endpoint={config.endpoint}, model={config.model}, "
        f"language={config.language}, vad_silence={config.vad_silence_threshold}s, "
        f"min_recording={config.min_recording_time}s")

    vad = VoiceActivityDetector(config)
    recorder = AudioRecorder(config)
    stop_event = asyncio.Event()
    ws_url = build_ws_url(config)
    
    log(f"WebSocket URL: {ws_url}")
    emit("connected")

    try:
        # Connect to WebSocket
        async with websockets.connect(ws_url, max_size=None) as ws:
            log("WebSocket connected")
            
            await recorder.start()
            emit("ready")

            # Start stdin monitor task
            stdin_task = asyncio.create_task(check_stdin_stop(stop_event))
            
            # Start WebSocket receiver task
            receiver_task = asyncio.create_task(receive_transcriptions(ws, stop_event))

            frame_count = 0
            speech_frames = 0
            last_text = ""

            # Recording loop with VAD
            while not stop_event.is_set():
                audio_data = await recorder.read_chunk()
                if audio_data is None:
                    continue

                frame_count += 1

                # Process with VAD
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                is_voice, should_stop = vad.process(audio_array)

                if is_voice:
                    speech_frames += 1

                # Send audio chunk to WebSocket (raw s16le PCM)
                try:
                    await ws.send(audio_data)
                except ConnectionClosed:
                    log("WebSocket connection closed during send")
                    break

                # Log progress every 100 frames (~1.6 seconds)
                if frame_count % 100 == 0:
                    log(f"Frame {frame_count}: speech_frames={speech_frames}, is_voice={is_voice}")

                # Check if VAD detected extended silence after speech
                if should_stop:
                    log(f"VAD stopped after {frame_count} frames, {speech_frames} speech frames")
                    emit("vad_stopped")
                    break

            # Stop recording
            await recorder.stop()
            stdin_task.cancel()
            
            # Close WebSocket gracefully to get final transcription
            log("Closing WebSocket connection...")
            await ws.close()
            
            # Wait for receiver to finish
            try:
                final_text = await asyncio.wait_for(receiver_task, timeout=5.0)
                if final_text:
                    emit("final", text=final_text)
                else:
                    emit("final", text="")
            except asyncio.TimeoutError:
                log("Timeout waiting for final transcription")
                emit("final", text="")

    except ConnectionRefusedError:
        emit("error", error="Cannot connect to faster-whisper server. Is it running?")
    except Exception as e:
        log(f"Error in transcription loop: {e}")
        emit("error", error=str(e))
        await recorder.stop()


async def receive_transcriptions(ws, stop_event: asyncio.Event) -> str:
    """Receive transcription messages from WebSocket."""
    last_text = ""
    try:
        async for message in ws:
            if stop_event.is_set():
                break
            try:
                data = json.loads(message)
                text = data.get("text", "").strip()
                if text and text != last_text:
                    last_text = text
                    emit("partial", text=text)
                    log(f"Transcription: {text[:60]}...")
            except json.JSONDecodeError:
                log(f"Non-JSON message: {message[:100]}")
    except ConnectionClosed:
        log("WebSocket closed by server")
    except Exception as e:
        log(f"Receiver error: {e}")
    
    return last_text


async def check_stdin_stop(stop_event: asyncio.Event) -> None:
    """Monitor stdin for STOP command."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    try:
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        while not stop_event.is_set():
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=0.1)
                if line.strip() == b"STOP":
                    log("Received STOP command from extension")
                    stop_event.set()
                    break
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        log(f"stdin monitor error: {e}")


def parse_args() -> Config:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="ECodeWhisper voice transcription")
    parser.add_argument("--endpoint", default="ws://localhost:4445/v1/audio/transcriptions")
    parser.add_argument("--model", default="")
    parser.add_argument("--language", default="es")
    parser.add_argument("--vad-silence", type=float, default=1.5)
    parser.add_argument("--vad-threshold", type=float, default=0.5)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--min-recording", type=float, default=1.0)

    args = parser.parse_args()

    return Config(
        endpoint=args.endpoint,
        model=args.model,
        language=args.language,
        vad_silence_threshold=args.vad_silence,
        vad_threshold=args.vad_threshold,
        sample_rate=args.sample_rate,
        min_recording_time=args.min_recording,
    )


def main() -> None:
    """Entry point."""
    config = parse_args()
    asyncio.run(transcribe_stream(config))


if __name__ == "__main__":
    main()
