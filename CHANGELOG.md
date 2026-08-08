# Changelog

Notable changes to WhisperQ. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
