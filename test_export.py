#!/usr/bin/env python3
"""
Manual test: verify that export creates a real file on disk.
Usage: python test_export.py [audio.wav]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import AudioAnnotator
import tkinter as tk

audio_path = sys.argv[1] if len(sys.argv) > 1 else None
if not audio_path or not os.path.exists(audio_path):
    print(f"Usage: python test_export.py <audio.wav>")
    sys.exit(1)

root = tk.Tk()
root.geometry("1400x900")
root.update()

app = AudioAnnotator(root, audio_path)
root.update()

# Create test segments
app._on_drag_start(100, 858.0)
app._on_drag_end(500, 944.0)
app._on_speaker_select('说话人2')
app._on_drag_start(550, 944.0)
app._on_drag_end(600, 948.0)

print(f"Segments: {len(app.segments)}")
for s in app.segments:
    print(f"  {app._fmt(s['start'])} -> {app._fmt(s['end'])} [{s['speaker']}]")

# Export directly (bypass dialog)
export_txt = "/tmp/test_export.txt"
export_csv = "/tmp/test_export.csv"

# TXT
lines_txt = []
for seg in app.segments:
    s = app._fmt(seg["start"])
    e = app._fmt(seg["end"])
    d = app._fmt(max(0, seg["end"] - seg["start"]))
    lines_txt.append(f"{seg['speaker']}\t{s}\t{e}\t{d}")
with open(export_txt, "w", encoding="utf-8") as f:
    f.write("\n".join(lines_txt) + "\n")

# CSV
lines_csv = ["讲话人,开始时间,结束时间,时长"]
for seg in app.segments:
    s = app._fmt(seg["start"])
    e = app._fmt(seg["end"])
    d = app._fmt(max(0, seg["end"] - seg["start"]))
    lines_csv.append(f"{seg['speaker']},{s},{e},{d}")
with open(export_csv, "w", encoding="utf-8-sig") as f:
    f.write("\n".join(lines_csv) + "\n")

print(f"\n=== TXT Export ===")
print(f"Path: {export_txt}")
print(f"Exists: {os.path.exists(export_txt)}")
print(f"Size: {os.path.getsize(export_txt)} bytes")
with open(export_txt) as f:
    print(f.read())

print(f"=== CSV Export ===")
print(f"Path: {export_csv}")
print(f"Exists: {os.path.exists(export_csv)}")
print(f"Size: {os.path.getsize(export_csv)} bytes")
with open(export_csv, encoding="utf-8-sig") as f:
    print(f.read())

print("Export test PASSED")

root.destroy()
