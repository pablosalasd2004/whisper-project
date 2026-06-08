# Whisper HUD

A voice-to-text tool for **Hyprland / Wayland** desktops. Press a keybinding to start recording, press it again to transcribe — the resulting text is typed directly into the focused window and copied to the clipboard.

Transcription runs locally via [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (no API, no cloud, no data leaves your machine).

## How it works

```
SUPER+R (first press)
  └─► transcribe.sh
        ├─ starts pw-record  →  records audio to /tmp/whisper-recording.wav
        └─ launches indicator.py  →  GTK4 floating HUD with animated bars (cyan)

SUPER+R (second press)
  └─► transcribe.sh
        ├─ stops pw-record
        ├─ runs whisper-cli  →  HUD turns yellow while processing
        ├─ copies result with wl-copy
        └─ types text with wtype
```

Press **ESC** while the HUD is visible to cancel recording without transcribing.

## Requirements

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) compiled with `whisper-cli` binary
- PipeWire (`pw-record`)
- `wl-copy` (package `wl-clipboard`)
- `wtype`
- Python 3 packages: `PyGObject` (GTK4), `sounddevice`, `numpy`, `pycairo`

## Installation

### 1. Build whisper.cpp

```bash
git clone https://github.com/ggerganov/whisper.cpp ~/.whisper/whisper.cpp
cd ~/.whisper/whisper.cpp
cmake -B build -DGGML_VULKAN=1   # remove -DGGML_VULKAN=1 if you don't have a Vulkan GPU
cmake --build build --config Release -j$(nproc)
```

### 2. Download a model

```bash
cd ~/.whisper/whisper.cpp
bash models/download-ggml-model.sh large-v3-turbo
```

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `tiny` | 75 MB | Very fast | Basic |
| `base` | 142 MB | Fast | Good |
| `small` | 466 MB | Medium | Good |
| `medium` | 1.5 GB | Slow | Very good |
| `large-v3-turbo` | 1.6 GB | Medium | Excellent |
| `large-v3` | 3.1 GB | Slow | Excellent |

### 3. Install Python dependencies

```bash
# Arch Linux / CachyOS / Manjaro
sudo pacman -S python-gobject python-sounddevice python-numpy python-cairo

# pip
pip install PyGObject sounddevice numpy pycairo
```

### 4. Place the scripts

```bash
git clone https://github.com/pablosalasd2004/whisper-project ~/.whisper
```

The scripts expect to live in `~/.whisper/`.

### 5. Configure the keybinding in Hyprland

Add to `~/.config/hypr/bindings.lua`:

```lua
hl.bind("SUPER + R", hl.dsp.exec_cmd("bash " .. os.getenv("HOME") .. "/.whisper/transcribe.sh"), { description = "Whisper: record/transcribe voice" })
```

Apply with `hyprctl reload`.

Also add a window rule so the HUD floats at the bottom center. In `~/.config/hypr/hyprland.lua`:

```lua
o.window("whisper-indicator", {
  size = { 220, 44 },
  move = { "(monitor_w/2-window_w/2)", "(monitor_h-window_h-50)" },
})
```

## Files

| File | Description |
|------|-------------|
| `transcribe.sh` | Main toggle script: start recording → transcribe |
| `indicator.py` | GTK4 floating HUD with animated equalizer |
| `cancel.sh` | Cancels active recording and cleans up temp files |

## Customization

### Change the model

Edit the `MODEL` variable in `transcribe.sh`:

```bash
MODEL="$HOME/.whisper/whisper.cpp/models/ggml-large-v3-turbo.bin"
```

### Change the HUD appearance

Edit the constants at the top of `indicator.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BG_COLOR` | `#0a1220` | Background color |
| `ACCENT_RECORDING` | `#78dce8` | Bar color while recording |
| `ACCENT_TRANSCRIBING` | `#f2c063` | Bar color while transcribing |
| `NUM_BARS` | `16` | Number of equalizer bars |
| `MAX_BAR_HEIGHT` | `28` | Max bar height in px |
| `WINDOW_WIDTH` | `220` | Window width in px |
| `WINDOW_HEIGHT` | `44` | Window height in px |

If you change `WINDOW_WIDTH` or `WINDOW_HEIGHT`, update the matching `size` in your Hyprland config too.

## Troubleshooting

**HUD doesn't appear**
```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print('OK')"
```

**Bars don't animate**
```bash
python3 -c "import sounddevice; print('OK')"
# If it fails: sudo pacman -S python-sounddevice
```

**whisper-cli produces no output**
```bash
~/.whisper/whisper.cpp/build/bin/whisper-cli --help
ls -lh ~/.whisper/whisper.cpp/models/
```

**Clean up stuck processes**
```bash
kill $(cat /tmp/whisper-recording.pid 2>/dev/null) 2>/dev/null
kill $(cat /tmp/whisper-indicator.pid 2>/dev/null) 2>/dev/null
rm -f /tmp/whisper-recording.{pid,wav} /tmp/whisper-state /tmp/whisper-indicator.pid
```

## License

MIT
