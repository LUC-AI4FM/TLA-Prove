# GRPO Action-Lane Summary

## Scope

This note keeps the public summary of the action-lane GRPO experiments without
including machine-specific runbook details.

## Main Outcome

The GRPO action lane established that ChatTLA can run end-to-end repair and
training experiments over benchmark-style syntax and structure failures, but it
did not by itself produce release-ready benchmark behavior.

## Durable Lessons

- Training on repair-style signal is useful when benchmark failures are mostly
  mechanical or structural.
- Deterministic syntax repair remains important even when a trained adapter is
  available.
- Infrastructure success is not the same thing as benchmark success; release
  claims still need checked benchmark evidence.

## Public Interpretation

This lane is best treated as a research and repair mechanism, not as proof that
the public model is ready for another release.

The authoritative public readiness decision continues to live in the checked-in
publish manifests:

- `outputs/manifests/hf_publish_readiness.json`
- `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json`

## Next Use

Use the action lane when:

- a benchmark failure pattern repeats often enough to justify targeted repair
  data; and
- the resulting changes can be measured against the checked benchmark surface.

Avoid treating action-lane progress as sufficient unless it changes the
benchmark evidence directly.
