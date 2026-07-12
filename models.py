"""Core data models and project persistence for Audio Annotator."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


PROJECT_VERSION = 1


@dataclass
class Segment:
    start: float
    end: float
    speaker: str

    def __post_init__(self):
        self.start = float(self.start)
        self.end = float(self.end)
        self.speaker = str(self.speaker)
        if self.end < self.start:
            self.start, self.end = self.end, self.start

    def __getitem__(self, key):
        if key in {"start", "end", "speaker"}:
            return getattr(self, key)
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "start":
            self.start = float(value)
        elif key == "end":
            self.end = float(value)
        elif key == "speaker":
            self.speaker = str(value)
        else:
            raise KeyError(key)
        if self.end < self.start:
            self.start, self.end = self.end, self.start

    @property
    def duration(self):
        return max(0.0, self.end - self.start)

    def to_dict(self):
        return {"start": self.start, "end": self.end, "speaker": self.speaker}

    @classmethod
    def from_dict(cls, data):
        return cls(data["start"], data["end"], data["speaker"])


@dataclass
class Speaker:
    name: str
    color: str

    def to_dict(self):
        return {"name": self.name, "color": self.color}

    @classmethod
    def from_dict(cls, data):
        return cls(str(data["name"]), str(data["color"]))


@dataclass
class AnnotationProject:
    audio_path: str | None = None
    speakers: list[Speaker] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)

    def normalize(self):
        self.segments = sorted(
            [coerce_segment(seg) for seg in self.segments],
            key=lambda seg: (seg.start, seg.end),
        )
        return self

    def to_dict(self):
        return {
            "version": PROJECT_VERSION,
            "audio_path": self.audio_path,
            "speakers": [speaker.to_dict() for speaker in self.speakers],
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @classmethod
    def from_dict(cls, data):
        speakers = [Speaker.from_dict(item) for item in data.get("speakers", [])]
        segments = [Segment.from_dict(item) for item in data.get("segments", [])]
        return cls(data.get("audio_path"), speakers, segments).normalize()


def coerce_segment(segment):
    if isinstance(segment, Segment):
        return segment
    return Segment.from_dict(segment)


def sort_segments(segments):
    segments[:] = sorted([coerce_segment(seg) for seg in segments], key=lambda seg: (seg.start, seg.end))
    return segments


def validate_segment(segment, duration=None, min_duration=0.05):
    segment = coerce_segment(segment)
    if duration is not None:
        segment.start = max(0.0, min(segment.start, duration))
        segment.end = max(0.0, min(segment.end, duration))
    if segment.end < segment.start:
        segment.start, segment.end = segment.end, segment.start
    return segment.duration >= min_duration


def adjust_segment_edge(segments, index, edge, time_value, duration=None, min_duration=0.05):
    if not 0 <= index < len(segments):
        return False
    segment = coerce_segment(segments[index])
    t = float(time_value)
    if duration is not None:
        t = max(0.0, min(t, duration))
    if edge == "start":
        if segment.end - t < min_duration:
            t = segment.end - min_duration
        segment.start = max(0.0, t)
    elif edge == "end":
        if t - segment.start < min_duration:
            t = segment.start + min_duration
        segment.end = min(duration, t) if duration is not None else t
    else:
        raise ValueError(f"Unknown edge: {edge}")
    sort_segments(segments)
    return True


def split_segment(segments, index, split_time, min_duration=0.05):
    if not 0 <= index < len(segments):
        return False
    segment = coerce_segment(segments[index])
    t = float(split_time)
    if t - segment.start < min_duration or segment.end - t < min_duration:
        return False
    first = Segment(segment.start, t, segment.speaker)
    second = Segment(t, segment.end, segment.speaker)
    segments[index:index + 1] = [first, second]
    sort_segments(segments)
    return True


def merge_segments(segments, first_index):
    second_index = first_index + 1
    if not 0 <= first_index < len(segments) or not 0 <= second_index < len(segments):
        return False
    first = coerce_segment(segments[first_index])
    second = coerce_segment(segments[second_index])
    speaker = first.speaker if first.speaker == second.speaker else first.speaker
    merged = Segment(min(first.start, second.start), max(first.end, second.end), speaker)
    segments[first_index:second_index + 1] = [merged]
    sort_segments(segments)
    return True


def find_overlaps(segments):
    ordered = sorted([coerce_segment(seg) for seg in segments], key=lambda seg: (seg.start, seg.end))
    overlaps = []
    for idx in range(1, len(ordered)):
        if ordered[idx].start < ordered[idx - 1].end:
            overlaps.append((idx - 1, idx))
    return overlaps


def save_project(path, project):
    path = Path(path)
    payload = project.normalize().to_dict()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_project(path):
    path = Path(path)
    return AnnotationProject.from_dict(json.loads(path.read_text(encoding="utf-8")))
