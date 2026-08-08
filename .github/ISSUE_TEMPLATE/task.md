---
name: Task / bug / question
about: Anything that would otherwise be lost in a chat transcript
title: ''
labels: ''
assignees: Rumeasiyan
---

<!--
Write this for someone who has not seen the conversation it came from.
No "as discussed". If you delete the headings, keep the content.
-->

## What

<!-- The thing itself, in one or two sentences. -->

## Why it matters

<!-- The concrete consequence of ignoring this. Not "it would be nice" —
     what actually breaks, degrades, or gets missed. -->

## Where it surfaced

<!-- File paths and line numbers, or the doc section. -->

## Options (decisions only)

<!-- Delete if this isn't a decision. Otherwise: the realistic options, a
     recommendation, and the reasoning for it. -->

## Constraint check

<!-- Tick anything this touches. These are the rules in AGENTS.md that cause
     hard-to-diagnose failures when broken. -->

- [ ] Could cause recording or transcript content to leave the machine
      (**apply the `privacy-risk` label**)
- [ ] Touches the CPU-vs-MPS device split (ASR must stay on CPU — CTranslate2
      has no Metal backend and fails silently)
- [ ] Adds bash 4+ syntax (`mapfile`, `local -n`, negative array indices) —
      macOS ships bash 3.2
- [ ] Changes what counts as a completed transcription (`is_done`)
- [ ] Requires a `VERSION` and `CHANGELOG.md` update
