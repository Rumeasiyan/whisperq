#!/usr/bin/env python3
"""Transcribe with AssemblyAI instead of the local CPU, keeping speaker labels.

Usage:  python scripts/assemblyai_transcribe.py ["file1.mp4" ...]
        With no args, processes every media file in input/.

This is an opt-in alternative to mps_pipeline.py, not a replacement. It exists
because ASR is the only slow stage locally -- measured at 1.29x realtime for
large-v3 on this machine, so the 15.3-hour module 03 batch is about 20 hours of
saturated CPU. Diarization on MPS and alignment are minutes by comparison.

PRIVACY. This uploads the audio to a third party. The recordings are
third-party copyright and contain identifiable speech, and an upload cannot be
undone -- the provider may retain, cache or log it regardless of what happens
here afterwards. That is why this lives in its own script that must be invoked
deliberately, rather than behind a flag on the local pipeline where someone
could reach it by accident. Consent is per batch, not standing.

Output matches mps_pipeline.py closely enough that build_clean_srt.py and
burn_subs.sh work downstream unchanged: a .json of {segments:[{start, end,
text, speaker}]}, plus .srt and .txt.
"""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import OUTDIR, list_media, is_done, load_env

load_env()

import subprocess
import requests

API = "https://api.assemblyai.com/v2"
LANG = os.environ.get("WQ_LANG") or "en"

# AssemblyAI's default model is used unless this names another. Deliberately not
# defaulted to a specific model string: a wrong identifier fails the request
# outright, and their default already includes diarization.
SPEECH_MODEL = os.environ.get("WQ_AAI_MODEL") or None

POLL_SECONDS = 15


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def extract_audio(src, dst):
    """Downmix to 16 kHz mono Opus before upload.

    The source videos are hundreds of MB each and only the audio is needed.
    Opus at 24 kbps mono is transparent enough for speech recognition while
    turning a 5-hour lecture into tens of megabytes, which keeps the upload from
    becoming the slowest part of a job whose entire purpose is to be fast.
    """
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", src,
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k",
         dst],
        check=True,
    )


def upload(path, key):
    with open(path, "rb") as fh:
        r = requests.post(f"{API}/upload", headers={"authorization": key}, data=fh)
    r.raise_for_status()
    return r.json()["upload_url"]


def submit(audio_url, key):
    body = {"audio_url": audio_url, "speaker_labels": True, "language_code": LANG}
    if SPEECH_MODEL:
        body["speech_model"] = SPEECH_MODEL
    r = requests.post(f"{API}/transcript", headers={"authorization": key}, json=body)
    if r.status_code >= 400:
        # The API explains refusals (bad model name, unsupported language) in the
        # body; raise_for_status alone would discard exactly the useful part.
        raise RuntimeError(f"submit failed {r.status_code}: {r.text[:400]}")
    return r.json()["id"]


def wait(tid, key):
    while True:
        r = requests.get(f"{API}/transcript/{tid}", headers={"authorization": key})
        r.raise_for_status()
        d = r.json()
        status = d["status"]
        if status == "completed":
            return d
        if status == "error":
            raise RuntimeError(f"transcription failed: {d.get('error')}")
        time.sleep(POLL_SECONDS)


def to_segments(d):
    """AssemblyAI utterances -> whisperx-shaped segments.

    Utterances are already grouped by speaker turn, which is the granularity
    build_clean_srt.py wants. Times are milliseconds there and seconds here.
    """
    segs = []
    for u in d.get("utterances") or []:
        segs.append({
            "start": u["start"] / 1000.0,
            "end": u["end"] / 1000.0,
            "text": (u.get("text") or "").strip(),
            # Normalised to SPEAKER_00 form so downstream code and the existing
            # transcripts label speakers the same way. AssemblyAI numbers
            # speakers "A", "B", ... instead.
            "speaker": f"SPEAKER_{ord(u['speaker']) - 65:02d}" if len(u.get("speaker","")) == 1 else u.get("speaker"),
        })
    return segs


def ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int(round((t - int(t)) * 1000)):03d}"


def write_outputs(base, segs, lang):
    json.dump({"segments": segs, "language": lang},
              open(os.path.join(OUTDIR, base + ".json"), "w"), ensure_ascii=False)
    with open(os.path.join(OUTDIR, base + ".srt"), "w") as fh:
        for i, s in enumerate(segs, 1):
            fh.write(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n"
                     f"[{s['speaker']}] {s['text']}\n\n")
    with open(os.path.join(OUTDIR, base + ".txt"), "w") as fh:
        for s in segs:
            fh.write(f"[{s['speaker']}] {s['text']}\n")


def main(files):
    key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not key:
        sys.exit("ERROR: ASSEMBLYAI_API_KEY not set. Add it to .env "
                 "(see .env.example). Nothing was uploaded.")
    os.makedirs(OUTDIR, exist_ok=True)
    tmpdir = os.path.join(OUTDIR, ".aai_tmp")
    os.makedirs(tmpdir, exist_ok=True)

    todo = [f for f in files if not is_done(f)]
    log(f"{len(todo)}/{len(files)} files to process (rest already done)")
    if not todo:
        return
    log(f"UPLOADING {len(todo)} file(s) to AssemblyAI. Audio leaves this machine.")

    for i, f in enumerate(todo, 1):
        base = os.path.splitext(os.path.basename(f))[0]
        log(f"=== [{i}/{len(todo)}] {base} ===")
        t0 = time.time()
        audio = os.path.join(tmpdir, base + ".opus")
        try:
            log("extracting audio...")
            extract_audio(f, audio)
            mb = os.path.getsize(audio) / 1e6
            log(f"uploading ({mb:.1f} MB)...")
            url = upload(audio, key)
            log("submitted; waiting for transcription...")
            d = wait(submit(url, key), key)
            segs = to_segments(d)
            if not segs:
                log("WARNING: no utterances returned; writing nothing for this file")
                continue
            write_outputs(base, segs, d.get("language_code", LANG))
            spk = len({s["speaker"] for s in segs})
            cov = sum(s["end"] - s["start"] for s in segs)
            log(f"DONE {base}  segments={len(segs)} speakers={spk} "
                f"speech={cov/60:.0f} min  ({(time.time()-t0)/60:.1f} min wall)")
        finally:
            # The extracted audio is a copy of personal speech; do not leave it
            # lying around once the upload is done.
            if os.path.exists(audio):
                os.remove(audio)

    log("ALL DONE")


if __name__ == "__main__":
    main(sys.argv[1:] or list_media())
