#!/usr/bin/env python3
"""
Whisper HUD Indicator — GTK4 floating window
Shows recording/transcribing state with an animated equalizer.

States (via /tmp/whisper-state):
  recording    → cyan bars animadas con audio real
  transcribing → amarillo, barras estáticas bajas
  done         → cierra la ventana
  cancel       → cierra la ventana
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk

import cairo
import threading
import math
import os
import sys

# ---------------------------------------------------------------------------
# Personalización del diseño
# ---------------------------------------------------------------------------
BG_COLOR              = "#0a1220"
ACCENT_RECORDING      = "#78dce8"   # cyan
ACCENT_TRANSCRIBING   = "#f2c063"   # amarillo

NUM_BARS              = 16
MAX_BAR_HEIGHT        = 28          # px, altura máxima de las barras
MIN_BAR_HEIGHT        = 3           # px, altura mínima de las barras
BAR_GAP               = 3          # px, separación entre barras
UPDATE_INTERVAL_MS    = 50          # ms entre frames de animación

WINDOW_WIDTH          = 220
WINDOW_HEIGHT         = 44
# ---------------------------------------------------------------------------

STATE_FILE    = "/tmp/whisper-state"

def parse_color(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

# ── Audio capture ────────────────────────────────────────────────────────────
_audio_levels = [0.0] * NUM_BARS   # shared between audio thread and draw
_audio_lock   = threading.Lock()

def _start_audio_capture():
    """Hilo daemon que captura RMS del micrófono en tiempo real."""
    try:
        import sounddevice as sd
        import numpy as np

        CHUNK = 1024

        def callback(indata, frames, time_info, status):
            rms = float(np.sqrt(np.mean(indata ** 2)))
            # Normalise: típicamente 0..0.1 → 0..1
            level = min(1.0, rms * 14.0)
            with _audio_lock:
                # desplazar barras para efecto "waterfall" suave
                for i in range(NUM_BARS - 1):
                    _audio_levels[i] = _audio_levels[i + 1] * 0.85
                _audio_levels[NUM_BARS - 1] = level

        stream = sd.InputStream(
            channels=1,
            samplerate=16000,
            blocksize=CHUNK,
            dtype="float32",
            callback=callback,
        )
        stream.start()
        # Bloquea el hilo indefinidamente; el proceso principal lo terminará
        import time
        while True:
            time.sleep(1)
    except Exception:
        pass   # Si sounddevice falla, simplemente no hay animación real


# ── GTK4 Application ─────────────────────────────────────────────────────────
class WhisperIndicator(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.pablosalasd2004.WhisperHUD")
        self._state        = "recording"
        self._bars         = [MIN_BAR_HEIGHT / MAX_BAR_HEIGHT] * NUM_BARS
        self._phase        = 0.0   # para animación suave en modo transcribing
        self.win           = None

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
        self.win.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        # DrawingArea ocupa toda la ventana
        da = Gtk.DrawingArea()
        da.set_content_width(WINDOW_WIDTH)
        da.set_content_height(WINDOW_HEIGHT)
        da.set_hexpand(True)
        da.set_vexpand(True)
        da.set_draw_func(self._on_draw, None)
        self._da = da
        self.win.set_child(da)

        # ESC cancela grabación
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key)
        self.win.add_controller(key_ctrl)

        self.win.present()

        # Timers
        GLib.timeout_add(UPDATE_INTERVAL_MS, self._tick_animation)
        GLib.timeout_add(UPDATE_INTERVAL_MS, self._tick_state)

    # -- drawing --
    def _on_draw(self, da, cr, w, h, user_data):
        # Clear to transparent first
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        # Solid background — Hyprland clipea las esquinas
        r, g, b = parse_color(BG_COLOR)
        cr.set_source_rgb(r, g, b)
        cr.paint()

        # Color de acento según estado
        if self._state == "transcribing":
            accent = parse_color(ACCENT_TRANSCRIBING)
        else:
            accent = parse_color(ACCENT_RECORDING)

        # Barras del ecualizador — centradas horizontalmente
        PAD = 14  # padding a cada lado
        available = w - 2 * PAD
        bar_w = max(3, available // NUM_BARS - BAR_GAP)
        total_w = NUM_BARS * (bar_w + BAR_GAP) - BAR_GAP
        x_start = (w - total_w) / 2.0  # centrado

        for i, level in enumerate(self._bars):
            bar_h = max(MIN_BAR_HEIGHT, level * MAX_BAR_HEIGHT)
            x = x_start + i * (bar_w + BAR_GAP)
            y = (h - bar_h) / 2.0

            cr.set_source_rgba(*accent, 0.9)
            # Barras redondeadas
            bx, by, bw, bh = x, y, bar_w, bar_h
            if bh > bw:
                cr.new_sub_path()
                cr.arc(bx + bw/2, by + bw/2,      bw/2,  math.pi, 0)
                cr.arc(bx + bw/2, by + bh - bw/2, bw/2,  0,       math.pi)
                cr.close_path()
            else:
                cr.rectangle(bx, by, bw, bh)
            cr.fill()

    # -- animation tick --
    def _tick_animation(self):
        if self._state == "recording":
            # Copiar niveles reales del audio
            with _audio_lock:
                for i in range(NUM_BARS):
                    self._bars[i] = _audio_levels[i]
        elif self._state == "transcribing":
            # Animación suave estilo "idle"
            self._phase += 0.08
            for i in range(NUM_BARS):
                base = 0.15 + 0.10 * math.sin(self._phase + i * 0.4)
                self._bars[i] = max(MIN_BAR_HEIGHT / MAX_BAR_HEIGHT, base)
        else:
            for i in range(NUM_BARS):
                self._bars[i] = MIN_BAR_HEIGHT / MAX_BAR_HEIGHT

        if self._da:
            self._da.queue_draw()

        return True   # mantener el timer vivo

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

        return True   # mantener el timer vivo

    # -- ESC key: cancel recording --
    def _on_key(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._cancel()
            return True
        return False

    def _cancel(self):
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cancel_script = os.path.join(script_dir, "cancel.sh")
        subprocess.Popen(
            ["bash", cancel_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.quit()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Lanzar captura de audio en hilo daemon
    t = threading.Thread(target=_start_audio_capture, daemon=True)
    t.start()

    app = WhisperIndicator()
    sys.exit(app.run(None))
