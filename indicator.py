#!/usr/bin/env python3
"""
Whisper HUD Indicator — GTK4 floating window
Shows recording/transcribing state with an animated equalizer.

States (via /tmp/whisper-state):
  recording    → cyan bars animated with real per-band audio levels
  transcribing → yellow, low idle animation
  done         → closes the window
  cancel       → closes the window
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk

import cairo
import math
import os
import sys

import numpy as np

# ---------------------------------------------------------------------------
# Appearance
# ---------------------------------------------------------------------------
BG_COLOR              = "#0a1220"
ACCENT_RECORDING      = "#78dce8"   # cyan
ACCENT_TRANSCRIBING   = "#f2c063"   # yellow

NUM_BARS              = 16
MAX_BAR_HEIGHT        = 28          # px
MIN_BAR_HEIGHT        = 3           # px
BAR_GAP               = 3          # px
UPDATE_INTERVAL_MS    = 50

WINDOW_WIDTH          = 220
WINDOW_HEIGHT         = 44
# ---------------------------------------------------------------------------

STATE_FILE = "/tmp/whisper-state"
WAV_FILE   = "/tmp/whisper-recording.wav"
WAV_HEADER = 44   # bytes, standard RIFF WAV header

# Audio analysis constants
_SAMPLE_RATE   = 16000
_CHUNK_SAMPLES = 3200   # 200 ms of audio — better FFT resolution
_FREQ_MIN      = 85.0   # Hz, low fundamental of speech
_FREQ_MAX      = 8000.0 # Hz, high speech content

# Map display bar index → FFT frequency band index.
# Low-frequency bands (most speech energy) are placed in the center;
# high-frequency bands (less energy) on the edges — creates a symmetric hill.
_BAR_FREQ_MAP = [15, 13, 11, 9, 7, 5, 3, 1, 0, 2, 4, 6, 8, 10, 12, 14]

# Module-level audio state (readable by tests and external code)
_audio_levels  = [0.0] * NUM_BARS   # current per-bar levels, 0..1
# Noise floor starts at a conservative estimate and adapts continuously
# during silence/pauses — avoids the inconsistency of a fixed startup window.
_noise_floor   = 0.01


def parse_color(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


# ── Audio analysis ───────────────────────────────────────────────────────────

def _wav_levels():
    """
    Read the last ~200 ms of the WAV file pw-record is writing.

    Returns a list of NUM_BARS floats in [0, 1]: one per log-spaced frequency
    band.  The noise floor adapts continuously during silence so the display
    stays consistent regardless of microphone sensitivity or PipeWire startup
    timing.

    Also updates the module-level _audio_levels list so external code and
    tests can inspect the current state without holding a reference to the
    WhisperIndicator instance.
    """
    global _audio_levels, _noise_floor

    try:
        with open(WAV_FILE, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size <= WAV_HEADER:
                return [0.0] * NUM_BARS
            n_bytes = min(_CHUNK_SAMPLES * 2, size - WAV_HEADER)
            f.seek(size - n_bytes)
            raw = f.read(n_bytes)
    except OSError:
        return [0.0] * NUM_BARS

    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    n = len(samples)
    if n < 64:
        return [0.0] * NUM_BARS

    overall_rms = float(np.sqrt(np.mean(samples ** 2)))

    # Adaptive noise floor: slow EMA that only updates when the signal is
    # quiet (≤ 3× current floor).  This tracks ambient room noise and pauses
    # between words but ignores voice peaks — so the floor never drifts up
    # while the user is speaking.
    if overall_rms < _noise_floor * 3:
        _noise_floor = max(0.003, _noise_floor * 0.99 + overall_rms * 0.01)

    gain = min(8.0, 0.5 / max(_noise_floor, 0.003))

    # Overall energy above the calibrated floor — drives all bars together
    base = max(0.0, min(1.0, (overall_rms - _noise_floor) * gain))

    # FFT frequency analysis — shapes the per-bar variation
    win      = np.hanning(n)
    spectrum = np.abs(np.fft.rfft(samples * win)) * (2.0 / n)
    freqs    = np.fft.rfftfreq(n, d=1.0 / _SAMPLE_RATE)

    edges    = np.logspace(np.log10(_FREQ_MIN), np.log10(_FREQ_MAX), NUM_BARS + 1)
    band_mag = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (freqs >= lo) & (freqs < hi)
        band_mag.append(float(np.mean(spectrum[mask])) if mask.any() else 0.0)

    # Normalise FFT shape to [0, 1] relative to the loudest band
    mx = max(band_mag) if max(band_mag) > 0 else 1.0
    fft_shape = [v / mx for v in band_mag]

    # Hybrid level: base energy × per-bar FFT shape, reordered so low-freq
    # bands (most speech energy) appear in the center of the display.
    levels = [base * (0.3 + 0.7 * fft_shape[_BAR_FREQ_MAP[i]]) for i in range(NUM_BARS)]

    _audio_levels = levels
    return levels


def _reset_calibration():
    """Reset audio state for a new recording."""
    global _noise_floor, _audio_levels
    _noise_floor  = 0.01
    _audio_levels = [0.0] * NUM_BARS


# ── GTK4 Application ─────────────────────────────────────────────────────────
class WhisperIndicator(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.pablosalasd2004.WhisperHUD")
        _reset_calibration()
        self._state  = "recording"
        self._bars   = [MIN_BAR_HEIGHT / MAX_BAR_HEIGHT] * NUM_BARS
        self._phase  = 0.0
        self.win     = None

    # -- lifecycle --
    def do_activate(self):
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_default_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.win.set_resizable(False)
        self.win.set_decorated(False)
        self.win.set_title("whisper-indicator")

        css = b"window { background-color: transparent; }"
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            self.win.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        da = Gtk.DrawingArea()
        da.set_content_width(WINDOW_WIDTH)
        da.set_content_height(WINDOW_HEIGHT)
        da.set_hexpand(True)
        da.set_vexpand(True)
        da.set_draw_func(self._on_draw, None)
        self._da = da
        self.win.set_child(da)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self.win.add_controller(key_ctrl)

        self.win.present()

        GLib.timeout_add(UPDATE_INTERVAL_MS, self._tick_animation)
        GLib.timeout_add(UPDATE_INTERVAL_MS, self._tick_state)

    # -- drawing --
    def _on_draw(self, da, cr, w, h, user_data):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        r, g, b = parse_color(BG_COLOR)
        cr.set_source_rgb(r, g, b)
        cr.paint()

        if self._state == "transcribing":
            accent = parse_color(ACCENT_TRANSCRIBING)
        else:
            accent = parse_color(ACCENT_RECORDING)

        PAD       = 14
        available = w - 2 * PAD
        bar_w     = max(3, available // NUM_BARS - BAR_GAP)
        total_w   = NUM_BARS * (bar_w + BAR_GAP) - BAR_GAP
        x_start   = (w - total_w) / 2.0

        for i, level in enumerate(self._bars):
            bar_h = max(MIN_BAR_HEIGHT, level * MAX_BAR_HEIGHT)
            x     = x_start + i * (bar_w + BAR_GAP)
            y     = (h - bar_h) / 2.0

            cr.set_source_rgba(*accent, 0.9)
            bx, by, bw, bh = x, y, bar_w, bar_h
            if bh > bw:
                cr.new_sub_path()
                cr.arc(bx + bw/2, by + bw/2,      bw/2, math.pi, 0)
                cr.arc(bx + bw/2, by + bh - bw/2, bw/2, 0,       math.pi)
                cr.close_path()
            else:
                cr.rectangle(bx, by, bw, bh)
            cr.fill()

    # -- animation tick --
    def _tick_animation(self):
        if self._state == "recording":
            targets = _wav_levels()
            for i, target in enumerate(targets):
                if target > self._bars[i]:
                    self._bars[i] = self._bars[i] * 0.3 + target * 0.7   # fast attack
                else:
                    self._bars[i] = self._bars[i] * 0.7 + target * 0.3   # smooth decay

        elif self._state == "transcribing":
            self._phase += 0.08
            for i in range(NUM_BARS):
                base = 0.15 + 0.10 * math.sin(self._phase + i * 0.4)
                self._bars[i] = max(MIN_BAR_HEIGHT / MAX_BAR_HEIGHT, base)

        else:
            for i in range(NUM_BARS):
                self._bars[i] = MIN_BAR_HEIGHT / MAX_BAR_HEIGHT

        if self._da:
            self._da.queue_draw()

        return True

    # -- state poll --
    def _tick_state(self):
        try:
            with open(STATE_FILE, "r") as f:
                state = f.read().strip()
        except FileNotFoundError:
            return True

        if state in ("done", "cancel"):
            self.quit()
            return False

        if state != self._state:
            self._state = state
            if self._da:
                self._da.queue_draw()

        return True

    # -- ESC key: cancel recording --
    def _on_key(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._cancel()
            return True
        return False

    def _cancel(self):
        import subprocess
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        cancel_script = os.path.join(script_dir, "cancel.sh")
        subprocess.Popen(
            ["bash", cancel_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.quit()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = WhisperIndicator()
    sys.exit(app.run(None))
