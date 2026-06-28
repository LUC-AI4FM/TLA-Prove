---
license: mit
language:
- en
task_categories:
- text-generation
tags:
- tla-plus
- formal-methods
- tlaps
- tlc
- sany
- theorem-proving
- chattla
pretty_name: ChatTLA TLA+ Prover Corpora v1
---

# ChatTLA TLA+ Prover Corpora v1

Verifier-backed training and evaluation corpora for ChatTLA TLA+ prover work.

## Files

- `data/train/chattla_tla_prover_sft_v1.jsonl`: 1125 SFT rows combining existing Diamond SFT data with oversampled verified TLAPS proof rows.
- `data/train/sany_tlc_pass_sft_v1.jsonl`: 170 SANY/TLC-pass rows with deterministic inline TLC config and inferred constants.
- `data/eval/prover_eval.jsonl`: 18 TLAPS-callback-compatible eval rows derived from verified proof traces.
- `data/eval/sany_tlc_pass_eval_v1.jsonl`: 30 held-out SANY/TLC-pass eval rows.
- `data/traces/tlaps_verified_autoprover_traces_v1.jsonl`: 18 verified TLAPS proof traces.
- `metadata/`: summary, preflight, replay, and manifest evidence.

## Verification Snapshot

- Verified TLAPS traces: 18 rows, raw 299/299 obligations proved.
- Prover eval: 18 rows, 299/299 gold TLAPS obligations.
- SANY/TLC SFT: 170 rows, no holdout overlap.
- SANY/TLC held-out replay: 30 checked, 30 TLC-gold, 29 Diamond.

Use the metadata files as the source of truth for checksums and replay status.
