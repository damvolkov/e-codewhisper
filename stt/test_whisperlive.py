#!/usr/bin/env python3
"""Test client for WhisperLive (Collabora) WebSocket server."""

import asyncio
import json
import struct
import sys
import uuid

import numpy as np

try:
    import websockets
except ImportError:
    print("pip install websockets")
    sys.exit(1)


async def main():
    host = "localhost"
    port = 9090
    uid = str(uuid.uuid4())
    
    uri = f"ws://{host}:{port}"
    print(f"[INFO] Connecting to {uri}...")
    
    async with websockets.connect(uri) as ws:
        # Send initial config
        config = {
            "uid": uid,
            "language": "es",  # Spanish
            "task": "transcribe",
            "model": "small",
            "use_vad": True,
        }
        await ws.send(json.dumps(config))
        print(f"[INFO] Sent config: {config}")
        
        # Wait for SERVER_READY
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"[SERVER] {data}")
            
            if data.get("message") == "SERVER_READY":
                print("[INFO] Server ready! Starting audio capture...")
                break
            elif data.get("status") == "ERROR":
                print(f"[ERROR] {data.get('message')}")
                return
        
        # Start audio capture with arecord (Linux ALSA)
        proc = await asyncio.create_subprocess_exec(
            "arecord", "-f", "S16_LE", "-c", "1", "-r", "16000", "-t", "raw", "-q", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        print("[INFO] Recording... (Ctrl+C to stop)")
        
        async def send_audio():
            """Read audio and send to server."""
            chunk_size = 4096  # bytes (2048 samples of int16)
            try:
                while True:
                    data = await proc.stdout.read(chunk_size)
                    if not data:
                        break
                    
                    # Convert int16 to float32 normalized
                    audio_int16 = np.frombuffer(data, dtype=np.int16)
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0
                    
                    await ws.send(audio_float32.tobytes())
            except asyncio.CancelledError:
                pass
        
        async def receive_transcriptions():
            """Receive and print transcriptions."""
            try:
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        if "segments" in data:
                            for seg in data["segments"]:
                                text = seg.get("text", "").strip()
                                if text:
                                    print(f"\r[TRANSCRIPTION] {text}", end="", flush=True)
                        elif "message" in data:
                            print(f"\n[SERVER] {data['message']}")
                    except json.JSONDecodeError:
                        pass
            except asyncio.CancelledError:
                pass
        
        # Run both tasks
        send_task = asyncio.create_task(send_audio())
        recv_task = asyncio.create_task(receive_transcriptions())
        
        try:
            await asyncio.gather(send_task, recv_task)
        except KeyboardInterrupt:
            print("\n[INFO] Stopping...")
        finally:
            send_task.cancel()
            recv_task.cancel()
            proc.terminate()
            await proc.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Bye!")
