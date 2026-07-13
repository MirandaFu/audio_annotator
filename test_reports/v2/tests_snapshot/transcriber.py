"""Optional ASR backend for filling segment text from audio."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

import soundfile as sf

from models import coerce_segment
from correction import WordConfidence, SegmentConfidence


class TranscriptionUnavailable(RuntimeError):
    pass


# VAD presets for different audio types
VAD_PRESETS = {
    "aggressive": {
        "min_silence_duration_ms": 300,
        "speech_pad_ms": 100,
        "description": "激进分割，适合噪音多的环境",
    },
    "balanced": {
        "min_silence_duration_ms": 500,
        "speech_pad_ms": 200,
        "description": "平衡分割，默认推荐",
    },
    "conservative": {
        "min_silence_duration_ms": 800,
        "speech_pad_ms": 300,
        "description": "保守分割，减少过度切分",
    },
}


@dataclass
class VadConfig:
    """VAD segmentation parameters."""
    min_silence_duration_ms: int = 500
    speech_pad_ms: int = 200
    preset: str = "balanced"

    def to_kwargs(self) -> dict:
        return {
            "min_silence_duration_ms": self.min_silence_duration_ms,
            "speech_pad_ms": self.speech_pad_ms,
        }


class FasterWhisperTranscriber:
    def __init__(self, model_size="medium", device="auto", compute_type="float16"):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionUnavailable(
                "未安装语音识别依赖。请先安装: pip install faster-whisper"
            ) from exc

        kwargs = {"compute_type": compute_type}
        self.model_size = model_size
        self.device = device
        self.model = WhisperModel(model_size, device=device, **kwargs)

    def transcribe_file(self, path, language="zh"):
        segments, _ = self.model.transcribe(
            path,
            language=language,
            vad_filter=True,
            beam_size=5,
        )
        return "".join(segment.text.strip() for segment in segments).strip()

    def transcribe_with_timestamps(self, path, language="zh", initial_prompt=None,
                                   word_timestamps=False, vad_config=None):
        """Transcribe full file, return list of {start, end, text} with timestamps.

        Args:
            path: Audio file path.
            language: Language code.
            initial_prompt: Whisper initial prompt for context.
            word_timestamps: Whether to include word-level timestamps.
            vad_config: VadConfig instance for VAD parameters.
        """
        vad_kwargs = (vad_config or VadConfig()).to_kwargs()
        kwargs = dict(
            language=language,
            vad_filter=True,
            vad_parameters=vad_kwargs,
            beam_size=5,
            word_timestamps=word_timestamps,
        )
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        segments, info = self.model.transcribe(str(path), **kwargs)

        results = []
        word_data = []
        for seg in segments:
            results.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            if word_timestamps and hasattr(seg, "words"):
                seg_words = []
                for word in seg.words:
                    seg_words.append({
                        "word": word.word,
                        "probability": round(word.probability, 4),
                        "start": round(word.start, 2),
                        "end": round(word.end, 2),
                    })
                word_data.append(seg_words)

        return results, info, word_data


def transcribe_audio_segment(audio_path, segment, transcriber, language="zh"):
    segment = coerce_segment(segment)
    data, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
    start = max(0, int(segment.start * sample_rate))
    end = min(len(data), int(segment.end * sample_rate))
    if end <= start:
        return ""

    audio_slice = data[start:end]
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            temp_path = temp.name
        sf.write(temp_path, audio_slice, sample_rate)
        return transcriber.transcribe_file(temp_path, language=language)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def match_transcription_to_segments(transcribed_segments, annotation_segments):
    """Match full-file transcription to user annotation segments by time overlap.

    For each annotation segment, find the transcribed text that overlaps with it.
    Returns list of (annotation_segment, matched_text).
    """
    results = []
    for annot_seg in annotation_segments:
        seg = coerce_segment(annot_seg)
        seg_start = seg.start
        seg_end = seg.end
        matched_texts = []

        for tseg in transcribed_segments:
            # Check overlap: transcribed segment overlaps with annotation segment
            if tseg["end"] <= seg_start or tseg["start"] >= seg_end:
                continue
            if tseg["text"]:
                matched_texts.append(tseg["text"])

        text = " ".join(matched_texts).strip() if matched_texts else ""
        results.append((annot_seg, text))
    return results


def match_confidence_to_segments(word_data, annotation_segments):
    """Match word-level confidence data to annotation segments by time overlap.

    Returns list of SegmentConfidence objects, one per annotation segment.
    """
    results = []
    for annot_seg in annotation_segments:
        seg = coerce_segment(annot_seg)
        seg_start = seg.start
        seg_end = seg.end
        matched_words = []

        for seg_words in word_data:
            for w in seg_words:
                # Word overlaps with annotation segment
                if w["end"] <= seg_start or w["start"] >= seg_end:
                    continue
                matched_words.append(w)

        words = [WordConfidence(
            word=w["word"],
            probability=w["probability"],
            start=w["start"],
            end=w["end"],
        ) for w in matched_words]
        results.append(SegmentConfidence(words=words))
    return results


# ─── 片段合并策略 ────────────────────────────────────────────────────────────


def merge_short_segments(segments: list[dict], min_duration: float = 1.0,
                         max_gap: float = 0.5) -> list[dict]:
    """Merge adjacent short transcribed segments into longer ones.

    When Whisper's VAD produces many fragments shorter than min_duration,
    merge them with their neighbors if the gap is within max_gap seconds.

    Args:
        segments: List of {start, end, text} dicts from transcription.
        min_duration: Segments shorter than this are candidates for merging.
        max_gap: Maximum gap between segments to consider for merging.

    Returns:
        Merged list of segments.
    """
    if len(segments) <= 1:
        return segments

    result = [dict(segments[0])]
    for seg in segments[1:]:
        prev = result[-1]
        prev_dur = prev["end"] - prev["start"]
        gap = seg["start"] - prev["end"]

        if prev_dur < min_duration and 0 <= gap <= max_gap:
            # Merge into previous segment
            prev["end"] = seg["end"]
            prev["text"] = (prev["text"] + " " + seg["text"]).strip()
        else:
            result.append(dict(seg))

    return result


# ─── 双模型投票 ────────────────────────────────────────────────────────────


@dataclass
class TranscriptionResult:
    """Result from a single model transcription."""
    model_size: str
    segments: list[dict] = field(default_factory=list)
    total_duration: float = 0.0

    @property
    def segment_count(self) -> int:
        return len(self.segments)


def transcribe_with_model(path: str, model_size: str, language: str = "zh",
                          initial_prompt: str | None = None,
                          vad_config=None) -> TranscriptionResult:
    """Run transcription with a specific model size.

    Args:
        path: Audio file path.
        model_size: Whisper model size ("tiny", "small", "medium", "large-v3").
        language: Language code.
        initial_prompt: Whisper initial prompt.
        vad_config: VadConfig instance.

    Returns:
        TranscriptionResult with segments and metadata.
    """
    transcriber = FasterWhisperTranscriber(model_size=model_size, compute_type="float16")
    segments, info, _ = transcriber.transcribe_with_timestamps(
        path, language=language, initial_prompt=initial_prompt, vad_config=vad_config
    )
    return TranscriptionResult(
        model_size=model_size,
        segments=segments,
    )


def vote_transcription(path: str, annotation_segments: list[dict],
                      language: str = "zh", initial_prompt: str | None = None,
                      vad_config=None) -> list[tuple]:
    """Dual-model voting transcription.

    Transcribes with both small and medium models, then for each annotation
    segment picks the text from the model that produced more content for that
    segment's time range.

    Args:
        path: Audio file path.
        annotation_segments: User annotation segments for matching.
        language: Language code.
        initial_prompt: Whisper initial prompt.
        vad_config: VadConfig instance.

    Returns:
        List of (annotation_segment, text) tuples with merged results.
    """
    small_result = transcribe_with_model(path, "small", language, initial_prompt, vad_config)
    medium_result = transcribe_with_model(path, "medium", language, initial_prompt, vad_config)

    # Merge short segments from each model independently
    small_result.segments = merge_short_segments(small_result.segments)
    medium_result.segments = merge_short_segments(medium_result.segments)

    # Match both to annotation segments
    small_matches = match_transcription_to_segments(small_result.segments, annotation_segments)
    medium_matches = match_transcription_to_segments(medium_result.segments, annotation_segments)

    results = []
    for i, annot_seg in enumerate(annotation_segments):
        _, small_text = small_matches[i] if i < len(small_matches) else (annot_seg, "")
        _, medium_text = medium_matches[i] if i < len(medium_matches) else (annot_seg, "")

        # Prefer the model with more content for this segment
        if len(medium_text) >= len(small_text):
            results.append((annot_seg, medium_text))
        else:
            results.append((annot_seg, small_text))

    return results, {"small": small_result, "medium": medium_result}
