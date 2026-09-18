# Changelog

Notable changes to WhisperQ. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-09-18

### Added
- `scripts/normalize_audio.sh` — levels recordings whose speech volume swings
  too widely for the pipeline to handle, writing 16 kHz mono WAVs to
  `output/normalized/`. Chain is
  `highpass -> afftdn -> speechnorm -> loudnorm -> alimiter`, overridable via
  `WQ_FILTERS`.

  The industry recordings that prompted this measured -22 to -32 LUFS with a
  loudness range of 18.5-22.5 LU, against the ~7 LU typical of broadcast
  speech, and true peaks above 0 dBFS on all four. That is quiet speech next to
  full-scale transients, so a flat gain increase cannot help — it would only
  clip the peaks harder. `speechnorm` expands the quiet passages instead, and
  `loudnorm` lands every file on the same target so the pipeline stops behaving
  differently on each one. Measured result: all four converge to a mean of
  roughly -23 dB with peaks at -1.6 dB.

  `afftdn` runs before the expansion deliberately: raising quiet passages also
  raises background hiss, and amplified near-silence is a known trigger for
  Whisper emitting text over nothing.

## [1.1.0] — 2026-09-18

### Added
- Transcription language is now configurable via `WQ_LANG` (ISO 639-1), instead
  of being a hardcoded `en` in three separate scripts. The `WQ_` prefix is
  deliberate: `LANG` is the POSIX locale variable and is already set to
  something like `en_US.UTF-8` in every shell.
- `WQ_ALIGN_MODEL` names a HuggingFace wav2vec2 CTC model for forced alignment.
  WhisperX ships alignment defaults for roughly 40 languages while Whisper
  transcribes about 99, so languages outside the smaller set need this to
  produce word timestamps — and therefore to get speaker labels at all.
- `WQ_MODEL` overrides the Whisper model size without editing a script.
- `WQ_FONT` sets the hard-burn subtitle font. Helvetica carries no Indic
  glyphs, so a Tamil or Sinhala burn rendered as empty boxes.
- `load_env()` in `scripts/paths.py`, so `python scripts/mps_pipeline.py` picks
  up `.env` on its own. Previously only the shell entrypoints did, via
  `config.sh`.
- Tamil is verified working end to end with
  `WQ_ALIGN_MODEL=Harveenchadha/vakyansh-wav2vec2-tamil-tam-250`.

### Changed
- `mps_pipeline.py` no longer aborts when a language has no alignment model. It
  logs a warning and continues without alignment, yielding segment-level
  timestamps and no speaker labels. The old behaviour raised `ValueError` only
  after the ASR pass had finished, discarding hours of CPU work for a condition
  knowable at startup.
- The diarization model is not loaded at all when alignment is unavailable,
  since `assign_word_speakers` has no word timestamps to attach turns to.
- `burn_subs.sh` writes the subtitle track's language metadata from `WQ_LANG`
  via a new `lang_iso639_2()` helper, rather than always claiming `eng`.
  Unmapped languages get `und` rather than a confidently wrong label.

## [1.0.0] — 2026-08-08

First tagged version. The pipeline had been in working use for a month; this
release is the point it became a reusable project rather than a scratch
directory.

### Added
- `scripts/burn_subs.sh` — attaches `.clean.srt` to source video. Defaults to a
  `mov_text` soft-mux (seconds per file, no quality loss); `hard` mode
  re-encodes with subtitles in the pixels. This step previously existed only as
  an ad-hoc ffmpeg command in shell history.
- `scripts/config.sh` and `scripts/paths.py` — shared path resolution, venv
  activation, `.env` loading, and the ffmpeg@7 linker workaround.
- `is_done()` skip predicate with a `FORCE=1` override, in both languages.
- `input/` + `output/{transcripts,subbed}/` layout, both gitignored.
- `AGENTS.md`, `CLAUDE.md`, `docs/DECISIONS.md`, `docs/BUILD_PLAN.md`, `LICENSE`
  (MIT), `VERSION`, this changelog.

### Changed
- Scripts resolve paths from their own location instead of the caller's cwd, so
  they work from any directory.
- Input files are discovered by glob, largest-first, replacing the hardcoded
  filename list `parallel.sh` carried.
- `parallel.sh` takes a worker count argument instead of a fixed 2.
- `mps_pipeline.py` processes all of `input/` when given no arguments.
- `requirements.txt` cut from a 100-package `pip freeze` to three direct
  dependencies.

### Fixed
- Completion is now judged on the `.json` rather than the `.srt`. WhisperX
  writes the `.srt` incrementally, so a killed run left a truncated file that
  every later run skipped as complete — producing videos whose subtitles stop
  partway through with no error anywhere.
- Removed `mapfile` and bash 4 array indexing, which fail on the bash 3.2 that
  macOS ships. The scripts could not have run on a clean Mac.

### Security
- Git history reinitialised. The previous history carried roughly 1.3 GB of
  lecture video, including blobs above GitHub's 100 MB limit. Recordings are
  third-party copyright and diarized transcripts are identifiable personal
  speech; `.gitignore` now excludes them by directory and by extension.

[1.0.0]: https://github.com/Rumeasiyan/whisperq/releases/tag/v1.0.0
