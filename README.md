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

## Public Dataset Surface

ChatTLA keeps three public dataset layers distinct:

1. **Benchmark / eval**
   - canonical `FormaLLM` benchmark surface: `205` prompt/spec entries
   - current handcrafted benchmark surface: `20` problems in
     `data/benchmarks/benchmark_suite.json`
   - separate historical holdout: `30` rows in
     `data/processed/diamond_eval_holdout.jsonl`

2. **Training imports**
   - tracked public `TLA-Prove` import surface: `2350` raw rows
   - normalized tracked public import: `1005` deduplicated ChatTLA-format rows
   - default prover SFT corpus continues to treat the `205`-row canonical
     `FormaLLM` layer as the benchmark/eval anchor

3. **Audited expansion artifacts**
   - full committed public `TLA-Prove` JSONL surface: `2757` rows
   - public seed repo surface: `2110` `.tla` files and `2108` usable modules
   - public seed prover candidates: `168` SANY-clean rows

Primary checked-in artifacts:

- [data/processed/formalllm_eval_v1.jsonl](/Users/eric/GitHub/ChatTLA/ChatTLA/data/processed/formalllm_eval_v1.jsonl)
- [outputs/manifests/ai4fm_public_tlaprove_corpora.json](/Users/eric/GitHub/ChatTLA/ChatTLA/outputs/manifests/ai4fm_public_tlaprove_corpora.json)
- [data/processed/ai4fm_public_tlaprove_import_v1.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/data/processed/ai4fm_public_tlaprove_import_v1.summary.json)
- [data/processed/ai4fm_public_seed_file_manifest_v1.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/data/processed/ai4fm_public_seed_file_manifest_v1.summary.json)
- [data/processed/ai4fm_public_seed_tla_modules_v1.summary.json](/Users/eric/GitHub/ChatTLA/ChatTLA/data/processed/ai4fm_public_seed_tla_modules_v1.summary.json)

For the full public-source audit trail, see
[docs/AI4FM_PUBLIC_DATASET_SURFACE.md](/Users/eric/GitHub/ChatTLA/ChatTLA/docs/AI4FM_PUBLIC_DATASET_SURFACE.md).

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
