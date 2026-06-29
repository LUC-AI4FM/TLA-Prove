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

Verifier-backed metadata for ChatTLA TLA+ prover training and evaluation corpora.
This bundle now includes the full committed `FormaLLM` layer plus the public
AI4FM expansion lanes alongside the prover replay evidence.

## Files

- `metadata/tla_prover_artifacts_v1.json`: top-level manifest for the shipped prover
  corpora and public AI4FM artifacts.
- `metadata/tla_prover_corpus_preflight.json`: schema preflight across the
  checked-in prover corpora.
- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec
  layer (`205` rows).
- `metadata/ai4fm_public_tlaprove_corpora.json`: public AI4FM TLA-Prove corpus
  report (`2350` tracked training/eval rows within a `2757`-row committed public
  JSONL surface).
- `metadata/ai4fm_public_tlaprove_import_v1.summary.json`: normalized public AI4FM
  import layer (`1005` rows).
- `metadata/ai4fm_public_seed_file_manifest_v1.summary.json`: public GitHub seed
  file manifest (`3140` tracked files, `2110` `.tla` files, `2108` usable module rows).
- `metadata/ai4fm_public_seed_tla_modules_v1.summary.json`: usable public `.tla`
  module corpus (`2108` rows).
- `metadata/ai4fm_public_seed_license_surface.json`: repo-level SPDX/provenance
  rollup for the `11` committed public seed repos.
- `metadata/ai4fm_public_seed_prover_candidates_v1.summary.json`: SANY-clean public
  autoprover candidate subset (`98` rows).
- `metadata/ai4fm_public_discovery_manifest_v1.summary.json`: live public repo
  discovery manifest (`18` repo records).
- `metadata/ai4fm_public_dataset_surface.json`: rollup report across the committed
  public AI4FM dataset surface.
- `metadata/chattla_tla_prover_sft_v1.summary.json`: mixed prover SFT summary.
- `metadata/sany_tlc_pass_sft_v1.summary.json`: SANY/TLC-pass SFT summary.
- `metadata/prover_eval.summary.json`: TLAPS prover eval summary.
- `metadata/sany_tlc_pass_eval_v1.summary.json`: held-out SANY/TLC-pass eval
  summary.
- `metadata/tlaps_verified_autoprover_traces_v1.summary.json`: verified TLAPS proof
  trace summary.
- `metadata/sany_tlc_pass_eval_replay.json`: latest held-out replay result.
- `metadata/sany_tlc_pass_corpus_diagnostic.json`: corpus diagnostic report.

## Verification Snapshot

- Mixed prover SFT corpus: `1330` rows (`1053` Diamond SFT + `205` `FormaLLM`
  + `18 * 4` verified TLAPS rows).
- Verified TLAPS traces: `18` rows, raw `299/299` obligations proved.
- Prover eval: `18` rows, `299/299` gold TLAPS obligations.
- SANY/TLC SFT: `170` rows, no holdout overlap.
- SANY/TLC held-out replay: `30` checked, `30` TLC-gold, `29` Diamond.
- `FormaLLM`: `205` canonical prompt/spec rows across `71` families.
- Public AI4FM normalized import: `1005` rows from the tracked `2350`-row
  public corpora slice.
- Public seed repo license surface: `3` Apache-2.0 repos, `3` MIT repos, `2`
  NOASSERTION repos, and `3` unknown-license repos.
- Public AI4FM seed-module prover candidates: `98` rows out of `2108` usable
  public seed-module rows.

Use the metadata files as the source of truth for checksums and replay status.
