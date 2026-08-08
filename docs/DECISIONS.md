# Decision log

Append-only, newest first.

**The bar for an entry**: something a competent person would later look at and
ask "why is it like this?" — architecture, dependency choices, resolved open
questions, reversals. Not routine implementation choices.

**The *why* should be longer than the *what*.** The what is visible in the code;
the why is not, and it is the reason this file exists. Record what was rejected
and the trade-off accepted, so a future reader can tell whether the reasoning
still holds.

Format: `## YYYY-MM-DD — Title`, then **Decision**, **Why**, **Consequences**, **Refs**.

---

## 2026-08-08 — Judge transcription completion on `.json`, not `.srt`

**Decision.** `is_done()` treats a file as transcribed when a non-empty
`<base>.json` exists in `output/transcripts/`. Implemented twice, in
`scripts/config.sh` and `scripts/paths.py`, which must be kept in step.

**Why.** The two earlier scripts disagreed: `transcribe.sh` checked for `.txt`,
`parallel.sh` checked for a non-empty `.srt`. Both are wrong in the same way.
WhisperX streams the `.srt` to disk as it goes, so a run killed partway through
a two-hour lecture leaves a syntactically valid, non-empty, *truncated* `.srt`.
Every later run then skips that file, and the truncation is only discovered when
someone watches the video and the subtitles stop halfway. The `.json` is written
once, at the end, after diarization has been merged — its presence is the only
artifact that actually proves the pipeline completed.

Rejected: checksum or duration-matching the transcript against the source audio.
More correct, but requires decoding the media just to answer "is this done?",
which is slow on a directory of multi-gigabyte videos.

Accepted trade-off: a run killed *during* JSON writing could leave a corrupt
`.json` that is non-empty and therefore treated as done. Judged rare enough to
handle with `FORCE=1` rather than by parsing the JSON on every check.

**Consequences.** `FORCE=1` added as the escape hatch across all scripts.
Anything that changes WhisperX's output-writing order breaks this assumption.

**Refs.** `scripts/config.sh` `is_done`, `scripts/paths.py` `is_done`.

---

## 2026-08-08 — Discard git history rather than rewrite it

**Decision.** Re-initialised the repository. The previous 10 commits were
deleted along with their objects.

**Why.** Eight lecture videos had been committed before `.gitignore` covered
them, leaving a 1.3 GB `.git` with individual blobs over 100 MB — above GitHub's
hard per-blob limit, so the repo could never have been pushed as it stood.

`git rm --cached` alone was insufficient: it removes files from `HEAD` but the
blobs remain reachable in history, so the push still fails. `git filter-repo`
would have preserved the commit messages, but the repository had no remote and
nothing had ever been pushed, so there was no history anyone else depended on —
and the ten messages documented a throwaway exploration phase, not decisions
worth keeping. The cost of rewriting exceeded the value of what would be saved.

**Consequences.** `.git` went from 1.3 GB to under 200 KB. All prior commit
SHAs are gone. `.gitignore` now blocks media two ways — by directory
(`input/*`, `output/**`) and by extension tree-wide — because the directory rule
alone would not have caught the `.m4a` that was sitting in the repo root.

**Refs.** `.gitignore`.

---

## 2026-08-08 — Soft-mux subtitles by default instead of burning them in

**Decision.** `scripts/burn_subs.sh` defaults to `soft`: add a `mov_text`
subtitle track and stream-copy the video and audio. Hard burn-in is available as
`./scripts/burn_subs.sh hard`.

**Why.** This reconstructs what had actually been done by hand — `ffprobe` on
the existing `output/subbed/` files shows a `mov_text` stream added alongside
untouched h264/aac, and the files are ~1.3% larger than their sources, which
rules out a re-encode. Soft-muxing takes seconds per file against hours, loses
no quality, and lets the viewer switch subtitles off. For reviewing one's own
lectures that is the right default.

Hard burn survives any player or upload but costs a full re-encode and a
generation of quality loss, so it is opt-in for when a file is being shared
somewhere that ignores subtitle tracks.

**Consequences.** `mov_text` is not shown by every player (VLC and QuickTime
are fine). Users who see no subtitles need the `hard` mode, which the script's
header comment says.

**Refs.** `scripts/burn_subs.sh`.

---

## 2026-07-11 — Split the pipeline: ASR on CPU, diarization on MPS

**Decision.** `scripts/mps_pipeline.py` runs Whisper ASR and alignment on CPU
with `int8`, and only pyannote speaker diarization on MPS.

**Why.** The obvious optimisation on Apple Silicon — move everything to the GPU
— cannot work. WhisperX's ASR runs on CTranslate2, which has no Metal backend
at all. Passing `device="mps"` there does not raise; it degrades silently, which
is worse than failing. Diarization is plain PyTorch and does move to MPS, where
it measured roughly 8× faster than CPU on this hardware.

So the split is not a tuning choice, it is the only arrangement that works.
`mps_diarize_test.py` exists to re-measure the diarization half if the hardware
or torch version changes.

**Consequences.** `PYTORCH_ENABLE_MPS_FALLBACK=1` is set before importing torch,
so pyannote ops without a Metal kernel drop to CPU instead of raising. Models
are loaded once and reused across files, and audio is freed after each file to
keep memory flat over a long batch. This is also the single largest obstacle to
running WhisperQ on Linux or Windows — see `docs/BUILD_PLAN.md`.

**Refs.** `scripts/mps_pipeline.py`, `scripts/mps_diarize_test.py`.

---

## 2026-07-11 — Point the dynamic loader at ffmpeg@7

**Decision.** `scripts/config.sh` prepends the Homebrew `ffmpeg@7` lib directory
to `DYLD_FALLBACK_LIBRARY_PATH`, and warns if that formula is missing.

**Why.** pyannote 4.x pulls in torchcodec, which links against ffmpeg 4–7
shared libraries. Homebrew's default `ffmpeg` is now v8. The mismatch fails
inside a native library, so the Python traceback points nowhere useful and the
error text does not mention ffmpeg versions at all. This cost significant
debugging time and is the single least discoverable requirement in the project.

Rejected: downgrading the system ffmpeg to v7. That breaks other tooling on the
machine for the sake of one project. Scoping the override to this project's
scripts leaves the rest of the system alone.

**Consequences.** Anyone running WhisperQ must `brew install ffmpeg@7` even
though they likely already have ffmpeg. The warning in `config.sh` is what makes
this diagnosable. `DYLD_FALLBACK_LIBRARY_PATH` is macOS-specific; the Linux
equivalent is `LD_LIBRARY_PATH`.

**Refs.** `scripts/config.sh`.

---

## 2026-07-11 — Build a readable segment-level `.srt` as a separate step

**Decision.** `scripts/build_clean_srt.py` post-processes WhisperX's `.json`
into `<base>.clean.srt`, rather than using the `.srt` WhisperX emits.

**Why.** With word-level alignment enabled, WhisperX's `.srt` is one cue per
*word* — unreadable on screen. Regenerating from the `.json` gives segment-level
cues, and lets speaker labels be printed only when the speaker actually changes,
which keeps multi-speaker crosstalk legible instead of prefixing every line.

Keeping it a separate script rather than a WhisperX flag means the presentation
can be re-tuned without re-running hours of transcription.

**Consequences.** The step reads the `.json`, so it depends on the same artifact
`is_done` keys on. It also repairs overlapping and zero-length cues, which occur
in the raw output and which some players reject outright.

**Refs.** `scripts/build_clean_srt.py`.

---

## 2026-07-10 — Two-worker pool with `mkdir` locks for parallel transcription

**Decision.** `scripts/parallel.sh` runs N workers (default 2) that each claim
files by creating a lock directory under `output/transcripts/.locks/`.

**Why.** Transcription is long-running and single-threaded per file, so several
files can usefully run at once. Coordination needs to guarantee no file is
processed twice. `mkdir` either succeeds or fails atomically on POSIX
filesystems, with no separate check-then-act window — a lock file created with
`test -f` then `touch` has exactly that race. It needs no dependencies beyond
the shell.

Workers process files largest-first (`list_media` sorts by size descending)
because a large file claimed last leaves one lane grinding alone while the
others sit idle. Longest-processing-time-first is the standard greedy fix.

**Consequences.** Locks persist after a crash, so an interrupted run must have
`output/transcripts/.locks/` cleared before those files are retried. The default
of 2 workers reflects memory, not cores: each worker holds its own model and
decoded audio.

**Refs.** `scripts/parallel.sh`.
