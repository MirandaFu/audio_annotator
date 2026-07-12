import importlib
import unittest


class SmokeTests(unittest.TestCase):
    def test_core_modules_import(self):
        for name in ("main", "models", "segments_table", "speaker_panel", "waveform_widget"):
            with self.subTest(module=name):
                self.assertIsNotNone(importlib.import_module(name))


if __name__ == "__main__":
    unittest.main()
