"""Optional ASR backend for filling segment text from audio."""
from __future__ import annotations

import os
import tempfile

import soundfile as sf

from models import coerce_segment


class TranscriptionUnavailable(RuntimeError):
    pass


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

    def transcribe_with_timestamps(self, path, language="zh"):
        """Transcribe full file, return list of {start, end, text} with timestamps."""
        segments, info = self.model.transcribe(
            path,
            language=language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
            beam_size=5,
            word_timestamps=False,
        )
        results = []
        for seg in segments:
            results.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
        return results, info


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
