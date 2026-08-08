"""Shared repo paths for the Python scripts.

Everything is resolved from this file's own location, so scripts work no matter
what directory they're invoked from.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDIR = os.path.join(ROOT, "input")
OUTDIR = os.path.join(ROOT, "output", "transcripts")
SUBDIR = os.path.join(ROOT, "output", "subbed")

MEDIA_EXTS = (".mp4", ".m4a", ".mov", ".mkv", ".wav", ".mp3", ".webm")


def list_media():
    """All media files in input/, largest-first."""
    files = [
        os.path.join(INDIR, f)
        for f in os.listdir(INDIR)
        if f.lower().endswith(MEDIA_EXTS) and not f.startswith(".")
    ]
    return sorted(files, key=os.path.getsize, reverse=True)
