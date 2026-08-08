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
from paths import OUTDIR, list_media, is_done

import torch
import whisperx
from whisperx.diarize import DiarizationPipeline, assign_word_speakers
from whisperx.utils import get_writer

MODEL       = "medium"
LANG        = "en"
COMPUTE     = "int8"
THREADS     = 8
DIARIZE_MODEL = "pyannote/speaker-diarization-community-1"
WRITER_ARGS = {"highlight_words": False, "max_line_count": 0, "max_line_width": 0}

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

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
    log("loading alignment model (cpu)...")
    align_model, align_meta = whisperx.load_align_model(LANG, "cpu")
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

        log("aligning (cpu)...")
        result = whisperx.align(result["segments"], align_model, align_meta,
                                audio, "cpu", return_char_alignments=False)

        log("diarizing (mps)...")
        diar = diarizer(audio)
        result = assign_word_speakers(diar, result)

        result["language"] = LANG
        writer(result, f, WRITER_ARGS)
        del audio, result, diar
        gc.collect()
        log(f"DONE {base}  ({dur:.0f} min audio in {(time.time()-t0)/60:.1f} min wall)")

    log("ALL DONE")

if __name__ == "__main__":
    main(sys.argv[1:] or list_media())
