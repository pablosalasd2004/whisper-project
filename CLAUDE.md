# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal voice-to-text tool for Hyprland/Wayland. `SUPER+R` toggles recording; on the second press, audio is transcribed with whisper.cpp and the result is typed into the focused window via `wtype` and copied to clipboard via `wl-copy`. A GTK4 floating HUD (`indicator.py`) shows state visually.

## Build whisper.cpp

```bash
cd ~/.whisper/whisper.cpp
cmake -B build -DGGML_VULKAN=1   # Vulkan backend (active config)
cmake --build build --config Release -j$(nproc)
# Binary lands at: build/bin/whisper-cli
```

Download a model:
```bash
cd ~/.whisper/whisper.cpp
bash models/download-ggml-model.sh large-v3-turbo   # or tiny, base, small, medium
```

## File roles

| File | Role |
|------|------|
| `transcribe.sh` | Toggle script: start recording (first call) → transcribe (second call). Driven by presence of `/tmp/whisper-recording.pid`. |
| `indicator.py` | GTK4 HUD process. Polls `/tmp/whisper-state` every 50 ms and renders animated equalizer bars. Launched by `transcribe.sh`, exits on `done`/`cancel`. |
| `cancel.sh` | Kills `pw-record`, writes `cancel` to state file, cleans temp files. Called by ESC handler inside `indicator.py`. |

## State machine

`/tmp/whisper-state` drives `indicator.py`:

- `recording` → cyan animated bars (real mic RMS via `sounddevice`)
- `transcribing` → yellow idle animation
- `done` / `cancel` → indicator exits

## Key configuration points

- **Model path**: `MODEL=` variable in `transcribe.sh` (currently `ggml-large-v3.bin`)
- **HUD appearance**: constants at the top of `indicator.py` (`BG_COLOR`, `ACCENT_RECORDING`, `ACCENT_TRANSCRIBING`, `NUM_BARS`, `MAX_BAR_HEIGHT`, `WINDOW_WIDTH`, `WINDOW_HEIGHT`)
- **Keybinding**: `~/.config/hypr/bindings.lua` — `SUPER + R`
- **Window position/size**: `~/.config/hypr/hyprland.lua` — `window("whisper-indicator", ...)`. If you change `WINDOW_WIDTH`/`WINDOW_HEIGHT` in `indicator.py`, update the matching `size` here too.

## Runtime temp files

| Path | Purpose |
|------|---------|
| `/tmp/whisper-state` | Current state string |
| `/tmp/whisper-recording.pid` | PID of `pw-record`; presence = recording in progress |
| `/tmp/whisper-recording.wav` | Recorded audio (deleted after transcription) |
| `/tmp/whisper-indicator.pid` | PID of `indicator.py` process |

## Dependencies

- `pw-record` (PipeWire)
- `whisper-cli` (built from `whisper.cpp/`)
- `wl-copy` (wl-clipboard)
- `wtype`
- Python: `gi` (GTK4 via PyGObject), `sounddevice`, `numpy`, `cairo`
- Apply Hyprland config changes with `hyprctl reload`
