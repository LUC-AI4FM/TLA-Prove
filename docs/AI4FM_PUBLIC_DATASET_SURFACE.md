# AI4FM Public Dataset Surface

This note captures the current public dataset surface that ChatTLA can use
without private infrastructure.

## Current public sources

- `LUC-AI4FM` org surface:
  <https://github.com/LUC-AI4FM>
- `FormaLLM`: <https://github.com/LUC-AI4FM/FormaLLM>
- `TLA-Prove`: <https://github.com/LUC-AI4FM/TLA-Prove>
- `tla-dataset-pipeline`: <https://github.com/LUC-AI4FM/tla-dataset-pipeline>
- `tla-dataset-pipeline` DVC metadata:
  <https://raw.githubusercontent.com/LUC-AI4FM/tla-dataset-pipeline/main/dvc.lock>
- checked-in org manifest:
  `outputs/manifests/ai4fm_org_surface.json`

## Verified current counts

These values come from the checked-in inspection report at
`outputs/manifests/ai4fm_public_dataset_surface.json`.
Treat them as the reproducible local snapshot; the live upstream heads
re-verified below are the current public-source reference.
That report now also carries a machine-readable `public_1800_plus_interpretation`
section plus `broader_public_lanes` counts, so the larger GitHub-surface
interpretation is encoded in the manifest and not only in this note.
The broader public FormaLLM file surface is also materialized directly in
`data/processed/formalllm_public_module_manifest_v1.jsonl` with a summary beside
it. A prover-facing join against the latest full-dataset smoke now lives at
`data/processed/formalllm_public_prover_surface_v1.jsonl`.

- `FormaLLM`
  - git head: `e74c2ed`
  - `205` canonical metadata entries
  - `71` families
  - `191` unique model names
  - `410` `.tla` files under `data/*/tla/*.tla`
  - `205` `_clean.tla` files, matching the canonical benchmark row count
  - `205` non-clean `.tla` variants in that same canonical module tree
  - `503` total `.tla` files across the public repo tree, including `93`
    auxiliary `.tla` files outside `data/*/tla/*.tla`
  - `136` `.cfg` files under `data/*/cfg/*.cfg`
  - `163` total `.cfg` files across the public repo tree, including `27`
    auxiliary `.cfg` files outside `data/*/cfg/*.cfg`
  - `187` cleaned comment prompt files
- `tla-dataset-pipeline`
  - git head: `59bd533`
  - DVC `pull` surface: `data/raw`, `2628` files
  - DVC `parse` input snapshot: `data/raw`, `227` files
  - DVC `parse` output surface: `data/parsed`, `3979` files

## 2026-06-29 upstream verification

We also re-checked the current upstream public repos directly on 2026-06-29:

- `LUC-AI4FM` org surface
  - the public org currently exposes `8` repos
  - `3` are corpus-relevant for ChatTLA today:
    `FormaLLM`, `TLA-Prove`, and `tla-dataset-pipeline`
  - the remaining `5` public repos (`FormaLLM-Reverse`, `paper-parse`,
    `webpage`, `ralph-tla`, `.github`) are useful context/provenance surfaces,
    but not primary TLA training lanes
- `FormaLLM`
  - current `main`: `b159f5df093e7ed71f4793bba99459b97a2bb23d`
  - `data/all_models.json` still contains exactly `205` canonical records
  - committed split files are currently `Input/train.json`, `Input/val.json`, and
    `Input/test.json`, and they still sum to `205`: `143` train, `30` val,
    `32` test
  - the canonical `data/*/tla/*.tla` module tree is `410` files:
    `205` `_clean.tla` modules that line up with the canonical benchmark layer,
    plus `205` paired non-clean variants
  - the full public repo tree is larger: `503` total `.tla` files and `163`
    total `.cfg` files, which includes `93` auxiliary `.tla` files and `27`
    auxiliary `.cfg` files outside the canonical `data/*/{tla,cfg}` trees
- `tla-dataset-pipeline`
  - current `main`: `4ac5620f7ef425285ca5a8d91304c9b4da5ca56f`
  - seed recipe currently lists `11` repos, `7` org seeds, `9` user seeds, and `5` search queries
  - `dvc.lock` still reports `2628` `pull` files, `227` `parse` input files, and `3979` `parse` output files
- `ai4fm.cs.luc.edu` live public pages
  - the current public site still describes the evaluation benchmark as `205`
    TLA+ specifications on the research landing page and paper pages
  - the visible public site narrative is aligned with the `205`-entry
    benchmark layer, not with the stale `1800+` architecture-doc note
- stale `1800+` note worth not over-trusting
  - `FormaLLM/doc/ARCHITECTURE.md` still says `all_models.json` is metadata for
    `1800+ specifications`
  - that line no longer matches the current committed public metadata file,
    which now contains `205` records

See also [AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md](AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md)
for the compact live re-verification note and exact commands used.

Important interpretation:

- the local `205`-row `formalllm_eval_v1` lane matches upstream exactly
- the broader public `FormaLLM` repo surface is larger than the canonical
  benchmark layer: `503` `.tla` files are visible publicly, but only the `205`
  `_clean.tla` files align one-for-one with the canonical benchmark rows; the
  canonical `data/*/tla/*.tla` tree itself is `410` files once those clean
  modules are paired with their non-clean variants
- the current full-dataset prover smoke does **not** yet justify mixing that
  broader canonical tree into prover training:
  - `410` canonical `.tla` rows were scanned
  - `403` were skipped
  - `7` were TLC-repair candidates
  - `0` reached TLAPS-partial or inductiveness evidence in that lane
- the local `1005` normalized `ai4fm_public_tlaprove_import_v1` rows and `98`
  `ai4fm_public_seed_prover_candidates_v1` rows are ChatTLA-derived downstream
  corpora, not counts published by the two upstream repos above
- the older `1800+` language appears to describe an earlier or broader internal
  surface, not the current committed public benchmark layer
- if someone cites `1800+` for the current public AI4FM GitHub surface, the closest reproducible interpretations today are the broader expansion lanes: `2757` committed `TLA-Prove` JSONL rows, `2110` public seed `.tla` files, or `2108` usable seed modules, not the canonical `205`-entry `FormaLLM` benchmark
- our local public-seed lane is now reconciled:
  - `ai4fm_public_seed_file_manifest_v1.summary.json` reports `2110` public
    seed `.tla` files
  - `ai4fm_public_seed_tla_modules_v1.summary.json` reports `2108` usable
    module rows
  - the exact `2`-row gap is explained by `.tla` files that do not expose a
    module header accepted by the corpus builder:
    - `apalache-mc/apalache:test/tla/y2k_09_OutTransition.tla`
    - `tlaplus/Examples:specifications/transaction_commit/2PCwithBTM.tla`
  - `ai4fm_public_seed_prover_candidates_v1.summary.json` now reads those
    `2108` module rows cleanly, with the stale `missing_module_content` bucket
    eliminated
- the remaining public seed repair queue is now materialized directly as
  `data/processed/ai4fm_public_seed_prover_repair_queue_v1.jsonl`:
  - `24` remaining shape-ready-but-not-SANY rows total
  - `9` are recoverable without new source material after transitive helper
    staging is taken into account
  - action split: `5` TLAPS-stub-only, `4` same-repo helper staging,
    `15` blocked on missing public dependencies
- measured replay against the current public candidate builder is stricter than
  that first-pass queue:
  - `data/processed/ai4fm_public_seed_prover_recovery_probe_v1.jsonl` currently
    shows `0/24` rows recovered by the existing builder
  - `15` remain blocked on unresolved imports even after current staging
  - `9` move past import staging but still fail with non-import SANY errors
- repo-level license provenance across the `11` committed public seed repos is
  mixed:
  - `3` Apache-2.0 repos covering `525` tracked `.tla` files
  - `3` MIT repos covering `1116` tracked `.tla` files
  - `2` NOASSERTION repos covering `410` tracked `.tla` files
  - `3` unknown-license repos covering `59` tracked `.tla` files
  - see `outputs/manifests/ai4fm_public_seed_license_surface.json` for the
    exact per-repo rollup and caution buckets

## Public TLA-Prove corpora

ChatTLA now also tracks the stable public corpora already committed in
`LUC-AI4FM/TLA-Prove`:

- report artifact: `outputs/manifests/ai4fm_public_tlaprove_corpora.json`
- repo head at inspection time: `d1b5142422cfab2ce9a2eba9522d6221776378d6`
- public JSONL rows across the tracked training/eval corpora: `2350`
- full committed public JSONL surface: `2757` rows across `19` files
- additional committed public JSONL rows outside the tracked corpora: `407`
  rows across `13` files (`7` rows under `data/toy/*` and `400` rows under
  `outputs/diamond_gen/*`)
- largest single corpus: `data/processed/diamond_sft_v3.jsonl` with `1053` rows
- base processed train corpus: `data/processed/train.jsonl` with `713` rows
- Ralph-generated expansion: `500` train rows and `50` dev rows
- prompt/topic expansion metadata: `200` topics across `10` batches
- public benchmark surface: `20` benchmark items and `13` non-null benchmark
  module mappings; the upstream `README.md` still mentions a `30-spec`
  held-out suite, so treat the explicit `diamond_eval_holdout.jsonl` file as
  the `30`-row eval holdout and `benchmark_suite.json` as the current
  `20`-item benchmark surface

The tracked `2350`-row slice is the stable public training/eval stack ChatTLA
ingests today without DVC or private infrastructure. The broader `2757`-row
committed surface is still valuable as an audit target, but it currently
includes toy and diamond-generation outputs that are not part of the tracked
import lane.

ChatTLA now materializes that public corpus stack as:

- `data/processed/ai4fm_public_tlaprove_import_v1.jsonl`
- `data/processed/ai4fm_public_tlaprove_import_v1.summary.json`

Current live import summary:

- `2350` raw public rows across the tracked corpora
- `1005` kept ChatTLA-format rows after normalization and exact final-spec dedupe
- `1345` duplicate rows collapsed
- kept rows by corpus:
  - `285` from `data/processed/train.jsonl`
  - `170` from `data/processed/diamond_sft_v3.jsonl`
  - `30` from `data/processed/diamond_eval_holdout.jsonl`
  - `471` from `data/frs_tla_ralph_gen/train.jsonl`
  - `48` from `data/frs_tla_ralph_gen/dev.jsonl`
  - `1` from `data/processed/eval.jsonl`

If we want the full raw tracked-corpora row surface instead of the normalized,
deduped import, ChatTLA can now materialize that tracked public stack directly:

- command:
  `python3 scripts/build_ai4fm_public_tlaprove_import.py --keep-duplicates --out data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl`
- expected scale from the current tracked corpora surface:
  - `2350` raw public rows from the tracked `LUC-AI4FM/TLA-Prove` corpora
  - plus the separate `205`-row `FormaLLM` canonical corpus
- current tracked raw-import artifact:
  - `2350` kept rows in `ai4fm_public_tlaprove_import_raw_v1` when exact-final-spec dedupe is disabled

If we want the full committed public `TLA-Prove` JSONL surface instead of just
the tracked six-corpus slice, the importer now also has an opt-in expansion
path:

- command:
  `python3 scripts/build_ai4fm_public_tlaprove_import.py --include-additional-public-jsonl --out data/processed/ai4fm_public_tlaprove_import_all_public_v1.jsonl`
- current extra public surface behind that flag:
  - `13` currently excluded public JSONL files
  - `407` additional public rows from `data/toy/*` and
    `outputs/diamond_gen/*`
  - current checked-in all-public import summaries:
    - `1010` kept rows in `ai4fm_public_tlaprove_import_all_public_v1`
    - `2757` kept rows in `ai4fm_public_tlaprove_import_all_public_raw_v1`
    - only `5` new unique normalized rows beyond the default `1005`-row tracked
      import lane
- the default tracked import lane stays unchanged; this is a non-default audit
  / expansion path
- there is now a matching non-default prover-corpus build on top of that wider
  normalized import:
  - `data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl`
  - `2438` total rows (`1330` baseline prover stack + `1010` full-public
    normalized import + `98` seed prover-candidate replays)

That gives us a clean two-lane setup:

- `formalllm_eval_v1.jsonl` for the canonical `205`-example benchmark layer
- `ai4fm_public_tlaprove_import_v1.jsonl` for normalized public-AI4FM imports
- `ai4fm_public_tlaprove_import_raw_v1.jsonl` when we need the full public row
  surface without exact-final-spec collapse

## Public discovery manifest

ChatTLA now also materializes the checked-in public discovery recipe as:

- `data/processed/ai4fm_public_discovery_manifest_v1.jsonl`
- `data/processed/ai4fm_public_discovery_manifest_v1.summary.json`

Current live summary:

- `11` operational seed repos
- `7` configured org seeds and `9` configured user seeds present for auditability
- `5` checked-in search queries
- `18` unique public repo records from the live recipe
- `4` of the `5` shipped repository-search queries currently return zero repos

That mismatch matters: the pipeline config includes `orgs` and `users`, but the
checked-in loader currently ignores them and only uses `repos`. The summary
also captures the current repository-search hit counts so we can distinguish the
public discovery recipe from the larger DVC-backed raw/parsed corpus.

## Public seed repo file manifest

ChatTLA now also materializes the committed public seed-repo lane as:

- `data/processed/ai4fm_public_seed_file_manifest_v1.jsonl`
- `data/processed/ai4fm_public_seed_file_manifest_v1.summary.json`

Current live summary:

- `11` committed public seed repos
- `3140` tracked `.tla`, `.cfg`, and `.tlaps` files across those repos
- `2110` `.tla` files
- `1030` `.cfg` files
- `6` repos with clearly permissive SPDX labels at the repo level, versus `5` redistribution-caution repos (`2` NOASSERTION and `3` unknown)
- largest seed repo surfaces:
  - `tlaplus/tlaplus`: `1660` tracked files
  - `tlaplus/Examples`: `634` tracked files
  - `apalache-mc/apalache`: `608` tracked files

This is the clearest currently committed GitHub lane above the 205-entry
`FormaLLM` layer: even before the broader DVC-backed crawl, the seed repos
already expose a multi-thousand-file public formal-spec surface.

ChatTLA now has a direct builder for turning that manifest into a usable public
`.tla` corpus:

- command:
  `python3 scripts/build_ai4fm_public_seed_tla_modules.py`
- default output:
  `data/processed/ai4fm_public_seed_tla_modules_v1.jsonl`

This is the bridge from the file-level AI4FM seed surface to a concrete module
dataset we can inspect, sample, and feed into later normalization or verifier
work.

Current reconciled live summary:

- `2110` raw `.tla` files in the file-level manifest
- `2108` usable module rows after header validation
- `2` dropped `.tla` files with no accepted module header
- `0` fetch failures during materialization

ChatTLA now also has a stricter public prover-candidate builder on top of that
raw module corpus:

- command:
  `python3 scripts/build_ai4fm_public_seed_prover_candidates.py`
- default output:
  `data/processed/ai4fm_public_seed_prover_candidates_v1.jsonl`

This keeps only public seed modules that are both SANY-clean and already match
the current autoprover contract (`Init`, `Next`, `Spec`, `TypeOK`, plus `vars`
or an explicit `[Next]_vars`-style spec body). It is the cleanest public bridge
from the 2,108 usable public seed-module rows into a prover-usable corpus
without private infrastructure.

Current reconciled live summary:

- `2108` module rows considered
- `98` kept prover-candidate rows
- `1004` rows rejected by SANY
- `1006` rows rejected as not matching the current autoprover candidate shape
- `0` rows now land in the stale `missing_module_content` bucket
- the new checked-in funnel report at
  `outputs/manifests/ai4fm_public_seed_prover_funnel.json` makes the next
  expansion ceiling explicit:
  - `168` rows already match the current autoprover shape
  - `70` of those shape-ready rows are still blocked by SANY rather than by
    missing `Init` / `Next` / `Spec` / `TypeOK`
  - the largest missing-shape bucket is still the fully incompatible surface:
    `994` rows missing all four required operators plus the `vars` / temporal
    spec shape

ChatTLA now also materializes two experiment-oriented public seed lanes directly
from that funnel:

- `data/processed/ai4fm_public_seed_prover_shape_ready_v1.jsonl`
  - `168` rows that already satisfy the current autoprover shape contract
  - `114` unique modules
- `data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.jsonl`
  - `70` rows that satisfy the autoprover shape contract but are not in the
    current SANY-clean prover-candidate lane
  - `46` unique modules
  - dominated by `tlaplus/Examples` (`42` rows), `tlaplus/tlaplus` (`20`), and
    `apalache-mc/apalache` (`7`)

Those are the cleanest currently committed repair-target surfaces for widening
the public prover corpus without relaxing the current `Init` / `Next` / `Spec`
/ `TypeOK` contract.

## How ChatTLA should use them

- Treat `FormaLLM` as the canonical public prompt/spec supervision layer.
- Treat `ai4fm_public_tlaprove_corpora` as the stable public JSONL expansion
  layer available right now.
- Treat `ai4fm_public_tlaprove_import_v1` as the normalized ChatTLA-format
  import built from that public corpus stack.
- Treat `ai4fm_public_tlaprove_import_raw_v1` as the full public row lane when
  we want to preserve oversampling and duplicate examples exactly as committed.
- Treat `ai4fm_public_seed_file_manifest_v1` as the public GitHub file-level
  expansion lane already committed in the pipeline seed repos.
- Treat `ai4fm_public_seed_tla_modules_v1` as the usable raw public `.tla`
  module corpus derived from that seed-file lane.
- Treat `ai4fm_public_seed_prover_candidates_v1` as the stricter public module
  corpus for current autoprover experiments.
- Treat `ai4fm_public_discovery_manifest_v1` as the public repo-level discovery
  lane we can ingest directly today.
- Treat `tla-dataset-pipeline` DVC counts as the broader public parsing lane.
- Do not collapse these into one dataset category: the 205-entry `FormaLLM`
  benchmark is curated, `TLA-Prove` is a public corpus stack, the discovery
  manifest is a public GitHub repo roster, and the DVC surface is a larger
  extraction and transformation inventory.
- For bounded prover-corpus experiments, ChatTLA can now materialize
  `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl`
  via:
  `python3 scripts/build_tla_prover_finetune_corpus.py --public-import-weight 1 --public-seed-candidates-weight 1 --out data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl`
  This keeps the current default `chattla_tla_prover_sft_v1` stable while
  exposing a `2433`-row public-AI4FM expansion lane (`1330` default prover SFT
  rows + `1005` normalized public import rows + `98` public seed prover-candidate
  replays).

## Rebuild

```bash
python3 scripts/inspect_ai4fm_public_tlaprove_corpora.py
python3 scripts/build_ai4fm_public_tlaprove_import.py
python3 scripts/build_ai4fm_public_seed_file_manifest.py
python3 scripts/build_ai4fm_public_seed_tla_modules.py
python3 scripts/build_ai4fm_public_seed_prover_candidates.py
python3 scripts/inspect_ai4fm_public_dataset_surface.py
python3 scripts/build_ai4fm_public_discovery_manifest.py
python3 scripts/build_tla_prover_manifest.py
python3 scripts/preflight_tla_prover_corpora.py
python3 scripts/check_tla_prover_pr_ready.py --include-untracked-scripts
```

The discovery manifest builder expects a local checkout of
`LUC-AI4FM/tla-dataset-pipeline` at `/tmp/LUC-AI4FM-tla-dataset-pipeline` by
default. Pass `--pipeline-repo /path/to/tla-dataset-pipeline` if your checkout
is elsewhere.
