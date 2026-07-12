import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from models import Segment
from transcriber import transcribe_audio_segment, match_transcription_to_segments


class FakeTranscriber:
    def __init__(self):
        self.sample_count = None

    def transcribe_file(self, path, language="zh"):
        data, _ = sf.read(path, dtype="float32", always_2d=False)
        self.sample_count = len(data)
        return f"{language}:{len(data)}"


class TranscriberTests(unittest.TestCase):
    def test_transcribe_audio_segment_slices_audio_by_time(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audio.wav"
            sample_rate = 16000
            data = np.zeros(sample_rate * 2, dtype=np.float32)
            sf.write(path, data, sample_rate)

            transcriber = FakeTranscriber()
            text = transcribe_audio_segment(path, Segment(0.5, 1.25, "说话人1"), transcriber)

            self.assertEqual(text, "zh:12000")
            self.assertEqual(transcriber.sample_count, 12000)

    def test_match_transcription_to_segments_by_overlap(self):
        transcribed = [
            {"start": 0.0, "end": 3.0, "text": "大家好欢迎参加"},
            {"start": 3.0, "end": 6.0, "text": "本次会议"},
            {"start": 6.0, "end": 10.0, "text": "讨论项目进度"},
        ]
        annotations = [
            Segment(0.5, 4.0, "说话人1"),
            Segment(4.0, 9.0, "说话人2"),
        ]
        results = match_transcription_to_segments(transcribed, annotations)

        self.assertEqual(len(results), 2)
        # First annotation (0.5-4.0) overlaps with first two transcribed segments
        self.assertEqual(results[0][1], "大家好欢迎参加 本次会议")
        # Second annotation (4.0-9.0) overlaps with second and third
        self.assertEqual(results[1][1], "本次会议 讨论项目进度")

    def test_match_no_overlap_returns_empty(self):
        transcribed = [{"start": 0.0, "end": 2.0, "text": "hello"}]
        annotations = [Segment(5.0, 6.0, "说话人1")]
        results = match_transcription_to_segments(transcribed, annotations)
        self.assertEqual(results[0][1], "")

    def test_match_empty_transcription_returns_empty(self):
        transcribed = []
        annotations = [Segment(0.0, 3.0, "说话人1")]
        results = match_transcription_to_segments(transcribed, annotations)
        self.assertEqual(results[0][1], "")


if __name__ == "__main__":
    unittest.main()
