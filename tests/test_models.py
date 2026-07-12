import json
import tempfile
import unittest
from pathlib import Path

from models import (
    AnnotationProject,
    Segment,
    Speaker,
    adjust_segment_edge,
    find_overlaps,
    load_project,
    merge_segments,
    save_project,
    sort_segments,
    split_segment,
)


class ModelTests(unittest.TestCase):
    def test_segment_supports_existing_dict_access(self):
        seg = Segment(2, 5, "说话人1")
        self.assertEqual(seg["start"], 2)
        seg["speaker"] = "张三"
        self.assertEqual(seg.speaker, "张三")

    def test_project_roundtrip_json(self):
        project = AnnotationProject(
            audio_path="/tmp/demo.wav",
            speakers=[Speaker("张三", "#E74C3C")],
            segments=[Segment(3, 4, "张三"), Segment(1, 2, "张三")],
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "demo.aaproj"
            save_project(path, project)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)

            loaded = load_project(path)
            self.assertEqual(loaded.audio_path, "/tmp/demo.wav")
            self.assertEqual(loaded.speakers[0].name, "张三")
            self.assertEqual([seg.start for seg in loaded.segments], [1, 3])

    def test_sort_split_merge_and_adjust(self):
        segments = [Segment(10, 20, "A"), Segment(1, 2, "B")]
        sort_segments(segments)
        self.assertEqual([seg.start for seg in segments], [1, 10])

        self.assertTrue(split_segment(segments, 1, 12))
        self.assertEqual([(seg.start, seg.end) for seg in segments], [(1, 2), (10, 12), (12, 20)])

        self.assertTrue(adjust_segment_edge(segments, 1, "end", 13, duration=30))
        self.assertEqual(segments[1].end, 13)

        self.assertTrue(merge_segments(segments, 1))
        self.assertEqual((segments[1].start, segments[1].end), (10, 20))

    def test_overlap_detection(self):
        segments = [Segment(0, 3, "A"), Segment(2, 4, "B"), Segment(5, 6, "A")]
        self.assertEqual(find_overlaps(segments), [(0, 1)])


if __name__ == "__main__":
    unittest.main()
