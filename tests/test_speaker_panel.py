"""Tests for SpeakerPanel selection, rename, add, delete logic."""
import unittest
from unittest.mock import MagicMock, patch

import tkinter as tk
from tkinter import messagebox

from speaker_panel import SpeakerPanel, SPEAKER_COLORS


class SpeakerPanelLogicTests(unittest.TestCase):
    def setUp(self):
        # Need a Tk root for messagebox to work
        self._root = tk.Tk()
        self._root.withdraw()

    def tearDown(self):
        self._root.destroy()

    def _make_panel(self, speakers=None, current=None):
        if speakers is None:
            speakers = ["说话人1", "说话人2"]
        colors = {name: SPEAKER_COLORS[i % len(SPEAKER_COLORS)] for i, name in enumerate(speakers)}
        panel = SpeakerPanel(MagicMock(), speakers, colors, current or speakers[0])
        panel.listbox = MagicMock()
        panel.listbox.curselection.return_value = [0]
        return panel

    def test_initial_selection_first_speaker(self):
        panel = self._make_panel()
        self.assertEqual(panel.current, "说话人1")

    def test_initial_selection_second_speaker(self):
        panel = self._make_panel(current="说话人2")
        self.assertEqual(panel.current, "说话人2")

    def test_rename_speaker_updates_name(self):
        panel = self._make_panel()
        result = panel.rename_speaker("说话人1", "张三")
        self.assertTrue(result)
        self.assertIn("张三", panel.speakers)
        self.assertNotIn("说话人1", panel.speakers)

    def test_rename_speaker_preserves_color(self):
        panel = self._make_panel()
        old_color = panel.colors.get("说话人1", "#888")
        panel.rename_speaker("说话人1", "张三")
        self.assertEqual(panel.colors.get("张三"), old_color)

    def test_rename_speaker_updates_current_if_needed(self):
        panel = self._make_panel(current="说话人1")
        panel.rename_speaker("说话人1", "张三")
        self.assertEqual(panel.current, "张三")

    def test_rename_speaker_rejects_empty(self):
        panel = self._make_panel()
        result = panel.rename_speaker("说话人1", "")
        self.assertFalse(result)

    def test_rename_speaker_rejects_duplicate(self):
        panel = self._make_panel()
        result = panel.rename_speaker("说话人1", "说话人2")
        self.assertFalse(result)

    def test_rename_speaker_rejects_same_name(self):
        panel = self._make_panel()
        result = panel.rename_speaker("说话人1", "说话人1")
        self.assertFalse(result)

    @patch.object(messagebox, "showinfo")
    def test_add_speaker_appends_list(self, mock_msg):
        panel = self._make_panel()
        panel._add()
        self.assertEqual(len(panel.speakers), 3)
        self.assertEqual(panel.speakers[-1], "说话人3")

    def test_add_speaker_assigns_color(self):
        panel = self._make_panel()
        panel._add()
        new_name = panel.speakers[-1]
        self.assertIn(new_name, panel.colors)

    def test_add_speaker_auto_selects(self):
        panel = self._make_panel()
        panel._add()
        self.assertEqual(panel.current, panel.speakers[-1])

    @patch.object(messagebox, "showinfo")
    def test_delete_speaker_prevents_last_one(self, mock_msg):
        panel = self._make_panel(speakers=["说话人1"])
        panel.listbox.curselection.return_value = [0]
        panel._delete()
        # Should not delete the last speaker
        self.assertEqual(len(panel.speakers), 1)
        mock_msg.assert_called_once()

    def test_delete_speaker_removes_color(self):
        panel = self._make_panel()
        panel.listbox.curselection.return_value = [0]
        name = panel.speakers[0]
        panel._delete()
        self.assertNotIn(name, panel.colors)

    @patch.object(SpeakerPanel, "_apply_colors")
    def test_set_speakers_replaces_all(self, mock_apply):
        panel = self._make_panel()
        panel.set_speakers(["张三", "李四"], {"张三": "#f00", "李四": "#0f0"}, current="张三")
        self.assertEqual(panel.speakers, ["张三", "李四"])
        self.assertEqual(panel.current, "张三")

    @patch.object(SpeakerPanel, "_apply_colors")
    def test_set_speakers_empty_clears(self, mock_apply):
        panel = self._make_panel()
        panel.set_speakers([], {}, current=None)
        self.assertEqual(panel.speakers, [])
        self.assertIsNone(panel.current)

    @patch.object(SpeakerPanel, "_apply_colors")
    def test_set_speakers_falls_back_to_first(self, mock_apply):
        panel = self._make_panel()
        panel.set_speakers(["张三"], {"张三": "#f00"})
        self.assertEqual(panel.current, "张三")

    def test_get_speakers_returns_copy(self):
        panel = self._make_panel()
        result = panel.get_speakers()
        self.assertIsInstance(result, list)
        result.append(" injected ")
        self.assertNotIn(" injected ", panel.speakers)

    def test_get_colors_returns_copy(self):
        panel = self._make_panel()
        result = panel.get_colors()
        self.assertIsInstance(result, dict)
        result["injected"] = "#fff"
        self.assertNotIn("injected", panel.colors)

    def test_set_current_changes_selection(self):
        panel = self._make_panel()
        panel.set_current("说话人2")
        self.assertEqual(panel.current, "说话人2")
        self.assertEqual(panel._selected_idx, 1)

    def test_next_speaker_name_increments(self):
        panel = self._make_panel(speakers=["说话人1", "说话人2", "说话人5"])
        name = panel._next_speaker_name()
        self.assertEqual(name, "说话人6")

    def test_next_speaker_name_no_existing(self):
        panel = self._make_panel(speakers=["张三", "李四"])
        name = panel._next_speaker_name()
        self.assertEqual(name, "说话人1")

    def test_is_light_detects_light_color(self):
        self.assertTrue(SpeakerPanel._is_light("#ffffff"))
        self.assertFalse(SpeakerPanel._is_light("#000000"))

    def test_is_light_mid_color(self):
        self.assertTrue(SpeakerPanel._is_light("#cccccc"))
        self.assertFalse(SpeakerPanel._is_light("#333333"))

    def test_desaturate_reduces_saturation(self):
        original = SpeakerPanel._desaturate("#ff0000", factor=0.5)
        r = int(original[1:3], 16)
        g = int(original[3:5], 16)
        b = int(original[5:7], 16)
        self.assertLess(r, 255)


if __name__ == "__main__":
    unittest.main()
