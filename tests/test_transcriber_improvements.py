"""Tests for transcription improvements: VAD config, merge strategy, model voting."""
import unittest
from unittest.mock import patch, MagicMock

from transcriber import (
    VadConfig,
    VAD_PRESETS,
    merge_short_segments,
    TranscriptionResult,
    vote_transcription,
)


class VadConfigTests(unittest.TestCase):
    def test_default_values(self):
        cfg = VadConfig()
        self.assertEqual(cfg.min_silence_duration_ms, 500)
        self.assertEqual(cfg.speech_pad_ms, 200)

    def test_custom_values(self):
        cfg = VadConfig(min_silence_duration_ms=300, speech_pad_ms=100)
        self.assertEqual(cfg.min_silence_duration_ms, 300)
        self.assertEqual(cfg.speech_pad_ms, 100)

    def test_to_kwargs(self):
        cfg = VadConfig(min_silence_duration_ms=400, speech_pad_ms=150)
        kwargs = cfg.to_kwargs()
        self.assertEqual(kwargs["min_silence_duration_ms"], 400)
        self.assertEqual(kwargs["speech_pad_ms"], 150)

    def test_presets_exist(self):
        self.assertIn("aggressive", VAD_PRESETS)
        self.assertIn("balanced", VAD_PRESETS)
        self.assertIn("conservative", VAD_PRESETS)

    def test_preset_values(self):
        aggressive = VAD_PRESETS["aggressive"]
        self.assertEqual(aggressive["min_silence_duration_ms"], 300)
        conservative = VAD_PRESETS["conservative"]
        self.assertGreater(conservative["min_silence_duration_ms"],
                           aggressive["min_silence_duration_ms"])


class MergeShortSegmentsTests(unittest.TestCase):
    def test_no_merge_when_above_threshold(self):
        segs = [
            {"start": 0.0, "end": 2.0, "text": "你好"},
            {"start": 2.0, "end": 4.0, "text": "世界"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 2)

    def test_merges_short_with_small_gap(self):
        segs = [
            {"start": 0.0, "end": 0.5, "text": "你"},
            {"start": 0.6, "end": 1.0, "text": "好"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "你 好")
        self.assertEqual(result[0]["start"], 0.0)
        self.assertEqual(result[0]["end"], 1.0)

    def test_no_merge_when_gap_exceeds_max(self):
        segs = [
            {"start": 0.0, "end": 0.5, "text": "你"},
            {"start": 1.1, "end": 1.5, "text": "好"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 2)

    def test_does_not_merge_long_segment(self):
        segs = [
            {"start": 0.0, "end": 3.0, "text": "这是一个长句子"},
            {"start": 3.1, "end": 3.5, "text": "很短"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 2)

    def test_max_duration_prevents_excessive_merge(self):
        """Merged segment must not exceed max_duration (including gaps)."""
        segs = [
            {"start": 0.0, "end": 0.3, "text": "a"},
            {"start": 0.5, "end": 0.8, "text": "b"},
            {"start": 1.0, "end": 1.3, "text": "c"},
            {"start": 1.5, "end": 1.8, "text": "d"},
            {"start": 2.0, "end": 5.0, "text": "e"},  # would push past limit
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5, max_duration=2.0)
        # a+b+c merge to 1.3s (within limit), d merges to 1.8s (within limit)
        # e cannot merge with d (would be 1.8+0.2+3.0=5.0 > 2.0)
        self.assertEqual(result[0]["text"], "a b c")
        self.assertEqual(result[0]["end"], 1.3)
        self.assertEqual(result[1]["text"], "d")
        self.assertEqual(result[2]["text"], "e")

    def test_empty_list(self):
        self.assertEqual(merge_short_segments([]), [])

    def test_single_segment(self):
        segs = [{"start": 0.0, "end": 0.5, "text": "a"}]
        result = merge_short_segments(segs)
        self.assertEqual(len(result), 1)

    def test_chain_merge(self):
        segs = [
            {"start": 0.0, "end": 0.3, "text": "a"},
            {"start": 0.5, "end": 0.7, "text": "b"},
            {"start": 0.9, "end": 1.1, "text": "c"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "a b c")

    def test_text_concatenation(self):
        segs = [
            {"start": 0.0, "end": 0.3, "text": "第一段"},
            {"start": 0.5, "end": 0.8, "text": "第二段"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(result[0]["text"], "第一段 第二段")

    def test_does_not_mutate_input(self):
        segs = [
            {"start": 0.0, "end": 0.5, "text": "你"},
            {"start": 0.6, "end": 1.0, "text": "好"},
        ]
        merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(segs), 2)  # original unchanged

    def test_negative_gap_not_merged(self):
        """Overlapping segments should not be treated as needing merge."""
        segs = [
            {"start": 0.0, "end": 0.5, "text": "你"},
            {"start": 0.4, "end": 1.0, "text": "好"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 2)

    def test_zero_gap_merged(self):
        segs = [
            {"start": 0.0, "end": 0.5, "text": "你"},
            {"start": 0.5, "end": 1.0, "text": "好"},
        ]
        result = merge_short_segments(segs, min_duration=1.0, max_gap=0.5)
        self.assertEqual(len(result), 1)


class TranscriptionResultTests(unittest.TestCase):
    def test_default_values(self):
        r = TranscriptionResult(model_size="small")
        self.assertEqual(r.model_size, "small")
        self.assertEqual(r.segment_count, 0)
        self.assertEqual(r.total_duration, 0.0)

    def test_segment_count(self):
        r = TranscriptionResult(model_size="medium", segments=[
            {"start": 0, "end": 1, "text": "a"},
            {"start": 1, "end": 2, "text": "b"},
        ])
        self.assertEqual(r.segment_count, 2)


class VoteTranscriptionTests(unittest.TestCase):
    def _make_match(self, n_segments):
        """Create mock matches list."""
        return [({"start": float(i), "end": float(i + 1)}, f"text{i}")
                for i in range(n_segments)]

    @patch("transcriber.transcribe_with_model")
    def test_returns_annotation_segments_count(self, mock_transcribe):
        """vote_transcription should return one entry per annotation segment."""
        from transcriber import match_transcription_to_segments
        mock_transcribe.return_value = TranscriptionResult(
            model_size="small",
            segments=[{"start": 0.0, "end": 3.0, "text": "hello world"}],
        )

        ann_segs = [
            {"start": 0.0, "end": 1.0, "speaker": "A"},
            {"start": 1.0, "end": 2.0, "speaker": "B"},
            {"start": 2.0, "end": 3.0, "speaker": "A"},
        ]
        results, info = vote_transcription("/fake/path.wav", ann_segs)
        self.assertEqual(len(results), 3)

    @patch("transcriber.transcribe_with_model")
    def test_prefers_longer_text(self, mock_transcribe):
        """When medium has longer text, it should be preferred."""
        from transcriber import match_transcription_to_segments

        def side_effect(*args, **kwargs):
            ms = args[1] if len(args) > 1 else kwargs.get("model_size")
            if ms == "small":
                return TranscriptionResult(model_size="small",
                    segments=[{"start": 0.0, "end": 1.0, "text": "abc"}])
            else:
                return TranscriptionResult(model_size="medium",
                    segments=[{"start": 0.0, "end": 1.0, "text": "abcdef"}])

        mock_transcribe.side_effect = side_effect

        ann_segs = [{"start": 0.0, "end": 1.0, "speaker": "A"}]
        results, info = vote_transcription("/fake/path.wav", ann_segs)
        _, text = results[0]
        self.assertEqual(text, "abcdef")


if __name__ == "__main__":
    unittest.main()
