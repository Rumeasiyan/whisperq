#!/usr/bin/env python3
"""Transcribe lectures with diarization, splitting compute across devices:
  - ASR (CTranslate2) + alignment -> CPU  (MPS unsupported by CTranslate2)
  - pyannote diarization           -> MPS  (~8x faster than CPU here)

Usage:  python scripts/mps_pipeline.py ["file1.mp4" ...]
        With no args, processes every media file in input/.
Skips any file already transcribed (see is_done in paths.py). Models are loaded once
and reused; audio is freed after each file so RAM stays flat.
"""
import os, sys, gc, time
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # unsupported ops -> CPU

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import OUTDIR, list_media, is_done, load_env

load_env()

import torch
import whisperx
from whisperx.diarize import DiarizationPipeline, assign_word_speakers
from whisperx.utils import get_writer

# `or` not a get() default: config.sh exports WQ_MODEL as an empty string when
# it is unset, and "" is a value as far as get() is concerned.
MODEL       = os.environ.get("WQ_MODEL") or "medium"

# WQ_ prefix because LANG is the POSIX locale variable, already set to something
# like en_US.UTF-8 in any normal shell -- reading it would feed the locale
# string to WhisperX as a language code.
LANG        = os.environ.get("WQ_LANG") or "en"

# wav2vec2 CTC model for forced alignment. Empty means "use WhisperX's default
# for LANG", which only exists for ~40 of the ~99 languages Whisper transcribes.
ALIGN_MODEL = os.environ.get("WQ_ALIGN_MODEL", "") or None

COMPUTE     = "int8"
THREADS     = 8
DIARIZE_MODEL = "pyannote/speaker-diarization-community-1"
WRITER_ARGS = {"highlight_words": False, "max_line_count": 0, "max_line_width": 0}

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_alignment(lang, override):
    """Return (model, metadata) for forced alignment, or (None, None).

    Whisper transcribes ~99 languages but WhisperX only ships wav2vec2 alignment
    defaults for ~40 of them, so a language outside the smaller set raises
    ValueError -- previously after the ASR pass had already run, throwing away
    hours of CPU work. Returning None instead degrades the run to segment-level
    timestamps with no speaker labels, which is worse output but still output.
    Set WQ_ALIGN_MODEL to a HuggingFace wav2vec2 CTC model to get alignment back.
    """
    try:
        return whisperx.load_align_model(lang, "cpu", model_name=override)
    except Exception as e:
        log(f"WARNING: no alignment model for '{lang}': {e}")
        log("WARNING: continuing WITHOUT alignment -- no word timestamps, so no")
        log("WARNING: speaker labels either. Set WQ_ALIGN_MODEL to fix.")
        return None, None

def main(files):
    hf = os.environ["HF_TOKEN"]
    os.makedirs(OUTDIR, exist_ok=True)
    torch.set_num_threads(THREADS)
    writer = get_writer("all", OUTDIR)

    todo = [f for f in files if not is_done(f)]
    log(f"{len(todo)}/{len(files)} files to process (rest already done)")
    if not todo:
        return

    log(f"loading ASR model '{MODEL}' (cpu/{COMPUTE}, {THREADS} threads)...")
    asr = whisperx.load_model(MODEL, device="cpu", compute_type=COMPUTE,
                              language=LANG, threads=THREADS)
    log(f"loading alignment model for '{LANG}' (cpu)...")
    align_model, align_meta = load_alignment(LANG, ALIGN_MODEL)
    # Diarization output is only usable through word timestamps, so without an
    # alignment model there is nothing to spend the model load on.
    diarizer = None
    if align_model is not None:
        log(f"loading diarization model '{DIARIZE_MODEL}' (mps)...")
        diarizer = DiarizationPipeline(model_name=DIARIZE_MODEL, token=hf, device="mps")

    for i, f in enumerate(todo, 1):
        base = os.path.splitext(os.path.basename(f))[0]
        log(f"=== [{i}/{len(todo)}] {base} ===")
        t0 = time.time()
        audio = whisperx.load_audio(f)
        dur = len(audio) / 16000 / 60  # minutes

        log("transcribing (cpu)...")
        result = asr.transcribe(audio, batch_size=8, print_progress=True)

        if align_model is None:
            # No word timestamps, so assign_word_speakers has nothing to attach
            # speaker turns to. Segment timestamps from the ASR pass survive and
            # build_clean_srt.py still produces usable cues -- just unlabelled.
            log("SKIPPING alignment and diarization (no alignment model)")
        else:
            log("aligning (cpu)...")
            result = whisperx.align(result["segments"], align_model, align_meta,
                                    audio, "cpu", return_char_alignments=False)

            log("diarizing (mps)...")
            diar = diarizer(audio)
            result = assign_word_speakers(diar, result)

        result["language"] = LANG
        writer(result, f, WRITER_ARGS)
        del audio, result
        gc.collect()
        log(f"DONE {base}  ({dur:.0f} min audio in {(time.time()-t0)/60:.1f} min wall)")

    log("ALL DONE")

if __name__ == "__main__":
    main(sys.argv[1:] or list_media())
