"""Tests for WaveformWidget geometry, zoom, peaks, and drawing helpers."""
import unittest
from unittest.mock import MagicMock

import numpy as np

from waveform_widget import WaveformWidget


class WaveformGeometryTests(unittest.TestCase):
    def _make_widget(self, width=800, height=200):
        widget = WaveformWidget(MagicMock())
        widget._data_for_test = None  # flag
        # Mock winfo
        widget.winfo_width = MagicMock(return_value=width)
        widget.winfo_height = MagicMock(return_value=height)
        widget.duration = 100.0
        widget._view_start = 0.0
        widget._view_end = 100.0
        return widget

    def test_plot_area_dimensions(self):
        w = self._make_widget(width=800, height=200)
        x0, y0, x1, y1 = w._plot_area()
        self.assertEqual(x0, 60)       # PADDING_LEFT
        self.assertEqual(y0, 10)       # PADDING_TOP
        self.assertEqual(x1, 780)      # 800 - PADDING_RIGHT(20)
        self.assertEqual(y1, 170)      # 200 - PADDING_BOTTOM(30)

    def test_time_to_x_at_start(self):
        w = self._make_widget()
        x = w._time_to_x(0.0)
        self.assertEqual(x, 60)  # PADDING_LEFT

    def test_time_to_x_at_end(self):
        w = self._make_widget()
        x = w._time_to_x(100.0)
        self.assertEqual(x, 780)  # PADDING_LEFT + plot_width (800-60-20)

    def test_time_to_x_midpoint(self):
        w = self._make_widget()
        x = w._time_to_x(50.0)
        self.assertEqual(x, 420)  # midpoint of plot area (60+780)/2

    def test_x_to_time_at_left_edge(self):
        w = self._make_widget()
        t = w._x_to_time(60)
        self.assertEqual(t, 0.0)

    def test_x_to_time_at_right_edge(self):
        w = self._make_widget()
        t = w._x_to_time(780)
        self.assertEqual(t, 100.0)

    def test_x_to_time_clamps_to_view(self):
        w = self._make_widget()
        # Click beyond plot area should clamp
        t = w._x_to_time(1000)
        self.assertEqual(t, 100.0)

    def test_x_to_time_clamps_negative(self):
        w = self._make_widget()
        t = w._x_to_time(0)
        self.assertEqual(t, 0.0)

    def test_zoom_limits(self):
        w = self._make_widget()
        w.set_zoom(1.0)
        self.assertEqual(w._zoom, 1.0)
        w.set_zoom(100.0)  # clamped to 50
        self.assertEqual(w._zoom, 50.0)

    def test_zoom_changes_view_range(self):
        w = self._make_widget()
        w.set_zoom(2.0, center_time=50.0)
        self.assertEqual(w._zoom, 2.0)
        self.assertEqual(w._view_end - w._view_start, 50.0)  # 100/2

    def test_zoom_reset(self):
        w = self._make_widget()
        w.set_zoom(10.0)
        w.zoom_reset()
        self.assertEqual(w._zoom, 1.0)
        self.assertEqual(w._view_start, 0.0)
        self.assertEqual(w._view_end, 100.0)

    def test_zoom_preserves_center(self):
        w = self._make_widget()
        w.set_zoom(2.0, center_time=40.0)
        center = (w._view_start + w._view_end) / 2
        self.assertAlmostEqual(center, 40.0, places=1)

    def test_zoom_increases_range(self):
        w = self._make_widget()
        w.set_zoom(2.0)
        w.zoom_in()  # 2.0 * 1.5 = 3.0
        self.assertEqual(w._zoom, 3.0)

    def test_zoom_decreases_range(self):
        w = self._make_widget()
        w.set_zoom(4.0)
        w.zoom_out()  # 4.0 / 1.5
        self.assertAlmostEqual(w._zoom, 4.0 / 1.5, places=5)

    def test_height_scale_clamped(self):
        w = self._make_widget()
        w.set_height_scale(10.0)  # clamped to 3.0
        self.assertEqual(w._height_scale, 3.0)
        w.set_height_scale(0.1)   # clamped to 0.3
        self.assertEqual(w._height_scale, 0.3)

    def test_set_playhead_updates_time(self):
        w = self._make_widget()
        w.set_playhead(25.0)
        self.assertEqual(w.playhead, 25.0)


class WaveformPeaksTests(unittest.TestCase):
    def _make_widget(self):
        w = WaveformWidget(MagicMock())
        w.duration = 10.0
        w._view_start = 0.0
        w._view_end = 10.0
        return w

    def test_compute_peaks_reduces_data(self):
        w = self._make_widget()
        # 10000 samples, max_peaks=10000, k=1 → same size
        w.audio_data = np.ones(5000, dtype=np.float32)
        w._compute_peaks()
        self.assertIsNotNone(w._peaks)
        self.assertEqual(len(w._peaks), 5000)

    def test_compute_peaks_downsample_large(self):
        w = self._make_widget()
        # 30000 samples, max_peaks=10000, k=3
        w.audio_data = np.ones(30000, dtype=np.float32)
        w._compute_peaks()
        self.assertIsNotNone(w._peaks)
        self.assertEqual(len(w._peaks), 10000)

    def test_compute_peaks_empty_data(self):
        w = self._make_widget()
        w.audio_data = None
        w._compute_peaks()
        self.assertIsNone(w._peaks)

    def test_get_visible_peaks_returns_subset(self):
        w = self._make_widget()
        w.winfo_width = MagicMock(return_value=800)
        w._peaks_full = np.arange(1000, dtype=np.float32)
        w._view_start = 2.0
        w._view_end = 8.0
        peaks = w._get_visible_peaks()
        self.assertIsNotNone(peaks)
        # Should be subset of 1000 peaks corresponding to 20%-80% range
        self.assertLessEqual(len(peaks), 1000)

    def test_get_visible_peaks_none_when_no_data(self):
        w = self._make_widget()
        w._peaks_full = None
        peaks = w._get_visible_peaks()
        self.assertIsNone(peaks)

    def test_get_visible_peaks_downsample_for_canvas(self):
        w = self._make_widget()
        w.winfo_width = MagicMock(return_value=800)
        w._peaks_full = np.ones(5000, dtype=np.float32)
        w._view_start = 0.0
        w._view_end = 10.0
        peaks = w._get_visible_peaks()
        # Canvas width is ~720px, max_display=720, so should downsample
        self.assertLessEqual(len(peaks), 720)


class WaveformSegmentTests(unittest.TestCase):
    def _make_widget(self):
        w = WaveformWidget(MagicMock())
        w.duration = 100.0
        w._view_start = 0.0
        w._view_end = 100.0
        w._zoom = 1.0
        w.winfo_width = MagicMock(return_value=800)
        w.winfo_height = MagicMock(return_value=200)
        w.segments = []
        w.speaker_colors = {}
        w.playhead = 0.0
        return w

    def test_segments_set_replaces_list(self):
        w = self._make_widget()
        segs = [{"start": 1.0, "end": 3.0, "speaker": "A", "text": "hello"}]
        w.set_segments(segs, {"A": "#ff0000"})
        self.assertEqual(len(w.segments), 1)
        self.assertEqual(w.segments[0]["speaker"], "A")

    def test_set_current_speaker_changes_highlight(self):
        w = self._make_widget()
        w.segments = [{"start": 1.0, "end": 3.0, "speaker": "A", "text": ""}]
        w.speaker_colors = {"A": "#ff0000"}
        w.set_current_speaker("B")
        self.assertEqual(w._current_speaker, "B")

    def test_desaturate_darkens_color(self):
        original = "#ff0000"  # pure red
        result = WaveformWidget._desaturate(original, factor=0.5)
        # Should be darker (mixed with gray)
        r = int(result[1:3], 16)
        g = int(result[3:5], 16)
        b = int(result[5:7], 16)
        self.assertLess(r, 255)  # Should be darker than pure red

    def test_fmt_short_formats_correctly(self):
        self.assertEqual(WaveformWidget._fmt_short(0), "00:00:00.0")
        self.assertEqual(WaveformWidget._fmt_short(65.5), "00:01:05.5")
        self.assertEqual(WaveformWidget._fmt_short(3661.5), "01:01:01.5")

    def test_hit_segment_edge_detects_start(self):
        w = self._make_widget()
        w.segments = [{"start": 10.0, "end": 20.0, "speaker": "A", "text": ""}]
        w._view_start = 0.0
        w._view_end = 100.0
        x0, y0, x1, y1 = w._plot_area()
        # start edge at 10.0 should be at x0 + 10/100 * (x1-x0)
        start_x = w._time_to_x(10.0)
        hit = w._hit_segment_edge(start_x, (y0 + y1) / 2)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[1], "start")

    def test_hit_segment_edge_detects_end(self):
        w = self._make_widget()
        w.segments = [{"start": 10.0, "end": 20.0, "speaker": "A", "text": ""}]
        end_x = w._time_to_x(20.0)
        hit = w._hit_segment_edge(end_x, 100)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[1], "end")

    def test_hit_segment_edge_none_when_far(self):
        w = self._make_widget()
        w.segments = [{"start": 10.0, "end": 20.0, "speaker": "A", "text": ""}]
        hit = w._hit_segment_edge(500, 100)  # far from both edges
        self.assertIsNone(hit)


if __name__ == "__main__":
    unittest.main()
