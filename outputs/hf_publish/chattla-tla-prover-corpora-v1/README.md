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
This bundle ships prover corpora plus metadata summaries for the broader public AI4FM expansion lanes.

## Files

- `metadata/tla_prover_artifacts_v1.json`: top-level manifest for the shipped prover
  corpora and public AI4FM artifacts.
- `metadata/tla_prover_corpus_preflight.json`: schema preflight plus exact `205/205` `FormaLLM` row
  coverage verification across the `1330`-row default, `2433`-row expanded, and
  `2438`-row full-public prover train corpora.
- `metadata/ai4fm_org_surface.json`: live public GitHub org snapshot (`8` repos,
  `3` corpus-relevant).
- `metadata/formalllm_eval_v1.summary.json`: full `FormaLLM` canonical prompt/spec
  layer (`205` rows).
- `metadata/ai4fm_public_tlaprove_corpora.json`: public AI4FM TLA-Prove corpus
  report (`2350` tracked training/eval rows within a `2757`-row committed public
  JSONL surface).
- `metadata/ai4fm_public_tlaprove_import_all_public_raw_v1.summary.json`: raw
  full-public import summary (`2757` undeduped rows).
- `metadata/ai4fm_public_tlaprove_import_all_public_v1.summary.json`: normalized
  full-public import layer (`1010` rows).
- `metadata/ai4fm_public_tlaprove_import_raw_v1.summary.json`: raw tracked-corpora
  import summary (`2350` undeduped rows).
- `metadata/ai4fm_public_tlaprove_import_v1.summary.json`: normalized public AI4FM
  import layer (`1005` rows).
- `metadata/ai4fm_public_seed_file_manifest_v1.summary.json`: public GitHub seed
  file manifest (`3140` tracked files, `2110` `.tla` files, `2108` usable module rows).
- `metadata/ai4fm_public_seed_tla_modules_v1.summary.json`: usable public `.tla`
  module corpus (`2108` rows).
- `metadata/ai4fm_public_seed_license_surface.json`: repo-level SPDX/provenance
  rollup for the `11` committed public seed repos.
- `metadata/hf_publish_readiness.json`: canonical publish-readiness gate (`2`
  blockers; `20` latest benchmark rows still missing every core TLA component).
- `metadata/hf_publish_readiness.chattla_20b_fc128best.json`: fresh `fc128best`
  publish-readiness gate (`1` blocker; `20` rows still missing every core component,
  `8` with obvious placeholder text).
- `metadata/benchmark_repair_pairs_fc128best.summary.json`: benchmark-derived
  repair curriculum summary (`19` rows covering `19` of `20` failed fresh-benchmark
  cases; `1` missing gold target).
- `metadata/ai4fm_public_seed_prover_candidates_v1.summary.json`: SANY-clean public
  autoprover candidate subset (`98` rows).
- `metadata/ai4fm_public_discovery_manifest_v1.summary.json`: live public repo
  discovery manifest (`18` repo records).
- `metadata/ai4fm_public_dataset_surface.json`: rollup report across the committed
  public AI4FM dataset surface.
- `metadata/chattla_tla_prover_sft_v1.summary.json`: mixed prover SFT summary.
- `metadata/chattla_tla_prover_sft_public_expanded_v1.summary.json`: non-default
  public-AI4FM expanded prover SFT summary (`2433` rows total; `1005` normalized import rows + `98` seed prover-candidate replays on top of the baseline prover stack).
- `metadata/chattla_tla_prover_sft_public_all_v1.summary.json`: full-public
  expanded prover SFT summary (`2438` rows total; `1010` normalized full-public import rows on top of the baseline prover stack).
- `metadata/tla_prover_corpus_experiment_matrix.json`: bounded corpus-lane
  comparison matrix covering the `1330`-row baseline, `2433`-row expanded lane,
  `2438`-row full-public lane, and the `98`/`2108` public seed funnel.
- `metadata/sany_tlc_pass_sft_v1.summary.json`: SANY/TLC-pass SFT summary.
- `metadata/prover_eval.summary.json`: TLAPS prover eval summary.
- `metadata/sany_tlc_pass_eval_v1.summary.json`: held-out SANY/TLC-pass eval
  summary.
- `metadata/tlaps_verified_autoprover_traces_v1.summary.json`: verified TLAPS proof
  trace summary.
- `metadata/sany_tlc_pass_eval_replay.json`: latest held-out replay result.
- `metadata/sany_tlc_pass_corpus_diagnostic.json`: corpus diagnostic report.

The AI4FM import and seed-repo lanes are metadata-only audit surfaces in this bundle; they are not yet mixed into `data/train/chattla_tla_prover_sft_v1.jsonl`. The copied
`metadata/tla_prover_artifacts_v1.json` remains a source-repo snapshot, so its
`path` and `exists` fields describe the repo state used to assemble the bundle,
not bundle-local copies of every artifact named there.

## Verification Snapshot

- Mixed prover SFT corpus: `1330` rows (`1053` Diamond SFT + `205` `FormaLLM`
  + `18 * 4` verified TLAPS rows).
- Preflight coverage proof: exact `205/205` `FormaLLM` rows are present in the
  default (`1330` rows), expanded (`2433` rows), and full-public (`2438` rows)
  prover train corpora.
- Public-AI4FM expanded prover SFT: `2433` rows total (`1005` normalized public
  import rows + `98` seed prover-candidate replays on top of the baseline prover
  stack).
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
- Canonical publish readiness gate: blocked, with `20` of `20` latest benchmark rows
  missing every core TLA component.
- `fc128best` publish readiness gate: blocked, with `20` of `20` rows missing every core component
  and `8` obvious-placeholder failures.
- Benchmark-derived repair curriculum: `19` rows covering `19` of `20`
  failed fresh-benchmark cases, with `1` missing gold target.

Use the metadata files as the source of truth for checksums and replay status.
