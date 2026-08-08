# WhisperQ build plan

Current state: **v1.0.0, macOS / Apple Silicon only.**

This document is the roadmap. It is deliberately specific about *what blocks
what*, so the cross-platform work can be picked up without re-deriving the
analysis. Each phase is independently shippable; nothing here requires the
phases to be done in order except where a dependency is stated.

---

## What actually ties WhisperQ to macOS

Four bindings, only one of which is fundamental. This is the honest inventory —
the project is far closer to portable than its name suggests.

| Binding | Location | Fundamental? | Fix |
|---|---|---|---|
| `device="mps"` for diarization | `scripts/mps_pipeline.py` | **Yes** — Metal is Apple-only | Device detection: `cuda` → `mps` → `cpu` |
| `stat -f '%z %N'` | `scripts/config.sh` `list_media` | No — BSD `stat` | GNU `stat` uses `-c '%s %n'`; detect, or drop to `find -printf`/`perl -e 'print -s'` |
| `DYLD_FALLBACK_LIBRARY_PATH` | `scripts/config.sh` | No — macOS dynamic loader | Linux equivalent is `LD_LIBRARY_PATH` |
| `brew --prefix ffmpeg@7` | `scripts/config.sh` | No — Homebrew assumption | Probe `pkg-config libavcodec`, fall back to distro paths |

`transcribe.sh`, `parallel.sh`, and `build_clean_srt.py` are already
device-agnostic — they run WhisperX on CPU and touch none of the above except
through `config.sh`. In practice **three of the four bindings live in one
file**, and that file is under 90 lines.

---

## Phase 1 — Portability groundwork *(no new features)*

Goal: run unchanged on Linux/CPU. Unblocks everything after it.

- [ ] Extract a `detect_platform()` in `config.sh` setting `OS` and `ARCH`.
- [ ] Replace the BSD `stat` call in `list_media` with a portable size probe.
      Guard with a test that the sort order is still largest-first — the pool's
      load balancing silently degrades if this returns unsorted output rather
      than failing.
- [ ] Choose the loader variable by platform (`DYLD_FALLBACK_LIBRARY_PATH` on
      macOS, `LD_LIBRARY_PATH` on Linux).
- [ ] Locate the ffmpeg 4–7 libraries without assuming Homebrew.
- [ ] Mirror all of the above in `paths.py`, or — better — have the Python
      scripts shell out to `config.sh` for path resolution so the logic exists
      once. **The duplicated `is_done` between `config.sh` and `paths.py` is
      already a drift risk**; do not add a third copy.

**Done when**: the CPU scripts run on a Linux box with no source edits.

## Phase 2 — Device abstraction

Depends on Phase 1.

- [ ] Replace the hardcoded `device="mps"` with a resolver:
      `cuda` if available → `mps` if available → `cpu`.
- [ ] Keep ASR pinned to CPU regardless of what the resolver returns.
      **This is not a limitation to fix later** — CTranslate2 has no Metal
      backend, and moving ASR to the detected device would silently produce
      wrong output on Mac. It has genuine CUDA support, so on NVIDIA hardware
      ASR *can* move to GPU, but that must be an explicit CUDA-only branch, not
      a consequence of the resolver.
- [ ] Rename `mps_pipeline.py` → `pipeline.py` and `mps_diarize_test.py` →
      `bench_diarize.py`. **Breaking change — `MAJOR` bump.**
- [ ] Extend `bench_diarize.py` to accept `cuda`.

**Done when**: one entrypoint picks the right device on Mac, NVIDIA Linux, and
CPU-only machines.

## Phase 3 — Correctness and trust

Currently there is **no test suite, linter, or CI**. At v1.0.0 with a public
repo, that is the largest gap.

- [ ] Tests for the pure logic — `build_clean_srt.py`'s timestamp formatting,
      overlap repair, and speaker-label suppression are all pure functions over
      small inputs and need no media fixtures.
- [ ] A test for `is_done` covering the partial-`.srt` case it exists to
      prevent, and `FORCE=1`.
- [ ] `shellcheck` over `scripts/*.sh`. Expect findings around the `eval` in
      `read_media_into`.
- [ ] GitHub Actions: shellcheck + `py_compile` + the unit tests on Linux.
      Cannot cover the MPS path — no Apple Silicon runners on the free tier.
- [ ] A tiny (~10s) audio fixture, licence-clear, for an end-to-end smoke test.
      **Must not be a lecture recording.**

## Phase 4 — Usability

- [ ] Single `whisperq` entrypoint with subcommands (`transcribe`, `clean`,
      `sub`, `bench`) replacing the current five scripts. **`MAJOR` bump.**
- [ ] Move `MODEL`, `LANG`, `COMPUTE`, `THREADS`, worker count out of script
      constants into `.env` or a config file. They are currently edited in
      place, which shows up as spurious diffs.
- [ ] Progress and time-remaining estimate for long batches.
- [ ] Non-English support. `LANG="en"` is hardcoded in three places and the
      alignment model is language-specific.

## Phase 5 — Dubbing

The name once promised this; nothing implements it. Scoped last because it is a
different problem from transcription, not an extension of it.

- [ ] Translate `.clean.srt` preserving cue timings.
- [ ] TTS per speaker, using the diarization labels the pipeline already
      produces — this is the part WhisperQ is unusually well positioned for.
- [ ] Time-stretch synthesised audio to fit the original cue windows.
- [ ] Mux as an alternate audio track rather than replacing the original.

**Open question before starting**: synthesised voices of identifiable real
lecturers is a consent question, not just a technical one. Resolve before
building, and record the outcome in `docs/DECISIONS.md`.

---

## Explicitly not planned

- **A hosted or web version.** Recordings are copyrighted and transcripts are
  personal data; uploading them anywhere is the exact risk `.gitignore` exists
  to prevent.
- **Bundling model weights.** Licence-gated, and users must accept the pyannote
  terms on their own HF account.
- **Windows native.** WSL2 is the intended path — it gets Phase 1's Linux work
  for free. Native Windows would need a third branch in every path helper for
  little benefit.
