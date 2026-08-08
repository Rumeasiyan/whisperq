#!/usr/bin/env bash
# Batch-transcribe everything in input/ with WhisperX (+ speaker diarization).
# Usage: ./scripts/transcribe.sh

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

MODEL="medium"
LANG="en"
# CTranslate2 has no MPS backend, so compute runs on CPU. int8 keeps it fast + low-RAM.
DEVICE="cpu"
COMPUTE="int8"

read_media_into files
echo "Found ${#files[@]} recordings in $INDIR."

for f in "${files[@]}"; do
  if is_done "$f"; then
    echo "SKIP (done): $(basename "$f")"
    continue
  fi
  echo "=============================================="
  echo "Transcribing: $(basename "$f")"
  echo "=============================================="
  whisperx "$f" \
    --model "$MODEL" \
    --language "$LANG" \
    --device "$DEVICE" \
    --compute_type "$COMPUTE" \
    --threads 8 \
    --diarize \
    --hf_token "$HF_TOKEN" \
    --output_dir "$OUTDIR" \
    --output_format all \
    --print_progress True
  echo "Done: $(basename "$f")"
done

echo "ALL DONE. Outputs in $OUTDIR (.txt .srt .vtt .json with speaker labels)"
