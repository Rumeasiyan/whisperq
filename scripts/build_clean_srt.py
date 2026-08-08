#!/usr/bin/env python3
"""Build readable, segment-level .srt from whisperx .json (the raw .srt is
one-word-per-cue and unusable on screen). Speaker label is shown only when the
speaker changes, so multi-speaker crosstalk stays legible.
Output: <base>.clean.srt next to each .json."""
import json, glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import OUTDIR

def ts(t):
    if t is None: t = 0.0
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000: s += 1; ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

for jf in sorted(glob.glob(os.path.join(OUTDIR, "*.json"))):
    segs = json.load(open(jf)).get("segments", [])
    out, n, prev_spk, prev_end = [], 0, None, None
    for seg in segs:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = seg.get("start"); end = seg.get("end")
        if start is None:
            continue
        if end is None or end <= start:
            end = start + 1.2                       # give sub a readable min duration
        if prev_end is not None and start < prev_end:
            start = prev_end                        # avoid overlap with previous cue
        if end <= start:
            end = start + 0.3
        spk = seg.get("speaker")
        label = f"[{spk}] " if spk and spk != prev_spk else ""
        prev_spk = spk if spk else prev_spk
        prev_end = end
        n += 1
        out.append(f"{n}\n{ts(start)} --> {ts(end)}\n{label}{text}\n")
    dst = jf[:-5] + ".clean.srt"
    open(dst, "w").write("\n".join(out) + "\n")
    print(f"{os.path.basename(dst)}: {n} cues")
