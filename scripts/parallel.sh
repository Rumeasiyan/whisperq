#!/usr/bin/env bash
# N-worker parallel transcription pool. Each worker atomically claims the next
# unprocessed file via `mkdir` (atomic lock), so no file is done twice.
# Files are ordered largest-first (see list_media) so the lanes stay balanced.
# Usage: ./scripts/parallel.sh [worker_count]   (default 2)

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

WORKERS="${1:-2}"
LOCKDIR="$OUTDIR/.locks"
mkdir -p "$LOCKDIR"

read_media_into FILES
echo "Pool: $WORKERS workers, ${#FILES[@]} candidate files."

worker() {
  local wid="$1"
  for f in "${FILES[@]}"; do
    local base; base="$(basename "${f%.*}")"
    # Atomic claim: mkdir succeeds for exactly one worker.
    if ! mkdir "$LOCKDIR/$base" 2>/dev/null; then
      continue   # already claimed by another worker
    fi
    if is_done "$f"; then
      echo "[w$wid] SKIP (done): $base"
      continue
    fi
    echo "[w$wid] START: $base"
    whisperx "$f" \
      --model large-v3 --language en --device cpu --compute_type int8 \
      --diarize --hf_token "$HF_TOKEN" \
      --output_dir "$OUTDIR" --output_format all --print_progress True \
      > "$OUTDIR/_w${wid}_${base}.log" 2>&1
    echo "[w$wid] DONE ($?): $base"
  done
  echo "[w$wid] EXIT"
}

for ((i = 1; i <= WORKERS; i++)); do
  worker "$i" &
done
wait
echo "POOL DONE"
