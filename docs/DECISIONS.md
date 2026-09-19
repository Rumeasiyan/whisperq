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

---

## 2026-09-18 — Alignment failure degrades the run instead of aborting it

**Decision.** When `whisperx.load_align_model()` cannot supply a model for the
configured language, `mps_pipeline.py` logs a warning and continues without
alignment or diarization, rather than propagating the exception.

**Why.** WhisperX is two systems with two different language sets. Whisper ASR
covers roughly 99 languages; forced alignment needs a wav2vec2 CTC model per
language and ships defaults for roughly 40 (`whisperx/alignment.py`). Tamil and
Sinhala are in the first set and not the second, which is the case that forced
this decision.

The old failure mode was the expensive kind: `load_align_model` was called
after the model-loading phase but the `ValueError` surfaced mid-run, so a
multi-hour ASR pass was already spent before anything told the user the language
was unsupported. The condition is fully knowable at startup.

Degrading is not free — losing word timestamps means `assign_word_speakers` has
nothing to attach diarization turns to, so speaker labels disappear entirely.
That is a real quality loss, not a cosmetic one, which is why the warning is
repeated across three lines and names the variable that fixes it. Segment-level
timestamps still come out of the ASR pass, and `build_clean_srt.py` already
rebuilds cues at segment granularity, so subtitles remain usable.

**Consequences.** An unsupported language now produces quiet output rather than
a crash, so the warning is the only signal that speaker labels are missing. A
caller who wants the hard failure back can check for `SPEAKER_` in the output.
Setting `WQ_ALIGN_MODEL` to any HuggingFace wav2vec2 CTC model restores full
behaviour; for Tamil, `Harveenchadha/vakyansh-wav2vec2-tamil-tam-250` is
verified to load with a native-script vocabulary and a `<pad>` blank token,
which is what WhisperX's trellis decoder expects.

**Refs.** `scripts/mps_pipeline.py` — `load_alignment()`; issue #6.

---

## 2026-09-19 — Hosted ASR is a separate script, not a flag

**Decision.** `scripts/assemblyai_transcribe.py` is its own entrypoint. The
local pipeline gained no `--remote` flag and no environment switch that would
route it to a hosted backend.

**Why.** ASR is the only slow stage. Measured on this machine, `large-v3` runs
at 1.29x realtime, so the 15.3-hour module 03 batch is about 20 hours of
saturated CPU; MPS diarization is minutes for the same batch and alignment is
seconds. Hosted ASR collapses the 20 hours and costs a few dollars, so the
capability is worth having.

What it is not worth is being reachable by accident. This script uploads
recording audio to a third party. The recordings are third-party copyright and
contain identifiable student and lecturer speech, and an upload cannot be
undone — the provider may retain, cache or log the audio regardless of anything
this repo does afterwards. A flag on `mps_pipeline.py` would put that one
mistyped environment variable away from a default-local run, and the failure
would be silent and irreversible. A separate script has to be typed on purpose.

AssemblyAI was chosen over the cheaper Whisper APIs because Whisper does not
diarize at any provider. Groq would cost $0.61 against AssemblyAI's $3.52 for
this batch, but would return unlabelled text and require a hybrid path: hosted
ASR for word timestamps, local pyannote for turns, then the existing merge.
Speaker labels are the reason this project exists rather than a plain WhisperX
invocation, so the $3 buys away a whole code path rather than a convenience.

**Consequences.** Two transcription backends now produce `output/transcripts/`
content, and they will not agree exactly — different ASR models and different
diarizers segment differently, so re-running a file through the other backend
changes the transcript. `is_done` cannot tell which backend produced a `.json`.
Speaker ids are normalised from AssemblyAI's `A`/`B`/`C` to `SPEAKER_00` so
downstream code cannot tell them apart either; that is deliberate for
`build_clean_srt.py`, but it does mean the provenance of a transcript is not
recorded anywhere. If that matters later, the `.json` is the place to record it.

Consent is per batch. The repo owner opted in for module 03 specifically, and
that is not standing permission for future batches. Provider retention and
training-data policy has not been reviewed against the university's agreement;
that remains open, alongside #4.

**Refs.** `scripts/assemblyai_transcribe.py`; issue #10.

