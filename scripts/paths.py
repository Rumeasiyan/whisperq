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


def is_done(src):
    """True when src has already been transcribed and needs no rerun.

    Mirrors is_done() in config.sh -- keep the two in step. Completion is judged
    on the .json, not the .srt: WhisperX writes the .srt incrementally, so a run
    killed midway leaves a partial .srt that a size check treats as finished
    forever. The .json is written once at the end, after diarization.

    FORCE=1 in the environment reprocesses everything.
    """
    if os.environ.get("FORCE") == "1":
        return False
    base = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(OUTDIR, base + ".json")
    return os.path.isfile(dst) and os.path.getsize(dst) > 0
