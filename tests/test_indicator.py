#!/usr/bin/env python3
"""
Unit tests for indicator.py

GTK4 is not available in headless CI environments, so gi/GTK/GLib/Gdk are
mocked via sys.modules before the module under test is imported.
"""

import sys
import types
import unittest
import struct
import math


# ---------------------------------------------------------------------------
# Mock gi and GTK stack so indicator.py can be imported without a display
# ---------------------------------------------------------------------------
def _build_gtk_mocks():
    # gi
    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *a, **kw: None
    sys.modules["gi"] = gi_mod

    # gi.repository
    repo_mod = types.ModuleType("gi.repository")
    gi_mod.repository = repo_mod
    sys.modules["gi.repository"] = repo_mod

    # Gtk
    gtk_mod = types.ModuleType("gi.repository.Gtk")

    class _FakeApp:
        def __init__(self, *a, **kw): pass
        def run(self, *a): return 0

    class _FakeAppWindow:
        def __init__(self, *a, **kw): pass
        def set_default_size(self, *a): pass
        def set_resizable(self, *a): pass
        def set_decorated(self, *a): pass
        def set_title(self, *a): pass
        def get_display(self): return None
        def get_style_context(self): return _FakeStyleCtx()
        def set_child(self, *a): pass
        def add_controller(self, *a): pass
        def present(self): pass

    class _FakeStyleCtx:
        def add_provider(self, *a): pass

    class _FakeDrawingArea:
        def set_content_width(self, *a): pass
        def set_content_height(self, *a): pass
        def set_hexpand(self, *a): pass
        def set_vexpand(self, *a): pass
        def set_draw_func(self, *a): pass
        def queue_draw(self): pass

    class _FakeCssProvider:
        def load_from_data(self, *a): pass

    class _FakeEvCtrlKey:
        def connect(self, *a): pass

    gtk_mod.Application = _FakeApp
    gtk_mod.ApplicationWindow = _FakeAppWindow
    gtk_mod.DrawingArea = _FakeDrawingArea
    gtk_mod.CssProvider = _FakeCssProvider
    gtk_mod.EventControllerKey = _FakeEvCtrlKey

    class _FakeStyleContext:
        @staticmethod
        def add_provider_for_display(*a): pass

    gtk_mod.StyleContext = _FakeStyleContext
    gtk_mod.STYLE_PROVIDER_PRIORITY_USER = 800
    sys.modules["gi.repository.Gtk"] = gtk_mod
    repo_mod.Gtk = gtk_mod

    # GLib
    glib_mod = types.ModuleType("gi.repository.GLib")
    glib_mod.timeout_add = lambda *a, **kw: 0
    sys.modules["gi.repository.GLib"] = glib_mod
    repo_mod.GLib = glib_mod

    # Gdk
    gdk_mod = types.ModuleType("gi.repository.Gdk")
    gdk_mod.KEY_Escape = 65307
    sys.modules["gi.repository.Gdk"] = gdk_mod
    repo_mod.Gdk = gdk_mod

    # cairo
    cairo_mod = types.ModuleType("cairo")
    cairo_mod.OPERATOR_SOURCE = 1
    cairo_mod.OPERATOR_OVER = 2
    sys.modules["cairo"] = cairo_mod


_build_gtk_mocks()

# Now import the module under test
sys.path.insert(0, "/tmp/whisper-review")
import indicator  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestParseColor(unittest.TestCase):

    def test_cyan_values(self):
        r, g, b = indicator.parse_color("#78dce8")
        self.assertAlmostEqual(r, 0x78 / 255.0, places=5)
        self.assertAlmostEqual(g, 0xdc / 255.0, places=5)
        self.assertAlmostEqual(b, 0xe8 / 255.0, places=5)

    def test_black(self):
        r, g, b = indicator.parse_color("#000000")
        self.assertEqual((r, g, b), (0.0, 0.0, 0.0))

    def test_white(self):
        r, g, b = indicator.parse_color("#ffffff")
        self.assertAlmostEqual(r, 1.0, places=5)
        self.assertAlmostEqual(g, 1.0, places=5)
        self.assertAlmostEqual(b, 1.0, places=5)

    def test_without_hash(self):
        """parse_color should work with or without the leading '#'."""
        with_hash    = indicator.parse_color("#78dce8")
        without_hash = indicator.parse_color("78dce8")
        self.assertEqual(with_hash, without_hash)

    def test_returns_three_floats(self):
        result = indicator.parse_color("#f2c063")
        self.assertEqual(len(result), 3)
        for v in result:
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)


class TestConstants(unittest.TestCase):

    def test_window_dimensions_positive(self):
        self.assertGreater(indicator.WINDOW_WIDTH, 0)
        self.assertGreater(indicator.WINDOW_HEIGHT, 0)

    def test_bar_height_ordering(self):
        self.assertLess(indicator.MIN_BAR_HEIGHT, indicator.MAX_BAR_HEIGHT)

    def test_accent_colors_are_valid_hex(self):
        for color in (indicator.BG_COLOR,
                      indicator.ACCENT_RECORDING,
                      indicator.ACCENT_TRANSCRIBING):
            self.assertTrue(color.startswith("#"),
                            f"{color!r} should start with '#'")
            self.assertEqual(len(color), 7,
                             f"{color!r} should be 7 characters (#rrggbb)")
            # Must be valid hex digits after '#'
            int(color[1:], 16)

    def test_audio_levels_length(self):
        """_audio_levels is a module-level list with one entry per bar."""
        self.assertEqual(len(indicator._audio_levels), indicator.NUM_BARS)


class TestWavLevels(unittest.TestCase):
    """Tests for _wav_levels() using a real temporary WAV file."""

    def _write_wav(self, path, samples_s16):
        """Write a minimal RIFF WAV (mono, 16 kHz, s16-LE)."""
        data = struct.pack(f"<{len(samples_s16)}h", *samples_s16)
        with open(path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + len(data)))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16))
            f.write(b"data")
            f.write(struct.pack("<I", len(data)))
            f.write(data)

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._orig_wav = indicator.WAV_FILE
        indicator.WAV_FILE = self._tmp.name
        indicator._reset_calibration()

    def tearDown(self):
        import os
        indicator.WAV_FILE = self._orig_wav
        indicator._reset_calibration()
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_returns_correct_length(self):
        """_wav_levels() always returns a list of length NUM_BARS."""
        # Write enough silence to pass the header check
        silence = [0] * 3200
        self._write_wav(self._tmp.name, silence)
        result = indicator._wav_levels()
        self.assertEqual(len(result), indicator.NUM_BARS)

    def test_all_values_in_range(self):
        """Every returned level must be in [0, 1]."""
        import math
        # 200 ms of a 440 Hz tone at half amplitude
        n = 3200
        tone = [int(16000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(n)]
        self._write_wav(self._tmp.name, tone)
        # Run enough ticks to complete calibration
        for _ in range(indicator._CALIB_TICKS + 1):
            result = indicator._wav_levels()
        for v in result:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_silence_produces_near_zero(self):
        """Pure silence after calibration should yield near-zero levels."""
        tiny_noise = [1] * 3200   # effectively silent
        self._write_wav(self._tmp.name, tiny_noise)
        # Calibrate on silence
        for _ in range(indicator._CALIB_TICKS + 1):
            result = indicator._wav_levels()
        self.assertTrue(all(v < 0.1 for v in result),
                        f"Expected near-zero levels, got: {result}")

    def test_audio_levels_module_var_updated(self):
        """_audio_levels module variable must be updated after calibration."""
        silence = [0] * 3200
        self._write_wav(self._tmp.name, silence)
        for _ in range(indicator._CALIB_TICKS + 1):
            indicator._wav_levels()
        self.assertEqual(len(indicator._audio_levels), indicator.NUM_BARS)

    def test_missing_file_returns_zeros(self):
        """_wav_levels() must not raise when the WAV file doesn't exist."""
        indicator.WAV_FILE = "/tmp/does_not_exist_whisper_test.wav"
        indicator._reset_calibration()
        result = indicator._wav_levels()
        self.assertEqual(result, [0.0] * indicator.NUM_BARS)
        indicator.WAV_FILE = self._tmp.name


if __name__ == "__main__":
    unittest.main()
