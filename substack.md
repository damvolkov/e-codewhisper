# I Built a Voice-to-Code Extension That Types As You Speak

**Your IDE just learned to listen.**

---

I spend most of my day inside Cursor and VS Code. Typing is fine — until it isn't. Long comments, documentation blocks, brainstorming inline, dictating TODOs while your hands are busy sketching architecture on paper. I kept wishing I could just *talk* to my editor and have it keep up.

So I built **ECodeWhisper** — a real-time voice-to-text extension for Cursor and VS Code that transcribes your speech *as you speak* and drops it right where your cursor is.

No copy-paste from another app. No browser tab with a transcription service. Just press `Ctrl+Shift+E`, talk, and watch your words materialize in your editor in real time.

## What It Actually Does

**Real-time streaming transcription.** This isn't "record, wait, paste." Words appear character by character while you're still talking. The extension connects over WebSocket to a local WhisperLive server running Faster-Whisper, so latency is minimal and everything stays on your machine.

**Automatic silence detection.** You don't have to hit stop. TEN VAD (Voice Activity Detection) listens for pauses in your speech and stops recording automatically. Configurable from 0.3 to 10 seconds of silence — fast for quick notes, generous for thoughtful dictation.

**Multilingual out of the box.** English, Spanish, French, German, and dozens more — just set your language code. Or leave it empty and let Whisper auto-detect.

**Fully local and private.** Your audio never leaves your machine. The WhisperLive server runs in a Docker container on your hardware. GPU-accelerated with NVIDIA, or CPU-only if you prefer. No cloud API keys. No subscriptions. No data harvesting.

**Model flexibility.** Choose from `tiny` to `large-v3` depending on your accuracy needs and hardware. Swap models in settings without restarting anything.

## The Flow

1. Press `Ctrl+Shift+E` (or `Cmd+Shift+E` on macOS)
2. Speak naturally
3. Watch text stream into your editor in real time
4. Pause speaking — recording stops automatically
5. Keep coding

The status bar tells you exactly what's happening: ready, recording with a live timer, or finishing up the last transcription chunk.

## Why This Exists

AI coding assistants are everywhere now. They generate code, refactor functions, write tests. But the input side is still keyboard-only. You type a prompt, the AI responds, you type another prompt.

ECodeWhisper fills the gap on the *input* side. Dictate your thoughts, requirements, or documentation at the speed of speech. Use it alongside Cursor's AI features — speak your intent, then let the agent handle the implementation.

It's particularly useful for:

- **Rapid note-taking** — dump ideas inline without breaking flow
- **Documentation** — dictate docstrings and comments naturally
- **Accessibility** — code without a keyboard when you need to
- **Thinking out loud** — sometimes speaking a problem reveals the solution

## Get It

ECodeWhisper is free, open source (MIT), and available now:

- **Cursor / VS Code Marketplace** — search "ECodeWhisper" or install `damvolkov.ecodewhisper`
- **Open VSX** — [open-vsx.org/extension/damvolkov/ecodewhisper](https://open-vsx.org/extension/damvolkov/ecodewhisper)
- **GitHub** — [github.com/damvolkov/e-codewhisper](https://github.com/damvolkov/e-codewhisper)

Server setup is one command:

```bash
make install-stt        # GPU version
make install-stt-cpu    # CPU version
```

Or run Docker directly:

```bash
docker run -d --gpus all -p 9090:9090 \
  ghcr.io/collabora/whisperlive-gpu:latest
```

## What's Next

This is v0.3.2. The core loop — speak, stream, insert — is solid. Coming next: deeper integration with AI agent workflows, smarter punctuation handling, and expanding beyond Linux to macOS and Windows.

If you've ever wished your editor could just listen, give it a try. Your voice is the fastest input device you own.

---

*ECodeWhisper is open source under the MIT license. Built with [WhisperLive](https://github.com/collabora/WhisperLive) by Collabora and [TEN VAD](https://github.com/TEN-framework/ten-vad).*
