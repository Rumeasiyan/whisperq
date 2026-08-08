@AGENTS.md

## Claude-specific notes

- **Subagents do not inherit this file.** When delegating via the Agent tool,
  restate the constraints that bear on the task — especially the CPU-vs-MPS
  device split and the "never commit `input/` or `output/`" rule. A subagent
  told only "make transcription faster" will reach for `device="mps"` on the ASR
  model, which fails silently.
- **Never `git add -f` anything under `input/` or `output/`.** The gitignore is
  the only thing standing between this repo and publishing third-party lecture
  recordings plus identifiable speech.
- Filenames here contain spaces. Prefer the Read/Edit/Glob tools over shell
  globbing; when you must use Bash, quote every expansion — an unquoted
  `$(ls input/*.mp4)` word-splits on the spaces.
