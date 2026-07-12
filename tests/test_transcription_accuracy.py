#!/usr/bin/env python3
"""
Transcription accuracy test.
Transcribes testdata audio with small model (default zh),
saves results, and compares against expected text.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transcriber import FasterWhisperTranscriber, transcribe_audio_segment
from models import Segment

TESTDATA_DIR = Path(__file__).resolve().parent.parent / "testdata"
AUDIO_PATH = TESTDATA_DIR / "3-数智办公四月第二次例会.wav"
OUTPUT_DIR = TESTDATA_DIR / "transcription_results"
MODEL_SIZES = ["small", "medium"]


def transcribe_full(audio_path, model_size="small", language="zh"):
    """Transcribe full audio file and return segments with timestamps."""
    print(f"\n{'='*60}")
    print(f"Model: {model_size} | Language: {language}")
    print(f"File: {audio_path.name}")
    print(f"{'='*60}")

    start_time = time.time()
    transcriber = FasterWhisperTranscriber(model_size=model_size, device="auto")

    segments, info = transcriber.model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
        beam_size=5,
        word_timestamps=True,
    )

    result_segments = []
    for seg in segments:
        result_segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    elapsed = time.time() - start_time
    print(f"Detected language: {info.language} (prob: {info.language_probability:.2f})")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Segments: {len(result_segments)}")
    return result_segments, elapsed


def transcribe_segments_by_slice(audio_path, segments_data, model_size="small", language="zh"):
    """Transcribe each segment individually by slicing audio."""
    print(f"\n{'='*60}")
    print(f"Slice-based transcription | Model: {model_size}")
    print(f"{'='*60}")

    start_time = time.time()
    transcriber = FasterWhisperTranscriber(model_size=model_size, device="auto")

    results = []
    for seg in segments_data:
        segment = Segment(seg["start"], seg["end"], "test")
        text = transcribe_audio_segment(str(audio_path), segment, transcriber, language=language)
        results.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": text,
        })
        print(f"  [{seg['start']:.1f}s -> {seg['end']:.1f}s] {text[:60]}")

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s for {len(results)} segments")
    return results, elapsed


def save_results(results, elapsed, model_size, suffix=""):
    """Save transcription results to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"transcription_{model_size}{suffix}.json"
    payload = {
        "model": model_size,
        "elapsed_seconds": round(elapsed, 2),
        "segment_count": len(results),
        "total_chars": sum(len(r["text"]) for r in results),
        "segments": results,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {output_path}")
    return output_path


def compare_results(path_a, path_b):
    """Compare two transcription result files."""
    data_a = json.loads(path_a.read_text(encoding="utf-8"))
    data_b = json.loads(path_b.read_text(encoding="utf-8"))

    segs_a = { (s["start"], s["end"]): s["text"] for s in data_a["segments"] }
    segs_b = { (s["start"], s["end"]): s["text"] for s in data_b["segments"] }

    print(f"\n{'='*60}")
    print(f"Comparing: {path_a.name} vs {path_b.name}")
    print(f"{'='*60}")

    # Find matching segments
    all_keys = set(segs_a.keys()) | set(segs_b.keys())
    diffs = 0
    for key in sorted(all_keys):
        ta = segs_a.get(key, "<missing>")
        tb = segs_b.get(key, "<missing>")
        if ta != tb:
            diffs += 1
            if diffs <= 10:
                print(f"\n  [{key[0]:.1f}s -> {key[1]:.1f}s]")
                print(f"    A: {ta[:80]}")
                print(f"    B: {tb[:80]}")

    print(f"\nDifferences: {diffs}/{len(all_keys)} segments")


def print_summary(path):
    """Print a readable summary of transcription results."""
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"\n{'='*60}")
    print(f"Summary: {path.name}")
    print(f"Model: {data['model']} | Time: {data['elapsed_seconds']}s | Segments: {data['segment_count']}")
    print(f"Total chars: {data['total_chars']}")
    print(f"{'='*60}")
    for seg in data["segments"][:20]:
        print(f"  [{seg['start']:7.1f}s -> {seg['end']:7.1f}s] {seg['text'][:70]}")
    if len(data["segments"]) > 20:
        print(f"  ... and {len(data['segments']) - 20} more segments")


def main():
    if not AUDIO_PATH.exists():
        print(f"ERROR: test audio not found: {AUDIO_PATH}")
        sys.exit(1)

    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    results = {}

    # Test 1: Full-file transcription with small model
    segs_small, t_small = transcribe_full(AUDIO_PATH, model_size="small")
    path_small = save_results(segs_small, t_small, "small")
    print_summary(path_small)

    # Test 2: Full-file transcription with medium model
    segs_medium, t_medium = transcribe_full(AUDIO_PATH, model_size="medium")
    path_medium = save_results(segs_medium, t_medium, "medium")
    print_summary(path_medium)

    # Test 3: Slice-based transcription (simulates the actual annotation workflow)
    # Use first 10 segments of small model result as sample segments
    sample_segments = segs_small[:10]
    segs_slice, t_slice = transcribe_segments_by_slice(AUDIO_PATH, sample_segments, model_size="small")
    path_slice = save_results(segs_slice, t_slice, "small", "_slice")
    print_summary(path_slice)

    # Compare full vs slice for small model
    compare_results(path_small, path_slice)

    # Compare small vs medium
    compare_results(path_small, path_medium)

    print(f"\n{'='*60}")
    print("All results saved to:", OUTPUT_DIR)
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
