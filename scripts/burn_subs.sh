#!/usr/bin/env bash
# Attach the generated .clean.srt to each source video, writing to output/subbed/.
#
# Two modes:
#   soft (default)  add a mov_text subtitle track, stream-copy video+audio.
#                   Seconds per file, no quality loss, viewer can toggle subs off.
#                   Not all players show mov_text -- VLC and QuickTime do.
#   hard            re-encode with the subtitles painted into the pixels.
#                   Hours per file and a generation of quality loss, but the
#                   subtitles survive any player, upload, or transcode.
#
# Usage: ./scripts/burn_subs.sh [soft|hard]

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

MODE="${1:-soft}"
if [[ "$MODE" != "soft" && "$MODE" != "hard" ]]; then
  echo "ERROR: mode must be 'soft' or 'hard', got '$MODE'" >&2
  exit 1
fi

# Style for hard mode. force_style is libass syntax; PrimaryColour is &HBBGGAA
# (blue-green-red), NOT RGB -- &H00FFFFFF is opaque white.
SUB_STYLE="FontName=Helvetica,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=30"

read_media_into FILES
echo "Mode: $MODE. ${#FILES[@]} candidate files."

done_count=0
skip_count=0

for src in "${FILES[@]}"; do
  base="$(basename "${src%.*}")"
  srt="$OUTDIR/${base}.clean.srt"
  dst="$SUBDIR/${base}.subbed.mp4"

  if [[ ! -s "$srt" ]]; then
    echo "SKIP (no .clean.srt -- run build_clean_srt.py first): $base"
    skip_count=$((skip_count + 1))
    continue
  fi
  if [[ -s "$dst" ]]; then
    echo "SKIP (already subbed): $base"
    skip_count=$((skip_count + 1))
    continue
  fi

  echo "=============================================="
  echo "Subbing ($MODE): $base"
  echo "=============================================="

  # Write to a .part file so an interrupted run never leaves a truncated .mp4
  # that the -s check above would mistake for a finished one.
  part="${dst}.part"

  if [[ "$MODE" == "soft" ]]; then
    ffmpeg -nostdin -y -i "$src" -i "$srt" \
      -map 0 -map 1 \
      -c copy -c:s mov_text \
      -metadata:s:s:0 language=eng \
      "$part"
  else
    # subtitles= filter needs the path escaped: ':' and ',' are filter syntax.
    esc_srt="$(printf '%s' "$srt" | sed -e 's/\\/\\\\/g' -e "s/'/\\\\'/g" -e 's/:/\\:/g')"
    ffmpeg -nostdin -y -i "$src" \
      -vf "subtitles='${esc_srt}':force_style='${SUB_STYLE}'" \
      -c:a copy \
      "$part"
  fi

  rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "FAILED (ffmpeg exit $rc): $base" >&2
    rm -f "$part"
    continue
  fi
  mv "$part" "$dst"
  echo "DONE: $(basename "$dst")"
  done_count=$((done_count + 1))
done

echo "SUBBING DONE. $done_count written, $skip_count skipped. Output in $SUBDIR"
