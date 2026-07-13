"""Tests for SegmentsTable formatting and data operations."""
import unittest
from unittest.mock import MagicMock

from segments_table import SegmentsTable, SPEAKER_PRESETS


class SegmentsTableFormattingTests(unittest.TestCase):
    def test_fmt_seconds_only(self):
        result = SegmentsTable._fmt(0.0)
        self.assertEqual(result, "00:00:00.00")

    def test_fmt_minutes_and_seconds(self):
        result = SegmentsTable._fmt(125.5)
        self.assertEqual(result, "00:02:05.50")

    def test_fmt_hours(self):
        result = SegmentsTable._fmt(3661.25)
        self.assertEqual(result, "01:01:01.25")

    def test_fmt_negative_clamps_to_zero(self):
        result = SegmentsTable._fmt(-5.0)
        self.assertEqual(result, "00:00:00.00")

    def test_get_existing_key(self):
        seg = {"start": 1.0, "text": "hello"}
        self.assertEqual(SegmentsTable._get(seg, "text"), "hello")

    def test_get_missing_key_returns_default(self):
        seg = {"start": 1.0}
        self.assertIsNone(SegmentsTable._get(seg, "text"))

    def test_get_bad_type_returns_default(self):
        self.assertIsNone(SegmentsTable._get("not_a_dict", "text"))


class SegmentsTableSetSegmentsTests(unittest.TestCase):
    def _make_table(self):
        table = SegmentsTable(MagicMock())
        table.tree = MagicMock()
        table.tree.get_children.return_value = []
        return table

    def test_set_segments_populates_tree(self):
        table = self._make_table()
        segs = [
            {"start": 0.0, "end": 5.0, "speaker": "说话人1", "text": "开场"},
            {"start": 5.0, "end": 10.0, "speaker": "说话人2", "text": "回应"},
        ]
        table.set_segments(segs, {"说话人1": "#ff0000", "说话人2": "#00ff00"})
        self.assertEqual(table.tree.insert.call_count, 2)

    def test_set_segments_clears_existing(self):
        table = self._make_table()
        table.tree.get_children.return_value = ["existing_item"]
        table.set_segments([], {})
        table.tree.delete.assert_called_with("existing_item")

    def test_set_segments_empty_list(self):
        table = self._make_table()
        table.set_segments([], {})
        self.assertEqual(table.tree.insert.call_count, 0)

    def test_set_segments_calculates_duration(self):
        table = self._make_table()
        segs = [{"start": 10.0, "end": 15.5, "speaker": "A", "text": ""}]
        table.set_segments(segs, {"A": "#000"})
        values = table.tree.insert.call_args.kwargs["values"]
        self.assertEqual(values[4], "5.5s")  # duration column

    def test_set_segments_indexing(self):
        table = self._make_table()
        segs = [
            {"start": 0.0, "end": 5.0, "speaker": "A", "text": ""},
            {"start": 5.0, "end": 10.0, "speaker": "B", "text": ""},
        ]
        table.set_segments(segs, {"A": "#f00", "B": "#0f0"})
        calls = table.tree.insert.call_args_list
        values0 = calls[0].kwargs["values"]
        values1 = calls[1].kwargs["values"]
        self.assertEqual(values0[0], 1)   # First item index = 1
        self.assertEqual(values1[0], 2)   # Second item index = 2

    def test_set_segments_missing_text_defaults_empty(self):
        table = self._make_table()
        segs = [{"start": 0.0, "end": 5.0, "speaker": "A"}]  # no "text" key
        table.set_segments(segs, {"A": "#000"})
        values = table.tree.insert.call_args.kwargs["values"]
        self.assertEqual(values[5], "")  # text column is empty


if __name__ == "__main__":
    unittest.main()
