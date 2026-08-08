# WhisperQ

Transcribe long recordings with [WhisperX](https://github.com/m-bain/whisperX),
label who spoke via pyannote diarization, and attach the result to the video as
a subtitle track.

Built for lecture recordings — multi-hour, multi-speaker, and too many of them
to babysit one at a time.

> **macOS / Apple Silicon only right now.** Three of the four things blocking
> Linux live in a single 90-line file. See [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

## Why this exists

`pip install whisperx` gets you transcription. It does not get you diarization
running at a usable speed on a Mac. Two things stand in the way, neither of them
documented upstream:

- **CTranslate2 — WhisperX's ASR backend — has no Metal backend.** Passing
  `device="mps"` doesn't raise an error; it silently degrades. Only the pyannote
  diarization stage can use the GPU, where it runs roughly **8× faster** than on
  CPU. `scripts/mps_pipeline.py` splits the pipeline accordingly: ASR and
  alignment on CPU, diarization on MPS.
- **torchcodec (via pyannote 4.x) links against ffmpeg 4–7**, but Homebrew's
  default `ffmpeg` is v8. The mismatch fails inside a native library, so the
  Python traceback is useless and never mentions ffmpeg. `scripts/config.sh`
  points the dynamic loader at the `ffmpeg@7` libs.

That knowledge is the actual content of this repo. The rest is plumbing.

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

`mp4 m4a mov mkv wav mp3 webm` are all accepted; files are processed
largest-first so a parallel run doesn't end with one lane grinding alone.

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

## Contributing

See [AGENTS.md](AGENTS.md) for conventions, constraints, and the workflow.
Work happens on branches with PRs into `main`.

## Licence

MIT — see [LICENSE](LICENSE).

The licence covers this code only. Recordings and transcripts you process are
yours to handle: lecture recordings are typically the institution's copyright,
and diarized transcripts are identifiable personal speech. Don't publish them.
