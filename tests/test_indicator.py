#!/usr/bin/env python3
"""
Unit tests for indicator.py

GTK4 is not available in headless CI environments, so gi/GTK/GLib/Gdk are
mocked via sys.modules before the module under test is imported.
"""

import sys
import types
import unittest


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
        self.assertEqual(len(indicator._audio_levels), indicator.NUM_BARS)


if __name__ == "__main__":
    unittest.main()
