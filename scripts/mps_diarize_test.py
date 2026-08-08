#!/usr/bin/env python3
"""Measure pyannote diarization speed on MPS vs the known CPU baseline.
Runs diarization only (community-1) on the smallest file in input/.
Usage: python scripts/mps_diarize_test.py [mps|cpu]"""
import os, sys, time
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # unsupported ops -> CPU
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import list_media

import torch
from whisperx.diarize import DiarizationPipeline

# Smallest media file in input/ -- shortest benchmark run.
AUDIO = list_media()[-1]
hf = os.environ["HF_TOKEN"]
dev = sys.argv[1] if len(sys.argv) > 1 else "mps"

print(f"device={dev}  loading diarization model...", flush=True)
t0 = time.time()
pipe = DiarizationPipeline(token=hf, device=dev)
print(f"model loaded in {time.time()-t0:.1f}s; diarizing...", flush=True)
t1 = time.time()
result = pipe(AUDIO)
dt = time.time() - t1
print(f"DIARIZE_SECONDS={dt:.1f}", flush=True)
print(f"segments={len(result)}", flush=True)
