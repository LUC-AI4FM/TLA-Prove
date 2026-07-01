# ChatTLA

ChatTLA is a TLA+ generation and evaluation project built on
[`openai/gpt-oss-20b`](https://huggingface.co/openai/gpt-oss-20b).
The repo focuses on a simple standard: generated specs should be judged by
parsing and model-checking behavior, not by language-model loss alone.

Public model page:
[`EricSpencer00/chattla-20b`](https://huggingface.co/EricSpencer00/chattla-20b)

## Current Status

The checked-in publish gates currently mark ChatTLA as **not ready for a fresh
Hugging Face release**.

Authoritative checked-in evidence:

- [outputs/manifests/hf_publish_readiness.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/manifests/hf_publish_readiness.json)
- [outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json)

As of the latest checked-in manifests:

- `chattla:20b` latest full 20-problem benchmark is stale and records `0/20`
  SANY passes and `0/20` TLC passes.
- `chattla:20b-fc128best` latest full 20-problem benchmark is also stale and
  records `0/20` SANY passes and `0/20` TLC passes.
- The latest published GGUF tracked in repo state remains
  `gguf/chattla-20b-v21-Q8_0.gguf`.

That means the public benchmark claim is currently unsupported by the checked-in
benchmark evidence, and the repo reflects that directly instead of claiming a
new publish is ready.

## Public Datasets

ChatTLA currently tracks ten public AI4FM-aligned data/artifact layers spanning the 205-example `FormaLLM` benchmark, the broader 666-record checked-in `FormaLLM` repo surface, a 2,350-row tracked `TLA-Prove` training/eval slice within a 2,757-row committed public JSONL surface, and a 2,110-file / 2,108-module public seed-repo surface:

| Surface | Current checked-in scope |
| --- | --- |
| `FormaLLM` | 205 canonical prompt/spec entries across 71 families |
| `FormaLLM public repo file surface` | 666 tracked public file records spanning 503 `.tla` files, 163 `.cfg` files, and the full 410-file canonical module tree |
| `FormaLLM prover-facing smoke surface` | 410 canonical `.tla` rows joined against the latest full-dataset smoke; 7 current TLC repair candidates and 403 skipped rows in the broader canonical tree replay |
| `TLA-Prove public corpora` | 2,350 JSONL rows across the tracked public training/eval corpora; the full committed public JSONL surface currently spans 2,757 rows across 19 files |
| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the tracked public corpora slice |
| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice |
| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files |
| `tla-dataset-pipeline seed prover candidates` | 168 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows |
| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface |
| `Public repo discovery manifest` | 18 live public repo records spanning the current AI4FM GitHub discovery surface |

The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; ChatTLA treats the live `205`-entry `all_models.json` and `Input/{train,val,test}.json` split files as the canonical public FormaLLM surface.

The verifier-backed preflight manifest at `outputs/manifests/tla_prover_corpus_preflight.json` now proves exact `205/205` `FormaLLM` row coverage across the default, expanded, and full-public prover train corpora rather than relying on summary counts alone.

The checked-in broader `FormaLLM` repo surface is also materialized directly: `data/processed/formalllm_public_module_manifest_v1.jsonl` records 666 public file records spanning 503 `.tla` files, 163 `.cfg` files, and the full 410-file canonical module tree, while `data/processed/formalllm_public_prover_surface_v1.jsonl` joins the 410 canonical `.tla` rows against the latest full-dataset smoke and currently isolates 7 TLC repair candidates.

The current fresh-benchmark repair curriculum for that blocked `fc128best` lane is summarized in `data/processed/benchmark_repair_pairs_fc128best.summary.json`: `20` repair pairs now cover all `20/20` failed benchmark rows, including the `BM020` public-module fallback.

If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: `2,757` committed `TLA-Prove` JSONL rows, `2,110` public seed `.tla` files, and `2,108` usable seed modules.

Repo-level license provenance across the `11` committed public seed repos is mixed: `3` Apache-2.0, `3` MIT, `2` NOASSERTION, and `3` unknown.

Only the `205`-row `FormaLLM` layer currently feeds `chattla_tla_prover_sft_v1`; the `TLA-Prove` and seed-repo lanes above are audited public expansion artifacts, not yet mixed into that prover corpus.

There is now an explicit non-default expansion build path as well: `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl` carries the current `1330`-row prover SFT stack plus the `1005`-row normalized public `TLA-Prove` import and `168` public seed prover-candidate replays for `2503` total rows.

The broader committed-public variant is now materialized too: `data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl` carries the same prover stack plus the `1010`-row full-public normalized import for `2508` total rows.

The full tracked-corpora public row lane is also materialized at `data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl` with `2350` rows when we need the undeduped AI4FM public import surface.

benchmark_suite.json  ← 20 current benchmark items; the 30-row holdout lives in diamond_eval_holdout.jsonl

Current public benchmark surface: `20` items in `data/benchmarks/benchmark_suite.json`, plus a separate `30`-row holdout in `data/processed/diamond_eval_holdout.jsonl`:

- `data/benchmarks/benchmark_suite.json`: current 20-row handwritten benchmark gate
- `data/processed/diamond_eval_holdout.jsonl`: separate 30-row holdout artifact
- `data/processed/formalllm_eval_v1.jsonl`: canonical 205-row `FormaLLM` benchmark/eval layer

For the full public-source audit trail, see [docs/AI4FM_PUBLIC_DATASET_SURFACE.md](/Users/eric/GitHub/ChatTLA/ChatTLA/docs/AI4FM_PUBLIC_DATASET_SURFACE.md), [docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md](/Users/eric/GitHub/ChatTLA/ChatTLA/docs/AI4FM_PUBLIC_SURFACE_2026_06_29_LIVE_VERIFICATION.md), and [docs/TLA_PROVER_2026_06_29_PUBLIC_CORPUS_NEXT_MOVE_STRATEGY.md](/Users/eric/GitHub/ChatTLA/ChatTLA/docs/TLA_PROVER_2026_06_29_PUBLIC_CORPUS_NEXT_MOVE_STRATEGY.md).

## Quick Start

### Ollama

```bash
ollama run EricSpencer00/chattla-20b
```

### Transformers

```python
from transformers import pipeline

pipe = pipeline("text-generation", model="EricSpencer00/chattla-20b", device_map="auto")
result = pipe(
    [{"role": "user", "content": "Write a TLA+ spec for two-phase commit."}],
    max_new_tokens=1024,
)
print(result[0]["generated_text"][-1]["content"])
```

### GGUF / llama.cpp

```bash
huggingface-cli download EricSpencer00/chattla-20b gguf/chattla-20b-v21-Q8_0.gguf --local-dir ./chattla
./llama-cli -m chattla/gguf/chattla-20b-v21-Q8_0.gguf -n 1024 --temp 0.4
```

## Local Setup

```bash
git clone https://github.com/LUC-AI4FM/ChatTLA.git
cd ChatTLA
git submodule update --init --recursive

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Java is required for SANY and TLC validation.

## Common Local Commands

### Benchmark

```bash
python3 -m src.inference.benchmark
```

### Single generation

```bash
python3 -m src.inference.ollama_client "A distributed read-write lock." --validate
```

### Smoke training

```bash
python3 -m src.training.train --smoke-test
```

### Refresh public dataset and readiness manifests

Rebuild the public AI4FM artifacts with:

```bash
python3 scripts/inspect_ai4fm_org_surface.py
python3 scripts/build_formalllm_public_module_manifest.py
python3 scripts/build_formalllm_public_prover_surface.py
python3 scripts/inspect_ai4fm_public_tlaprove_corpora.py
python3 scripts/build_ai4fm_public_tlaprove_import.py
python3 scripts/build_ai4fm_public_seed_file_manifest.py
python3 scripts/build_ai4fm_public_seed_tla_modules.py
python3 scripts/build_ai4fm_public_seed_prover_candidates.py
python3 scripts/inspect_ai4fm_public_dataset_surface.py
python3 scripts/build_ai4fm_public_discovery_manifest.py
python3 scripts/build_tla_prover_manifest.py
python3 scripts/preflight_tla_prover_corpora.py
python3 scripts/inspect_hf_publish_readiness.py
```

## Validation Tiers

| Tier | Meaning |
| --- | --- |
| `diamond` | parses, model-checks, and carries non-trivial invariant evidence |
| `gold` | TLC-clean |
| `silver` | SANY-clean |
| `bronze` | fails SANY |

## Repository Layout

```text
ChatTLA/
├── data/
│   ├── benchmarks/
│   ├── processed/
│   └── FormaLLM/
├── docs/
├── outputs/
├── scripts/
├── src/
│   ├── inference/
│   ├── prover/
│   ├── scraper/
│   ├── training/
│   └── validators/
└── tests/
```

## Notes

- The canonical `FormaLLM` benchmark surface in this repo is the current
  `205`-example layer, not the old shorthand `30`-example framing.
- The broader public AI4FM surfaces are tracked explicitly, but they are not
  automatically treated as default prover-training data.
- Checked-in manifests are the source of truth for readiness and public-surface
  claims.
