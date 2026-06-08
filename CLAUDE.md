# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**Whisper HUD** — a voice-to-text toggle for Hyprland/Wayland. One keybinding starts recording; pressing it again stops recording, runs whisper.cpp locally, and types the result into the focused window via `wtype` while also copying it to the clipboard via `wl-copy`.

This project is being submitted for **Codex for Open Source** consideration, so changes should be clean, well-tested, and usable by anyone on a similar Wayland/Hyprland setup without hand-holding.

## Running the tests

**Before running the bash test suite**, copy the scripts to the path the tests expect:

```bash
mkdir -p /tmp/whisper-review
cp transcribe.sh cancel.sh indicator.py /tmp/whisper-review/
```

Run bash integration tests (no hardware required — uses mock binaries):
```bash
bash tests/test_transcribe.sh
```

Run Python unit tests (no display required — GTK is mocked):
```bash
python3 -m pytest tests/test_indicator.py -v
# or without pytest:
python3 tests/test_indicator.py
```

## Architecture

### State machine (file-based IPC)

The three processes communicate exclusively through `/tmp/whisper-state`:

| Value | Who writes it | Who reads it |
|-------|--------------|--------------|
| `recording` | `transcribe.sh` on first press | `indicator.py` (polls every 50 ms) |
| `transcribing` | `transcribe.sh` after stopping pw-record | `indicator.py` |
| `done` | `transcribe.sh` when finished | `indicator.py` (triggers quit) |
| `cancel` | `cancel.sh` | `indicator.py` (triggers quit) |

### Data flow

```
First press  → write_state("recording") → launch indicator.py + pw-record
Second press → kill pw-record → write_state("transcribing") → run whisper-cli
             → write_state("done") → wl-copy + wtype result
ESC in HUD   → cancel.sh → write "cancel" → kill pw-record → cleanup
```

### Audio visualization

`indicator.py` reads the tail of the WAV file that `pw-record` is actively writing, runs an FFT on the last ~200 ms of samples (`_wav_levels()` in `indicator.py`), and maps the result to 16 log-spaced frequency bands (85–8000 Hz). The first 500 ms of every recording are used to auto-calibrate the noise floor so the display works correctly regardless of microphone sensitivity — no manual tuning required.

A module-level `_audio_levels` list is kept in sync after each tick; tests and external code can read current bar values without holding a reference to the `WhisperIndicator` instance.

### Key env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `WHISPER_DIR` | `~/.whisper` | Root of the installation |
| `WHISPER_MODEL` | `ggml-small.bin` | Model filename under `whisper.cpp/models/` |
| `WHISPER_THREADS` | `$(nproc)` | CPU threads passed to whisper-cli |
| `WHISPER_BEAM` | `1` | Beam size (1 = greedy/fastest, 5 = accurate) |
| `WHISPER_LANG` | `auto` | Language code — set to `en` etc. to skip detection |
| `WHISPER_PIDFILE` | `/tmp/whisper-recording.pid` | Overridable for testing |
| `WHISPER_STATEFILE` | `/tmp/whisper-state` | Overridable for testing |
| `WHISPER_INDICATOR_PIDFILE` | `/tmp/whisper-indicator.pid` | Overridable for testing |

## Hardcoded paths to be aware of

- Tests expect scripts at `/tmp/whisper-review/` (hardcoded in both test files).
- `indicator.py` reads state from `/tmp/whisper-state` and audio from `/tmp/whisper-recording.wav` (module-level constants — `WAV_FILE` and `STATE_FILE` — easy to patch for testing).
- `transcribe.sh` logs errors to `/tmp/whisper.log`.

## Requirements

Runtime: `PyGObject` (GTK4), `numpy`, `pycairo`, `pw-record`, `wl-copy`, `wtype`, `whisper-cli` (from whisper.cpp). The `sounddevice` entry in `requirements.txt` is no longer used at runtime — audio is read directly from the WAV file.
