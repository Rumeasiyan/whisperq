# WhisperQ

Turn a folder of long recordings into speaker-labelled transcripts and subtitled
video. Point it at `input/`, run it, come back later.

Built for lecture recordings — multi-hour, multi-speaker, and too many of them to
babysit one at a time.

> **macOS / Apple Silicon only right now.** Three of the four things blocking
> Linux live in a single 90-line file. See [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

## Why WhisperQ exists

[WhisperX](https://github.com/m-bain/whisperX) gives you transcription and
diarization. What it doesn't give you is either of them running at a usable
speed on a Mac, or an answer for what to do with 40 files. WhisperQ is the layer
that solves both.

**The device split.** The obvious move on Apple Silicon — put everything on the
GPU — cannot work. CTranslate2, the ASR backend, has no Metal backend at all,
and passing `device="mps"` doesn't raise an error; it silently degrades. Only
the pyannote diarization stage genuinely benefits from MPS, where it runs
roughly **8× faster** than on CPU. WhisperQ splits the pipeline accordingly:
ASR and alignment on CPU, diarization on MPS.

**The linker conflict.** torchcodec, pulled in by pyannote 4.x, links against
ffmpeg 4–7 shared libraries. Homebrew's default `ffmpeg` is v8. The mismatch
fails inside a native library, so the Python traceback is useless and never
mentions ffmpeg. WhisperQ points the dynamic loader at the `ffmpeg@7` libs and
warns you if they're missing.

**Batch behaviour.** Finished files are skipped, so an interrupted run resumes
instead of restarting. Work is claimed with atomic locks, so parallel workers
never collide. Files run largest-first, so a long one doesn't strand the other
workers idle at the end.

**Readable subtitles.** WhisperX's word-level `.srt` is one cue per *word* —
unusable on screen. WhisperQ rebuilds segment-level cues from the `.json`,
repairs overlapping and zero-length cues that some players reject outright, and
prints a speaker label only when the speaker actually changes.

## Layout

```
input/                 raw recordings                          (gitignored)
output/transcripts/    .txt .srt .vtt .json .tsv + .clean.srt  (gitignored)
output/subbed/         videos with a subtitle track            (gitignored)
scripts/
  config.sh            shared paths, venv, .env, ffmpeg@7 linker fix
  paths.py             the same, for the Python scripts
  transcribe.sh        sequential batch transcribe (CPU)
  parallel.sh          N-worker pool, atomic mkdir locks
  mps_pipeline.py      CPU ASR + MPS diarization — the fast path
  build_clean_srt.py   word-level .srt -> readable segment-level .clean.srt
  burn_subs.sh         attach subtitles to video (soft-mux or hard burn)
  mps_diarize_test.py  benchmark diarization, mps vs cpu
docs/
  DECISIONS.md         why the architecture is the way it is
  BUILD_PLAN.md        roadmap, including cross-platform support
```

Nothing under `input/` or `output/` is ever committed.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg@7          # needed even if you already have ffmpeg
cp .env.example .env           # then paste your HuggingFace token in
```

Accept the pyannote model licences on HuggingFace (both are listed in
`.env.example`) using the same account as your token — diarization returns a
401 until you do.

## Use

Drop recordings into `input/`, then:

```bash
python scripts/mps_pipeline.py       # CPU ASR + MPS diarization (fastest)
# or
./scripts/transcribe.sh              # sequential, CPU only
./scripts/parallel.sh 2              # 2-worker pool, CPU only

python scripts/build_clean_srt.py    # -> output/transcripts/*.clean.srt
./scripts/burn_subs.sh               # -> output/subbed/*.subbed.mp4
```

Already-transcribed files are skipped. `FORCE=1` reprocesses everything.

`mp4 m4a mov mkv wav mp3 webm` are all accepted.

### Subtitles: soft vs hard

`burn_subs.sh` defaults to **soft** — it adds a `mov_text` track and
stream-copies the video, taking seconds per file with no quality loss, and the
viewer can toggle subtitles off. VLC and QuickTime display these; some players
don't.

`./scripts/burn_subs.sh hard` re-encodes with the subtitles painted into the
pixels. Hours per file and a generation of quality loss, but they survive any
player or upload.

## Notes

- The default of 2 parallel workers is about memory, not cores — each worker
  holds its own model and decoded audio.
- If a run is interrupted, clear `output/transcripts/.locks/` before retrying
  those files.
- Completion is judged on the `.json`, not the `.srt`. The `.srt` is written
  incrementally, so a killed run leaves a truncated one that looks finished.

## Built on

WhisperQ is orchestration around excellent upstream work:

| | |
|---|---|
| [WhisperX](https://github.com/m-bain/whisperX) | ASR, forced alignment, diarization plumbing (BSD-2) |
| [pyannote.audio](https://github.com/pyannote/pyannote-audio) | Speaker diarization models (MIT; models separately licence-gated) |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | Fast Whisper inference (MIT) |
| [ffmpeg](https://ffmpeg.org) | Decoding and muxing |

## Contributing

See [AGENTS.md](AGENTS.md) for conventions, constraints, and the workflow.
Work happens on branches with PRs into `main`.

## Licence

MIT — see [LICENSE](LICENSE).

The licence covers this code only. Recordings and transcripts you process are
yours to handle: lecture recordings are typically the institution's copyright,
and diarized transcripts are identifiable personal speech. Don't publish them.
