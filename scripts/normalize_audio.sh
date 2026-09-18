#!/usr/bin/env bash
# Normalize recordings whose speech level swings too much for the pipeline to
# hear reliably, writing 16 kHz mono WAVs to output/normalized/.
#
# Usage: ./scripts/normalize_audio.sh ["file1.m4a" ...]
#        With no args, processes every media file in input/.
#
# This exists because of what the industry recordings measured at: a mean volume
# around -31 dB with peaks already at 0 dBFS, and a loudness range of 18.7 LU
# against the ~7 LU typical of broadcast speech. That combination is not "quiet
# audio" -- it is quiet speech sitting next to occasional full-scale transients,
# so a flat gain increase cannot fix it. It would only clip the peaks harder.
#
# The cost of leaving it alone is not just a worse transcript. WhisperX gates the
# ASR behind pyannote VAD, and quiet speech below the VAD threshold is discarded
# as silence before Whisper ever sees it -- the words go missing rather than
# coming out wrong. Diarization reads the same audio and loses the same passages.

set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

NORMDIR="$ROOT/output/normalized"
mkdir -p "$NORMDIR"

# 16 kHz mono is what Whisper consumes internally, so resampling here costs
# nothing and saves the pipeline doing it again per file.
RATE=16000

# Filter chain, in order. Each stage earns its place:
#
#   highpass=f=70   Room rumble and handling noise live below the voice. An
#                   adult fundamental bottoms out near 85 Hz, so 70 Hz clears
#                   the noise without touching speech. Done first so the later
#                   stages do not spend their gain amplifying it.
#
#   afftdn          Light spectral denoise. Not for listening quality -- it is
#                   here because the next stage raises quiet passages by a large
#                   factor, and amplified background hiss is a documented cause
#                   of Whisper hallucinating text over silence. nr=10 is gentle
#                   on purpose; heavier settings chew into consonants, which is
#                   where the intelligibility actually lives.
#
#   speechnorm      The stage that matters. Purpose-built for speech with an
#                   uneven level: it tracks per-utterance peaks and expands
#                   quiet ones toward the target, with limiting built in so the
#                   already-clipped loud parts are not pushed further. A
#                   compressor would squash the loud parts down instead; here
#                   the quiet parts are the problem, so expansion is the right
#                   direction. e=12.5 is a high ceiling on expansion, which this
#                   material needs -- it is a maximum, not a fixed gain.
#
#   loudnorm        Single-pass EBU R128 to a fixed target, so every file lands
#                   at the same level regardless of how it started. These four
#                   range from -25 to -37 dB mean, and a per-file target is what
#                   stops the pipeline behaving differently on each one.
#                   I=-18 is a little hotter than the -23 broadcast standard,
#                   which suits speech-only material with no music to leave room
#                   for.
#
#   alimiter        Backstop. loudnorm's single-pass mode predicts true peak
#                   rather than measuring it, so it can overshoot. This catches
#                   anything that does.
FILTERS="${WQ_FILTERS:-highpass=f=70,afftdn=nr=10:nf=-25,speechnorm=e=12.5:r=0.0001:l=1,loudnorm=I=-18:TP=-2:LRA=9,alimiter=limit=0.95}"

read_media_into files
if [[ $# -gt 0 ]]; then
  files=("$@")
fi

echo "Normalizing ${#files[@]} file(s) -> $NORMDIR"
echo "Filters: $FILTERS"
echo

done_count=0
for f in "${files[@]}"; do
  base="$(basename "${f%.*}")"
  dst="$NORMDIR/${base}.wav"

  # Same reasoning as is_done(): write to a .part first so an interrupted run
  # cannot leave a truncated WAV that the -s check below mistakes for finished.
  if [[ -s "$dst" && "${FORCE:-0}" != "1" ]]; then
    echo "SKIP (done): $base"
    continue
  fi

  echo "=============================================="
  echo "Normalizing: $base"
  echo "=============================================="
  part="${dst}.part"

  # -f wav is not optional: ffmpeg picks the muxer from the file extension, and
  # the .part suffix leaves it with ".part", which it cannot resolve --
  # "Unable to choose an output format". The format has to be stated explicitly
  # whenever the temp-file trick hides the real extension.
  ffmpeg -nostdin -y -i "$f" \
    -af "$FILTERS" \
    -ar "$RATE" -ac 1 -c:a pcm_s16le \
    -f wav "$part"

  rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "FAILED (ffmpeg exit $rc): $base" >&2
    rm -f "$part"
    continue
  fi
  mv "$part" "$dst"

  # Report what actually came out, not what was requested -- the whole point of
  # this script is a level claim, and an unverified one is worth nothing.
  echo "--- result ---"
  ffmpeg -nostdin -hide_banner -i "$dst" -af volumedetect -f null - 2>&1 \
    | grep -E "mean_volume|max_volume"
  echo "DONE: $base"
  done_count=$((done_count + 1))
done

echo
echo "Normalized $done_count file(s). Output in $NORMDIR"
echo "Feed these to the pipeline, e.g.:"
echo "  python scripts/mps_pipeline.py \"$NORMDIR\"/*.wav"
