#!/usr/bin/env python3
"""OCR every frame of an analyzed video into a timestamped text timeline.

Usage:
    python3 ocr_timeline.py <frames_dir> [--cache-dir <dir>] [--lang eng+vie]

Each frame is scaled to 1920px (ImageMagick, when available) and OCR'd with
tesseract --psm 11. Output is markdown on stdout: one section per frame that
contains text, heading carries the frame timestamp from evidence.json when
available (frames_dir's parent is checked automatically).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def find_convert() -> list[str] | None:
    for tool in ("magick", "convert"):
        path = shutil.which(tool)
        if path:
            return [path, "convert"] if tool == "magick" else [path]
    return None


def load_timestamps(cache_dir: Path | None, frames_dir: Path) -> dict[str, float]:
    candidates = []
    if cache_dir:
        candidates.append(cache_dir / "evidence.json")
    candidates.append(frames_dir.parent / "evidence.json")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stamps: dict[str, float] = {}
        for frame in data.get("frames", []):
            frame_path = frame.get("path")
            if not frame_path:
                continue
            try:
                stamps[Path(frame_path).name] = float(frame.get("timestamp", 0.0))
            except (TypeError, ValueError):
                continue
        if stamps:
            return stamps
    return {}


def ocr_frame(image: Path, convert: list[str] | None, lang: str, tmp_dir: Path) -> str:
    target = image
    if convert:
        resized = tmp_dir / (image.stem + ".png")
        try:
            subprocess.run(
                convert + [str(image), "-resize", "1920x", "-colorspace", "Gray", str(resized)],
                capture_output=True,
                timeout=60,
            )
            if resized.is_file():
                target = resized
        except Exception:
            pass
    proc = subprocess.run(
        ["tesseract", str(target), "stdout", "-l", lang, "--psm", "11"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return ""
    lines = (line.strip() for line in proc.stdout.splitlines())
    return "\n".join(line for line in lines if line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames_dir", type=Path, help="directory with frame_0001.jpg, ...")
    parser.add_argument("--cache-dir", type=Path, default=None, help="cache dir with evidence.json")
    parser.add_argument("--lang", default="eng+vie", help="tesseract language(s)")
    args = parser.parse_args()

    if shutil.which("tesseract") is None:
        print("tesseract not found in PATH", file=sys.stderr)
        return 1
    if not args.frames_dir.is_dir():
        print(f"not a directory: {args.frames_dir}", file=sys.stderr)
        return 1

    frames = sorted(
        p for p in args.frames_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not frames:
        print(f"no frames found in {args.frames_dir}", file=sys.stderr)
        return 1

    timestamps = load_timestamps(args.cache_dir, args.frames_dir)
    convert = find_convert()
    printed_any = False
    with tempfile.TemporaryDirectory(prefix="ocr-timeline-") as tmp:
        tmp_dir = Path(tmp)
        for frame in frames:
            text = ocr_frame(frame, convert, args.lang, tmp_dir)
            if not text:
                continue
            if printed_any:
                print()
            printed_any = True
            ts = timestamps.get(frame.name)
            stamp = f" ({ts:.2f}s)" if ts is not None else ""
            print(f"## {frame.name}{stamp}")
            print(text)
    if not printed_any:
        print("(no text detected in any frame)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
