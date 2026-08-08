# AGENTS.md — WhisperQ

Working guide for AI agents and new contributors. Everything here is specific to
this repository; if a rule is not stated, use ordinary judgement.

## What this project is

WhisperQ turns a folder of long recordings (originally university lectures) into
speaker-labelled transcripts and subtitled video.

It is an orchestration layer, not an ASR engine. The transcription and
diarization come from [WhisperX](https://github.com/m-bain/whisperX) and
pyannote. WhisperQ contributes four things those don't provide, and they are
what the code is mostly made of:

1. **The device split** — ASR on CPU, diarization on MPS. Not a tuning choice;
   the only arrangement that works (see Constraints).
2. **The ffmpeg@7 linker workaround** — otherwise diarization dies in a native
   library with no usable traceback.
3. **Batch behaviour** — resumable skip logic, atomic locks for parallel
   workers, largest-first ordering.
4. **Readable subtitles** — WhisperX emits one cue per *word*; WhisperQ rebuilds
   segment-level cues and repairs overlaps.

When editing, keep that boundary in mind: bugs in transcription quality are
usually upstream (label them `upstream`), bugs in resumption, ordering, paths,
or subtitle presentation are ours.

**Currently macOS/Apple Silicon only.** See `docs/BUILD_PLAN.md` for the
cross-platform roadmap and exactly which lines block Linux and Windows.

## Where to look

| Path | When you need it |
|---|---|
| `scripts/config.sh` | Shell entrypoint setup: paths, venv, `.env`, ffmpeg@7 linker fix, `list_media`, `is_done` |
| `scripts/paths.py` | Same for Python. `is_done` here must mirror `config.sh` |
| `scripts/transcribe.sh` | Sequential CPU transcription, one file at a time |
| `scripts/parallel.sh` | N-worker pool, atomic `mkdir` locks |
| `scripts/mps_pipeline.py` | The fast path: CPU ASR + MPS diarization |
| `scripts/build_clean_srt.py` | Converts raw word-level `.srt` into readable segment-level `.clean.srt` |
| `scripts/burn_subs.sh` | Attaches `.clean.srt` to video (soft-mux or hard burn) |
| `docs/DECISIONS.md` | Why the architecture is the way it is |
| `docs/BUILD_PLAN.md` | Roadmap, including cross-platform support |
| `input/`, `output/` | Media. Gitignored. Never commit contents |

## Constraints

Each of these is enforced somewhere in the code and will cause a hard-to-diagnose
failure if violated.

| Rule | Why | Enforced at |
|---|---|---|
| **Never commit anything under `input/` or `output/`** | Recordings are third-party copyright, and diarized transcripts are identifiable personal speech. Publishing them is a privacy breach, not just repo bloat. A prior history reached 1.3 GB and had to be discarded. | `.gitignore` (directory globs *and* extension globs) |
| **ASR must run on CPU, never MPS** | CTranslate2 (WhisperX's ASR backend) has no Metal backend. Passing `device="mps"` to `load_model` does not error — it silently falls back or produces garbage. Only pyannote diarization benefits from MPS. | `scripts/mps_pipeline.py` — `device="cpu"` on `load_model` and `align` |
| **`DYLD_FALLBACK_LIBRARY_PATH` must point at ffmpeg@7 libs** | torchcodec (pulled in by pyannote 4.x) links against ffmpeg 4–7. Homebrew's default `ffmpeg` is v8. Without this, diarization dies inside a native library with no usable Python traceback. | `scripts/config.sh` |
| **Target bash 3.2** | macOS ships bash 3.2 (2007) as `/bin/bash`. `mapfile`, `readarray`, `local -n`, and negative array indices are all bash 4+ and fail on a clean Mac. | `scripts/config.sh` — `read_media_into` exists solely for this |
| **`is_done` keys on `.json`, not `.srt`** | WhisperX writes the `.srt` incrementally. A killed run leaves a partial `.srt` that looks complete, so the file is skipped forever and silently ends up truncated. The `.json` is written once, after diarization. | `scripts/config.sh` and `scripts/paths.py` |
| **`HF_TOKEN` comes from `.env`, never a literal** | `.env` is gitignored; a hardcoded token would be published. pyannote also requires the model licences accepted on the same HF account or it 401s. | `scripts/config.sh` exits if unset |

## Commands

All verified working on this machine.

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg@7
cp .env.example .env          # paste HF token

# transcribe (pick one)
./scripts/transcribe.sh       # sequential, CPU
./scripts/parallel.sh 2       # 2-worker pool, CPU
python scripts/mps_pipeline.py  # CPU ASR + MPS diarization (fastest)

# post-process
python scripts/build_clean_srt.py   # -> output/transcripts/*.clean.srt
./scripts/burn_subs.sh soft         # -> output/subbed/*.subbed.mp4 (seconds)
./scripts/burn_subs.sh hard         # re-encode, subtitles in pixels (hours)

# reprocess everything, ignoring completed work
FORCE=1 ./scripts/transcribe.sh

# checks (no test suite exists yet — see docs/BUILD_PLAN.md)
bash -n scripts/*.sh          # shell syntax
python3 -m py_compile scripts/*.py
```

There is **no test suite, linter, or CI** in this repository. Do not document
commands for them until they exist.

## Conventions

- **Shell**: `set -uo pipefail` (`transcribe.sh` adds `-e`; the pool scripts
  deliberately omit it so one failed file does not kill the run). Every script
  sources `config.sh` and uses its absolute `$INDIR`/`$OUTDIR`/`$SUBDIR` rather
  than relative paths — scripts must work from any cwd.
- **Python**: stdlib-style comma imports, module-level `UPPERCASE` config
  constants, `log()` with an `HH:MM:SS` stamp for progress. No type hints
  currently used.
- **Comments** explain *why*, not *what*. The existing comments are the model:
  they document non-obvious constraints (linker paths, backend limitations),
  not the mechanics of the line below.
- **Commits**: imperative subject under ~50 chars, blank line, body explaining
  the reasoning. Conventional Commits prefixes are *not* used.
- **Filenames** in `input/` routinely contain spaces. Quote every expansion.

## Versioning

| | |
|---|---|
| Canonical source | `VERSION` at repo root |
| Current version | `1.0.0` |
| Build number | Not used — no packaged distributable |
| Scheme | Semantic versioning `MAJOR.MINOR.PATCH` |
| Cadence | **Bump in the same commit as every completed user-visible change** |

Which part changes:

| Change | Bump |
|---|---|
| Breaking: script removed/renamed, flag or output path changed incompatibly | `MAJOR` (reset minor+patch) |
| New capability, backward compatible (new script, new mode, new flag) | `MINOR` (reset patch) |
| Bug fix, hotfix, non-breaking security fix | `PATCH` |
| Docs, comments, refactor, formatting, internal maintenance | **No bump** |

Use the highest applicable bump when a change spans categories. Never add a
fourth component (`1.4.2.1`); a hotfix is a patch release.

Update `CHANGELOG.md` in the same commit. Do not create a git tag, publish a
release, or push a build unless explicitly asked.

## Workflow

1. Check for an existing open issue. If none, open one (see below) and assign it
   to `Rumeasiyan`.
2. Branch from `main`: `git checkout -b <short-slug>`. Work does not land
   directly on `main`.
3. Make the change. Verify with `bash -n scripts/*.sh` and
   `python3 -m py_compile scripts/*.py`; run the affected script on one real file
   where practical.
4. Decide the version bump from the table above. If it is not "no bump", update
   `VERSION` and `CHANGELOG.md` in the same commit.
5. If the change answers a "why is it like this?" question, add an entry to
   `docs/DECISIONS.md`.
6. Commit referencing the issue (`Refs #12`), push, open a PR.
7. Comment on the issue with what was built, what was verified, the resulting
   version, and anything deferred — with a link to the follow-up issue.

## Issues

**An item raised only in conversation is lost.** The moment you find an open
question, a deferred fix, a bug, or a risky assumption, open an issue — then,
not in a closing summary.

**Issues must be self-contained.** The reader has not seen the conversation.
No "as discussed". State:

- what it is
- why it matters — the concrete consequence of ignoring it
- where it surfaced — file paths, line numbers
- for decisions: the realistic options, with a recommendation and its reasoning

**Too small for an issue**: typos, comment rewording, formatting, renaming a
local variable. Filing those buries the real items.

Labels in use: `bug`, `enhancement`, `cross-platform`, `performance`,
`privacy-risk`, `docs`, `question`, `upstream`.

`privacy-risk` is the one to watch — apply it to anything that could cause
recording or transcript content to leave the machine.
