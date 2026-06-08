# Whisper HUD

A voice-to-text tool for **Hyprland / Wayland** desktops. Press a keybinding to start recording, press it again to transcribe — the resulting text is typed directly into the focused window and copied to the clipboard.

Transcription runs locally via [whisper.cpp](https://github.com/ggerganov/whisper.cpp) — no API key, no cloud, no data leaves your machine.

## How it works

```
SUPER+R (first press)
  └─► transcribe.sh
        ├─ starts pw-record  →  records audio to /tmp/whisper-recording.wav
        └─ launches indicator.py  →  GTK4 floating HUD with animated equalizer (cyan)

SUPER+R (second press)
  └─► transcribe.sh
        ├─ stops pw-record
        ├─ runs whisper-cli  →  HUD turns yellow while processing
        ├─ copies result with wl-copy
        └─ types text with wtype
```

Press **ESC** while the HUD is visible to cancel recording without transcribing.

## Requirements

**System packages:**

| Package | Arch / CachyOS / Manjaro | Purpose |
|---------|--------------------------|---------|
| PipeWire | `pipewire` (usually pre-installed) | Audio recording |
| wl-clipboard | `wl-clipboard` | Copy result to clipboard |
| wtype | `wtype` | Type result into focused window |
| Python 3 | `python` | HUD indicator |
| PyGObject | `python-gobject` | GTK4 bindings |
| NumPy | `python-numpy` | Audio FFT analysis |
| PyCairo | `python-cairo` | Drawing the HUD |
| CMake + GCC | `cmake base-devel` | Build whisper.cpp |

**Optional (for GPU acceleration):**

| Package | Purpose |
|---------|---------|
| `vulkan-headers vulkan-icd-loader` | Vulkan GPU support |
| `spirv-headers` | Required when building with Vulkan |

## Installation

### 1. Clone this repository

```bash
git clone https://github.com/pablosalasd2004/whisper-project ~/.whisper
```

> The scripts must live in `~/.whisper/`. All paths default to this location.

### 2. Install system dependencies

```bash
# Arch Linux / CachyOS / Manjaro — covers everything including Python packages
sudo pacman -S python-gobject python-numpy python-cairo wl-clipboard wtype cmake base-devel

# Add these if you want Vulkan GPU acceleration (recommended if you have any GPU)
sudo pacman -S vulkan-headers vulkan-icd-loader spirv-headers
```

> **Other distributions:** install the equivalent packages for your distro, then
> `pip install -r ~/.whisper/requirements.txt` for the Python dependencies.

### 3. Build whisper.cpp

```bash
git clone https://github.com/ggerganov/whisper.cpp ~/.whisper/whisper.cpp
cd ~/.whisper/whisper.cpp

# With Vulkan GPU acceleration (faster on most hardware with a GPU):
cmake -B build -DGGML_VULKAN=1
# Without GPU (CPU only):
cmake -B build

cmake --build build --config Release -j$(nproc)
```

### 4. Download a model

```bash
cd ~/.whisper/whisper.cpp
bash models/download-ggml-model.sh small
```

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `tiny` | 75 MB | Very fast | Basic |
| `base` | 142 MB | Fast | Good |
| `small` | 466 MB | Medium | Good ← **recommended** |
| `medium` | 1.5 GB | Slow | Very good |
| `large-v3-turbo` | 1.6 GB | Medium | Excellent |
| `large-v3` | 3.1 GB | Slow | Excellent |

### 5. Configure the keybinding in Hyprland

**Standard `.conf` format** (works in any Hyprland setup):

```ini
bind = SUPER, R, exec, bash ~/.whisper/transcribe.sh

windowrulev2 = float,      title:^(whisper-indicator)$
windowrulev2 = pin,        title:^(whisper-indicator)$
windowrulev2 = noborder,   title:^(whisper-indicator)$
windowrulev2 = size 220 44, title:^(whisper-indicator)$
windowrulev2 = center,     title:^(whisper-indicator)$
```

**Lua format** (omarchy / hyprland-lua setups):

```lua
hl.bind("SUPER + R", hl.dsp.exec_cmd("bash " .. os.getenv("HOME") .. "/.whisper/transcribe.sh"), { description = "Whisper: record/transcribe voice" })

o.window({ title = "whisper-indicator" }, {
  float      = true,
  pin        = true,
  border_size = 0,
  opacity    = "1 1",
  size       = { 220, 44 },
  move       = { "(monitor_w/2-window_w/2)", "(monitor_h-window_h-50)" },
})
```

Apply with `hyprctl reload`.

## Files

| File | Description |
|------|-------------|
| `transcribe.sh` | Main toggle script: start recording → transcribe |
| `indicator.py` | GTK4 floating HUD with animated equalizer |
| `cancel.sh` | Cancels active recording (also called by ESC in the HUD) |

## Customization

All behaviour is controlled by environment variables — no config files to edit.

### Model and paths

```bash
export WHISPER_MODEL=ggml-large-v3-turbo.bin   # default: ggml-small.bin
export WHISPER_DIR=/path/to/whisper             # default: ~/.whisper
```

### Speed vs. accuracy

| Variable | Default | Notes |
|----------|---------|-------|
| `WHISPER_THREADS` | `$(nproc)` | CPU threads for inference |
| `WHISPER_BEAM` | `1` | `1` = greedy (fastest); `5` = beam search (more accurate) |
| `WHISPER_LANG` | `auto` | Set to `en`, `es`, `fr` … to skip language detection (~0.5 s faster) |

Maximum speed (English-only setup):

```bash
export WHISPER_LANG=en
export WHISPER_BEAM=1
```

Maximum accuracy (slower):

```bash
export WHISPER_BEAM=5
export WHISPER_MODEL=ggml-large-v3-turbo.bin
```

Add these exports to your shell profile (`~/.bashrc`, `~/.zshrc`, `~/.config/fish/config.fish`) to make them permanent.

### HUD appearance

Edit the constants at the top of `indicator.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BG_COLOR` | `#0a1220` | Background colour |
| `ACCENT_RECORDING` | `#78dce8` | Bar colour while recording |
| `ACCENT_TRANSCRIBING` | `#f2c063` | Bar colour while transcribing |
| `NUM_BARS` | `16` | Number of equalizer bars |
| `MAX_BAR_HEIGHT` | `28` | Max bar height in px |
| `WINDOW_WIDTH` | `220` | Window width in px |
| `WINDOW_HEIGHT` | `44` | Window height in px |

If you change `WINDOW_WIDTH` or `WINDOW_HEIGHT`, update the matching `size` in your Hyprland window rule too.

### Audio sensitivity

The HUD auto-calibrates its noise floor during the first 500 ms of every recording, so it adapts automatically to any microphone without manual tuning. If `pw-record` is picking up the wrong input device:

```bash
pactl list sources short   # list available audio input sources
```

## Running the tests

```bash
# Copy scripts to the path the tests expect
mkdir -p /tmp/whisper-review
cp ~/.whisper/transcribe.sh ~/.whisper/cancel.sh ~/.whisper/indicator.py /tmp/whisper-review/

# Bash integration tests (no hardware required — uses mock binaries)
bash ~/.whisper/tests/test_transcribe.sh

# Python unit tests (no display required — GTK is mocked)
python3 ~/.whisper/tests/test_indicator.py -v
```

## Troubleshooting

**HUD doesn't appear**
```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print('GTK4 OK')"
```

**Bars don't animate**
```bash
python3 -c "import numpy; print('numpy OK')"
# If it fails: sudo pacman -S python-numpy
```

**No text is typed after transcription**
```bash
wtype --version   # confirm wtype is installed
```

**whisper-cli not found**
```bash
ls -lh ~/.whisper/whisper.cpp/build/bin/whisper-cli
```
If missing, re-run the build step (step 4 above).

**Check logs**

All whisper-cli output and dependency errors go to `/tmp/whisper.log`:

```bash
cat /tmp/whisper.log
```

**Clean up stuck processes**
```bash
kill $(cat /tmp/whisper-recording.pid 2>/dev/null) 2>/dev/null
kill $(cat /tmp/whisper-indicator.pid 2>/dev/null) 2>/dev/null
rm -f /tmp/whisper-recording.{pid,wav} /tmp/whisper-state /tmp/whisper-indicator.pid /tmp/whisper.log
```

## License

MIT
