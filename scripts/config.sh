#!/usr/bin/env bash
# Shared config for all shell scripts. Source this, don't run it.
#   source "$(dirname "$0")/config.sh"
# Resolves repo paths, activates the venv, loads .env, and fixes the ffmpeg@7
# dylib path that torchcodec (pyannote diarization) needs.

# Repo root = parent of scripts/. All paths below are absolute so scripts work
# regardless of the caller's cwd.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INDIR="$ROOT/input"
OUTDIR="$ROOT/output/transcripts"
SUBDIR="$ROOT/output/subbed"
mkdir -p "$INDIR" "$OUTDIR" "$SUBDIR"

# Media extensions treated as transcribable input.
MEDIA_EXTS=(mp4 m4a mov mkv wav mp3 webm)

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "ERROR: HF_TOKEN not set. Copy .env.example to .env and fill it in." >&2
  exit 1
fi

# torchcodec needs ffmpeg 4-7 shared libs, but brew's default ffmpeg is v8.
# Point the dynamic loader at the ffmpeg@7 libs.
FF7LIB="$(brew --prefix ffmpeg@7 2>/dev/null)/lib"
if [[ -d "$FF7LIB" ]]; then
  export DYLD_FALLBACK_LIBRARY_PATH="$FF7LIB:${DYLD_FALLBACK_LIBRARY_PATH:-}"
else
  echo "WARN: ffmpeg@7 not found; diarization may fail. Run: brew install ffmpeg@7" >&2
fi

# Print every media file in input/, one per line, largest-first so parallel
# workers stay balanced (big files start early instead of straggling at the end).
# macOS ships bash 3.2, so no mapfile/readarray anywhere in these scripts.
list_media() {
  local args=() ext first=1
  for ext in "${MEDIA_EXTS[@]}"; do
    if [[ $first -eq 1 ]]; then first=0; else args+=(-o); fi
    args+=(-iname "*.${ext}")
  done
  find "$INDIR" -maxdepth 1 -type f \( "${args[@]}" \) -print0 \
    | xargs -0 stat -f '%z %N' \
    | sort -rn \
    | cut -d' ' -f2-
}

# Read list_media() output into an array named by $1. Newline-delimited, so a
# filename containing a newline would break it -- none do, and the alternative
# (NUL-delimited read) needs bash 4.
read_media_into() {
  local __name="$1" __line
  eval "$__name=()"
  while IFS= read -r __line; do
    [[ -n "$__line" ]] && eval "$__name+=(\"\$__line\")"
  done < <(list_media)
}

# True when $1 (a media path) has already been transcribed and needs no rerun.
#
# TODO(you): implement this. See the note in the conversation — this predicate
# decides what "already done" means, and every script's skip logic hangs off it.
is_done() {
  local src="$1"
  local base; base="$(basename "${src%.*}")"
  return 1
}
