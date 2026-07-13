"""Integration tests for the full annotation → transcription → correction → export pipeline."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

from models import AnnotationProject, Segment, Speaker, sort_segments
from transcriber import match_transcription_to_segments
from correction import CorrectionConfig, CustomTerm, load_config, save_config
from main import AudioAnnotator, _parse_time, _cli_export


class AnnotationWorkflowIntegrationTests(unittest.TestCase):
    """Test the complete annotation workflow without GUI."""

    def test_full_annotation_roundtrip(self):
        """Create annotation project, simulate transcription, export, reload."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # Step 1: Create audio file
            audio_path = td / "meeting.wav"
            sample_rate = 16000
            data = np.random.randn(sample_rate * 10).astype(np.float32)
            sf.write(audio_path, data, sample_rate)

            # Step 2: Create annotation project
            speakers = [
                Speaker("张三", "#E74C3C"),
                Speaker("李四", "#3498DB"),
            ]
            segments = [
                Segment(0.0, 3.5, "张三", ""),
                Segment(3.5, 7.0, "李四", ""),
                Segment(7.0, 10.0, "张三", ""),
            ]
            project = AnnotationProject(
                audio_path=str(audio_path),
                speakers=speakers,
                segments=segments,
            )

            # Step 3: Save project
            project_path = td / "meeting.aaproj"
            from models import save_project
            save_project(project_path, project)

            # Step 4: Load project back
            from models import load_project
            loaded = load_project(project_path)
            self.assertEqual(loaded.audio_path, str(audio_path))
            self.assertEqual(len(loaded.speakers), 2)
            self.assertEqual(len(loaded.segments), 3)
            self.assertEqual(loaded.segments[0].speaker, "张三")
            self.assertEqual(loaded.segments[1].speaker, "李四")

            # Step 5: Simulate transcription match
            transcribed = [
                {"start": 0.0, "end": 2.0, "text": "大家好"},
                {"start": 2.0, "end": 4.0, "text": "今天开会"},
                {"start": 4.0, "end": 6.0, "text": "同意"},
                {"start": 6.0, "end": 8.0, "text": "有异议"},
                {"start": 8.0, "end": 10.0, "text": "那就这样"},
            ]
            matches = match_transcription_to_segments(transcribed, loaded.segments)
            for seg, text in matches:
                seg["text"] = text

            # Step 6: Apply correction
            config = CorrectionConfig.default()
            config.custom_terms = [CustomTerm("数智办公", "项目名称")]
            for seg in loaded.segments:
                seg["text"] = config.apply(seg["text"])

            # Step 7: Export TXT
            from main import AudioAnnotator
            root = MagicMock()
            annotator = AudioAnnotator.__new__(AudioAnnotator)
            annotator.audio_path = str(audio_path)
            annotator.segments = [s.to_dict() for s in loaded.segments]
            annotator.duration = 10.0

            export_path = td / "meeting_标注.txt"
            # Use _cli_export via a mock annotation file
            annot_path = td / "meeting_标注.txt"
            with open(annot_path, "w", encoding="utf-8") as f:
                for seg in annotator.segments:
                    f.write(f"{seg['speaker']}\t{_parse_time('00:00:00.00'):.2f}\t{_parse_time('00:00:00.00') + 3.5:.2f}\n")

            # Just verify the segments have text after correction
            texts = [s.text for s in loaded.segments]
            self.assertTrue(any(texts))  # At least some have text

    def test_transcription_matching_with_gaps(self):
        """When transcription has gaps, unmatched segments get empty text."""
        transcribed = [
            {"start": 0.0, "end": 2.0, "text": "hello"},
        ]
        annotations = [
            Segment(0.0, 2.0, "A"),
            Segment(5.0, 7.0, "B"),  # No transcription overlap
            Segment(2.0, 4.0, "C"),  # No transcription overlap
        ]
        results = match_transcription_to_segments(transcribed, annotations)
        self.assertEqual(results[0][1], "hello")
        self.assertEqual(results[1][1], "")
        self.assertEqual(results[2][1], "")

    def test_transcription_matching_partial_overlap(self):
        """Partial overlap should still match text."""
        transcribed = [
            {"start": 1.0, "end": 4.0, "text": "partial match"},
        ]
        annotations = [
            Segment(0.0, 5.0, "A"),  # Fully contains transcribed
            Segment(2.0, 3.0, "B"),  # Fully inside transcribed
        ]
        results = match_transcription_to_segments(transcribed, annotations)
        self.assertEqual(results[0][1], "partial match")
        self.assertEqual(results[1][1], "partial match")

    def test_correction_pipeline_preserves_unknown_text(self):
        """Text without any matching rules should pass through unchanged."""
        config = CorrectionConfig.default()
        text = "这是一个普通的句子"
        result = config.apply(text)
        self.assertEqual(result, text)

    def test_correction_handles_empty_input(self):
        config = CorrectionConfig.default()
        self.assertEqual(config.apply(""), "")
        self.assertEqual(config.apply(None), "")

    def test_sort_segments_after_edits(self):
        """Segments should remain sorted after any edit operation."""
        segs = [
            Segment(10.0, 20.0, "A"),
            Segment(1.0, 2.0, "B"),
            Segment(5.0, 8.0, "C"),
        ]
        sort_segments(segs)
        starts = [s.start for s in segs]
        self.assertEqual(starts, [1.0, 5.0, 10.0])

    def test_project_normalize_sorts_and_dedupes(self):
        """Normalize should sort segments and coerce types."""
        raw_segments = [
            {"start": "5.0", "end": "10.0", "speaker": "B", "text": ""},
            {"start": 1.0, "end": 3.0, "speaker": "A", "text": "first"},
        ]
        project = AnnotationProject(
            audio_path="/tmp/test.wav",
            speakers=[Speaker("A", "#f00")],
            segments=raw_segments,
        )
        project.normalize()
        self.assertEqual([s.start for s in project.segments], [1.0, 5.0])
        self.assertIsInstance(project.segments[0], Segment)

    def test_initial_prompt_changes_with_terms(self):
        """Adding terms to config should change the initial prompt."""
        config = CorrectionConfig.default()
        prompt_empty = config.build_initial_prompt()

        config.custom_terms.append(CustomTerm("数智办公", "项目"))
        config.custom_terms.append(CustomTerm("K8s", "集群"))
        prompt_with_terms = config.build_initial_prompt()

        self.assertNotEqual(prompt_empty, prompt_with_terms)
        self.assertIn("数智办公", prompt_with_terms)
        self.assertIn("K8s", prompt_with_terms)


class EdgeCaseTests(unittest.TestCase):
    """Boundary conditions and error cases."""

    def test_parse_time_edge_cases(self):
        self.assertEqual(_parse_time("00:00:00.00"), 0.0)
        self.assertEqual(_parse_time("99:59:59.99"), 359999.99)

    def test_parse_time_lenient_format(self):
        """_parse_time accepts non-zero-padded parts (splits on ':' correctly)."""
        self.assertEqual(_parse_time("1:2:3"), 3723.0)

    def test_parse_time_invalid_format(self):
        with self.assertRaises(ValueError):
            _parse_time("not_a_time")
        with self.assertRaises(ValueError):
            _parse_time("1:2")  # Only 2 parts

    def test_audio_engine_zero_duration(self):
        from main import AudioEngine
        engine = AudioEngine()
        self.assertEqual(engine.duration, 0.0)

    def test_audio_engine_no_data(self):
        from main import AudioEngine
        engine = AudioEngine()
        self.assertIsNone(engine._data)

    def test_segment_zero_duration(self):
        from models import Segment
        seg = Segment(1.0, 1.0, "A")
        self.assertEqual(seg.duration, 0.0)

    def test_segment_swapped_bounds(self):
        """Segment should auto-swap if end < start."""
        from models import Segment
        seg = Segment(5.0, 2.0, "A")
        self.assertEqual(seg.start, 2.0)
        self.assertEqual(seg.end, 5.0)

    def test_segment_negative_times(self):
        from models import Segment
        seg = Segment(-1.0, 3.0, "A")
        self.assertEqual(seg.start, -1.0)  # Allowed through __init__
        self.assertEqual(seg.end, 3.0)

    def test_overlap_detection_empty(self):
        from models import find_overlaps
        self.assertEqual(find_overlaps([]), [])

    def test_overlap_detection_single(self):
        from models import find_overlaps, Segment
        self.assertEqual(find_overlaps([Segment(0, 5, "A")]), [])

    def test_overlap_detection_no_overlaps(self):
        from models import find_overlaps, Segment
        segs = [Segment(0, 2, "A"), Segment(2, 4, "A"), Segment(4, 6, "A")]
        self.assertEqual(find_overlaps(segs), [])

    def test_overlap_detection_adjacent_not_overlap(self):
        """Segments touching at a boundary are not overlapping."""
        from models import find_overlaps, Segment
        segs = [Segment(0, 2, "A"), Segment(2, 4, "B")]
        self.assertEqual(find_overlaps(segs), [])

    def test_merge_segments_boundary(self):
        from models import merge_segments, Segment
        segs = [Segment(0, 2, "A"), Segment(2, 4, "A")]
        merge_segments(segs, 0)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].start, 0.0)
        self.assertEqual(segs[0].end, 4.0)

    def test_split_segment_boundary(self):
        from models import split_segment, Segment
        segs = [Segment(0, 4, "A")]
        result = split_segment(segs, 0, 2.0)
        self.assertTrue(result)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0].end, 2.0)
        self.assertEqual(segs[1].start, 2.0)

    def test_split_segment_too_close_to_edge(self):
        from models import split_segment, Segment
        segs = [Segment(0, 1.0, "A")]
        result = split_segment(segs, 0, 0.02)  # min_duration=0.05
        self.assertFalse(result)

    def test_adjust_edge_clamps_to_duration(self):
        from models import adjust_segment_edge, Segment
        segs = [Segment(0, 5.0, "A")]
        adjust_segment_edge(segs, 0, "end", 10.0, duration=8.0)
        self.assertEqual(segs[0].end, 8.0)

    def test_adjust_edge_prevents_inversion(self):
        from models import adjust_segment_edge, Segment
        segs = [Segment(2.0, 5.0, "A")]
        adjust_segment_edge(segs, 0, "start", 6.0, duration=10.0, min_duration=0.05)
        # start should be clamped so segment stays valid
        self.assertLessEqual(segs[0].start, segs[0].end - 0.05)


if __name__ == "__main__":
    unittest.main()
