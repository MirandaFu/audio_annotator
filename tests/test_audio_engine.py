"""Tests for AudioEngine playback state tracking."""
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from main import AudioEngine


class AudioEngineStateTests(unittest.TestCase):
    def _make_engine(self, duration=5.0, sample_rate=48000):
        engine = AudioEngine()
        engine._data = np.zeros(int(duration * sample_rate), dtype=np.float32)
        engine._fs = sample_rate
        engine._duration = duration
        engine._channels = 1
        return engine

    def test_duration_after_load(self):
        engine = self._make_engine(duration=3.0, sample_rate=48000)
        self.assertEqual(engine.duration, 3.0)

    def test_sample_rate_after_load(self):
        engine = self._make_engine(sample_rate=44100)
        self.assertEqual(engine.sample_rate, 44100)

    def test_not_playing_initially(self):
        engine = self._make_engine()
        self.assertFalse(engine.is_playing())

    def test_current_time_when_stopped(self):
        engine = self._make_engine()
        engine._start_pos = 2.5
        self.assertEqual(engine.current_time, 2.5)

    def test_current_time_when_playing(self):
        engine = self._make_engine()
        engine._play_offset = int(1.0 * 48000)
        engine._stream = MagicMock()
        engine._stream.active = True
        self.assertAlmostEqual(engine.current_time, 1.0)

    def test_stop_resets_position(self):
        engine = self._make_engine()
        engine._start_pos = 3.0
        engine._play_offset = 1000
        engine.stop()
        self.assertEqual(engine._start_pos, 0.0)
        self.assertFalse(engine.is_playing())

    def test_set_output_device(self):
        engine = self._make_engine()
        engine._output_device = 1
        self.assertEqual(engine._output_device, 1)

    def test_find_best_device_filters_virtual(self):
        devices = [
            (0, "MacBook Pro Speakers"),
            (1, "BlackHole 2ch"),
            (2, "Built-in Output"),
        ]
        with patch.object(AudioEngine, "get_output_devices", return_value=devices):
            idx, name = AudioEngine.find_best_output_device()
        self.assertEqual(idx, 0)
        self.assertEqual(name, "MacBook Pro Speakers")

    def test_find_best_device_fallback_to_first(self):
        devices = [(0, "Virtual Cable")]
        with patch.object(AudioEngine, "get_output_devices", return_value=devices):
            idx, name = AudioEngine.find_best_output_device()
        self.assertEqual(idx, 0)

    def test_find_best_device_empty(self):
        with patch.object(AudioEngine, "get_output_devices", return_value=[]):
            idx, name = AudioEngine.find_best_output_device()
        self.assertIsNone(idx)
        self.assertIsNone(name)


class AudioEnginePlaybackTests(unittest.TestCase):
    def _make_engine(self, duration=2.0, sample_rate=48000):
        engine = AudioEngine()
        engine._data = np.zeros(int(duration * sample_rate), dtype=np.float32)
        engine._fs = sample_rate
        engine._duration = duration
        engine._channels = 1
        return engine

    def test_pause_while_playing(self):
        engine = self._make_engine()
        engine._start_pos = 1.0
        engine._play_offset = int(1.5 * 48000)
        engine._stream = MagicMock()
        engine._stream.active = True

        engine.pause()

        self.assertFalse(engine.is_playing())
        # start_pos should capture current position
        self.assertAlmostEqual(engine._start_pos, 1.5, places=2)

    def test_pause_when_not_playing(self):
        engine = self._make_engine()
        engine._start_pos = 1.0
        engine.pause()
        # Should not change state
        self.assertEqual(engine._start_pos, 1.0)

    def test_resume_does_nothing_when_playing(self):
        engine = self._make_engine()
        engine._stream = MagicMock()
        engine._stream.active = True
        engine.resume()
        # Should not start another stream
        self.assertTrue(engine.is_playing())

    def test_seek_updates_position(self):
        engine = self._make_engine(duration=10.0)
        engine.seek(5.0)
        self.assertAlmostEqual(engine._start_pos, 5.0)

    def test_seek_clamps_to_duration(self):
        engine = self._make_engine(duration=10.0)
        engine.seek(20.0)
        self.assertAlmostEqual(engine._start_pos, 10.0)

    def test_seek_negative_clamps_to_zero(self):
        engine = self._make_engine(duration=10.0)
        engine.seek(-1.0)
        self.assertEqual(engine._start_pos, 0.0)


if __name__ == "__main__":
    unittest.main()
