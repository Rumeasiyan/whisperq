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


def load_env():
    """Load .env into os.environ, without overwriting anything already set.

    config.sh does this for the shell entrypoints, but mps_pipeline.py is run
    directly (python scripts/mps_pipeline.py) and so never passes through it.
    Without this, HF_TOKEN and the WQ_* settings only reach the Python path if
    the caller exported them by hand. Values already in the environment win, so
    an inline override still beats the file.
    """
    path = os.path.join(ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, sep, val = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            val = val.strip().strip("'\"")
            os.environ.setdefault(key, val)


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
