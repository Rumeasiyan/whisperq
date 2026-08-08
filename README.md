# video-subbed-dubbed

Transcribe lecture recordings with WhisperX (+ pyannote speaker diarization),
then burn readable subtitles into the video.

Media never enters git — `input/` and `output/` are gitignored. Clone this repo
anywhere, drop recordings into `input/`, and run.

## Layout

```
input/                 raw recordings (gitignored)
output/transcripts/    .txt .srt .vtt .json .tsv + .clean.srt (gitignored)
output/subbed/         videos with burned-in subtitles (gitignored)
scripts/
  config.sh            shared paths, venv, .env, ffmpeg@7 dylib fix
  paths.py             same, for the Python scripts
  transcribe.sh        sequential batch transcribe
  parallel.sh          N-worker pool, atomic mkdir locks
  mps_pipeline.py      ASR on CPU + diarization on MPS (~8x faster diarization)
  build_clean_srt.py   raw one-word-per-cue .srt -> readable segment-level .srt
  mps_diarize_test.py  benchmark diarization on mps vs cpu
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg@7          # torchcodec needs ffmpeg 4-7 libs; brew default is v8
cp .env.example .env           # then paste your HF token in
```

Accept the pyannote model licences on HuggingFace (listed in `.env.example`) or
diarization returns a 401.

## Run

```bash
./scripts/transcribe.sh              # sequential
./scripts/parallel.sh 2              # 2-worker pool
python scripts/mps_pipeline.py       # CPU ASR + MPS diarization, all of input/
python scripts/build_clean_srt.py    # readable .clean.srt from the .json
```

## Notes

- CTranslate2 (WhisperX's ASR backend) has no MPS backend, so ASR always runs on
  CPU with `int8`. Only pyannote diarization benefits from MPS.
- `parallel.sh` claims files with `mkdir` on a lock dir — atomic, so two workers
  never take the same file. Delete `output/transcripts/.locks/` to reset.
