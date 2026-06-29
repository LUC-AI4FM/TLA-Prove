# ChatTLA

Fine-tuning [`openai/gpt-oss-20b`](https://huggingface.co/openai/gpt-oss-20b) to generate verifiably correct [TLA+](https://lamport.azurewebsites.net/tla/tla.html) formal specifications.

**Key differentiator**: TLC model checking is the primary training metric — not perplexity. A generated spec must pass the TLA+ model checker before it counts as a success.

**Model:** [EricSpencer00/chattla-20b](https://huggingface.co/EricSpencer00/chattla-20b) (Apache 2.0)

---

## Quick Start

**Ollama (recommended):**
```bash
ollama run EricSpencer00/chattla-20b
```

**Python (transformers):**
```python
from transformers import pipeline

pipe = pipeline("text-generation", model="EricSpencer00/chattla-20b", device_map="auto")
result = pipe([{"role": "user", "content": "Write a TLA+ spec for two-phase commit."}], max_new_tokens=1024)
print(result[0]["generated_text"][-1]["content"])
```

**GGUF / llama.cpp:**
```bash
huggingface-cli download EricSpencer00/chattla-20b gguf/chattla-20b-v21-Q8_0.gguf --local-dir ./chattla
./llama-cli -m chattla/gguf/chattla-20b-v21-Q8_0.gguf -n 1024 --temp 0.4
```

---

## Checked-in Benchmark Snapshot (v15)

| Tier | Rate | Criterion |
|------|------|-----------|
| Diamond | 9/30 (30%) | Parses + model-checks + non-trivial invariants |
| Gold    | 9/30 (30%) | Parses + model-checks cleanly |

Evaluated on a 30-spec held-out suite with up to 3 self-correction attempts via TLC feedback.
The latest public Hugging Face GGUF is currently `gguf/chattla-20b-v21-Q8_0.gguf`; local publish readiness is tracked in `outputs/manifests/hf_publish_readiness.json` for the canonical `chattla:20b` lane and `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json` for the current `fc128best` candidate lane.
The current fresh-benchmark repair curriculum for that blocked `fc128best` lane is summarized in `data/processed/benchmark_repair_pairs_fc128best.summary.json`: `19` repair pairs cover `19/20` failed benchmark rows, leaving only `BM020` without a public gold target today.

---

## Public Datasets

ChatTLA currently tracks eight public AI4FM-aligned data/artifact layers spanning the 205-example `FormaLLM` benchmark, a 2,350-row tracked `TLA-Prove` training/eval slice within a 2,757-row committed public JSONL surface, and a 2,110-file / 2,108-module public seed-repo surface:

| Layer | Current public surface | Local artifact |
|------|-------------------------|----------------|
| `FormaLLM` | 205 canonical prompt/spec entries across 71 families | `data/processed/formalllm_eval_v1.jsonl` |
| `TLA-Prove public corpora` | 2,350 JSONL rows across the tracked public training/eval corpora; the full committed public JSONL surface currently spans 2,757 rows across 19 files | `outputs/manifests/ai4fm_public_tlaprove_corpora.json` |
| `TLA-Prove normalized import` | 1,005 deduplicated ChatTLA-format rows built from the committed public corpora | `data/processed/ai4fm_public_tlaprove_import_v1.jsonl` |
| `TLA-Prove raw import` | 2,350 undeduped ChatTLA-format rows spanning the full tracked public corpora slice | `data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl` |
| `tla-dataset-pipeline seed repo files` | 3,140 tracked `.tla` / `.cfg` / `.tlaps` files across the 11 committed public seed repos, including 2,110 `.tla` files | `data/processed/ai4fm_public_seed_file_manifest_v1.jsonl` |
| `tla-dataset-pipeline seed prover candidates` | 98 SANY-clean prover-candidate rows from 2,108 usable public seed-module rows | `data/processed/ai4fm_public_seed_prover_candidates_v1.jsonl` |
| `tla-dataset-pipeline discovery` | 18 live public repo records from the checked-in seed/search recipe; 4 of 5 shipped search queries currently return zero repositories | `data/processed/ai4fm_public_discovery_manifest_v1.jsonl` |
| `tla-dataset-pipeline` | 2,628 extracted raw files and 3,979 parsed artifacts in the public DVC surface | `outputs/manifests/ai4fm_public_dataset_surface.json` |

The mixed prover SFT lane already carries the full `205`-row `FormaLLM` benchmark. The generated local training file is `data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl`, and the committed public copy is `outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl`; the nearby `30`-row corpora in this repo are holdout/eval slices, not the prover training corpus.
The verifier-backed preflight manifest at `outputs/manifests/tla_prover_corpus_preflight.json` now proves exact `205/205` `FormaLLM` row coverage across the default, expanded, and full-public prover train corpora rather than relying on summary counts alone.
Only the `205`-row `FormaLLM` layer currently feeds `chattla_tla_prover_sft_v1`; the `TLA-Prove` and seed-repo lanes above are audited public expansion artifacts, not yet mixed into that prover corpus.
There is now an explicit non-default expansion build path as well: `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl` carries the current `1330`-row prover SFT stack plus the `1005`-row normalized public `TLA-Prove` import and `98` public seed prover-candidate replays for `2433` total rows. It is meant for bounded experiments, not as the default training lane.
The broader committed-public variant is now materialized too: `data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl` carries the same prover stack plus the `1010`-row full-public normalized import for `2438` total rows.
The full tracked-corpora public row lane is also materialized at `data/processed/ai4fm_public_tlaprove_import_raw_v1.jsonl` with `2350` rows when we need the undeduped AI4FM public import surface.
There is also an opt-in full committed-surface import path now: `python3 scripts/build_ai4fm_public_tlaprove_import.py --include-additional-public-jsonl --out data/processed/ai4fm_public_tlaprove_import_all_public_v1.jsonl` pulls in the currently excluded `data/toy/*` and `outputs/diamond_gen/*` files (`407` public rows across `13` JSONLs) without changing the default tracked-corpora lane. The current checked-in all-public import summaries land at `1010` deduped rows and `2757` raw rows, so the broader committed JSONL surface adds only `5` new unique normalized examples on top of the existing `1005`-row tracked import.

Rebuild the public AI4FM artifacts with:

```bash
python3 scripts/inspect_ai4fm_org_surface.py
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

The `TLA-Prove` report intentionally distinguishes the stable tracked training/eval corpora (`2,350` rows across `6` files) from the full committed public JSONL surface (`2,757` rows across `19` files, including `data/toy/*` and `outputs/diamond_gen/*`). The normalized import turns the tracked corpora slice into a deduplicated ChatTLA-format corpus.
The discovery manifest needs a local checkout of `LUC-AI4FM/tla-dataset-pipeline`; override it with `--pipeline-repo <path>` if your checkout is not at `/tmp/LUC-AI4FM-tla-dataset-pipeline`.
The seed file manifest records the committed public seed-repo file surface directly from GitHub trees. The dataset surface report records the broader DVC-backed counts, while the discovery manifest records what the public seed/search recipe currently materializes. The manifest build, corpus preflight, and PR-ready check are the compact local gates for the checked-in public artifact surface.
The older `1800+` FormaLLM wording comes from a stale architecture-doc note, not the current committed public metadata; ChatTLA treats the live `205`-entry `all_models.json` and `Input/{train,val,test}.json` split files as the canonical public FormaLLM surface. See `docs/AI4FM_PUBLIC_DATASET_SURFACE.md` for the exact upstream evidence and links.
If someone cites a public AI4FM GitHub surface of `1,800+`, the reproducible interpretation today is the broader expansion lanes above: `2,757` committed `TLA-Prove` JSONL rows, `2,110` public seed `.tla` files, and `2,108` usable seed modules. That is a statement about broader public AI4FM corpora, not the canonical `FormaLLM` benchmark.
The checked-in org-surface manifest at `outputs/manifests/ai4fm_org_surface.json` makes that broader GitHub surface concrete: on 2026-06-29 the public `LUC-AI4FM` org exposed `8` repos, with `FormaLLM`, `TLA-Prove`, and `tla-dataset-pipeline` as the `3` corpus-relevant ones.
Repo-level license provenance across the `11` committed public seed repos is mixed: `3` Apache-2.0, `3` MIT, `2` NOASSERTION, and `3` unknown. Treat the `5` non-permissive/unknown buckets as redistribution-caution surfaces until reviewed separately; see `outputs/manifests/ai4fm_public_seed_license_surface.json`.
The seed prover-candidate corpus is the first stricter audited bridge from the 2,110 public `.tla` files / 2,108 usable module rows toward future prover-lane expansion: it keeps only modules that pass SANY and already match the Phase-1 `Init`/`Next`/`Spec`/`TypeOK` autoprover contract.

---

## Project Structure

```
ChatTLA/
├── data/
│   ├── FormaLLM/        ← git submodule: seed specs (MIT)
│   ├── processed/       ← train/eval corpora, including formalllm_eval_v1.jsonl
│   └── benchmarks/
│       └── benchmark_suite.json  ← 30 hand-crafted eval problems
├── src/
│   ├── scraper/         ← Phase 1: data collection
│   ├── validators/      ← TLC/SANY wrappers
│   ├── training/        ← Phase 2: fine-tuning
│   └── inference/       ← Phase 3: deployment & eval
├── scripts/             ← RL loop, pipeline, and training scripts
├── configs/
│   └── accelerate_fsdp.yaml
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_finetuning.ipynb
│   └── 03_evaluation.ipynb
└── outputs/
    ├── eval/            ← benchmark result JSON files
    └── diamond_gen/     ← curated diamond-tier training data
```

---

## Setup

```bash
# 1. Clone and initialise submodules
git clone https://github.com/LUC-AI4FM/ChatTLA.git
cd ChatTLA
git submodule update --init --recursive

# 2. Create virtual environment and install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env: set HF_TOKEN (for publishing), GITHUB_TOKEN_1 (for scraping)

# 4. Verify Java (required for TLC/SANY validator)
java -version    # needs Java 8+
```

---

## Phases

### Phase 1 — Data Collection

```bash
# FormaLLM seed only (fast, no GitHub token needed):
python -m src.scraper.pipeline --no-github --no-annotate

# Full scrape (several hours, needs GITHUB_TOKEN_1):
python -m src.scraper.pipeline
```

**Output:** `data/validated/combined.jsonl`

### Phase 2 — Fine-Tuning

```bash
# Smoke test (10 steps):
python -m src.training.train --smoke-test

# Full training:
python -m src.training.train

# Monitor with MLflow:
mlflow ui --port 5000

# Merge LoRA into base:
python -m src.training.merge_lora
```

**Primary metric:** `tlc/tlc_clean_rate` > 0.70 on eval set.

### Phase 3 — Inference & Evaluation

```bash
# Convert to GGUF and register with Ollama:
python -m src.inference.convert_to_gguf

# Run 30-problem benchmark:
python -m src.inference.benchmark

# Quick spec generation:
python -m src.inference.ollama_client "A distributed read-write lock." --validate
```

---

## Model Details

| Property | Value |
|----------|-------|
| Base model | `openai/gpt-oss-20b` |
| Architecture | MoE, 21B total / 3.6B active |
| Quantisation | MXFP4 → dequantised to BF16 for training |
| PEFT | LoRA rank 8, all-linear + MoE expert layers |
| Prompt format | [harmony](https://github.com/openai/harmony) (required) |
| License | Apache 2.0 |

---

## Validation Tiers

| Tier | Criterion | Training use |
|------|-----------|-------------|
| **diamond** | TLC model-checks with non-trivial invariants | Primary GRPO reward signal |
| **gold** | TLC model-checks with zero violations | Primary SFT data |
| **silver** | SANY parses (syntactically valid) | Training data (labelled) |
| **bronze** | SANY fails | Rejected; kept for error analysis |

---

## Benchmark Suite

30 hand-crafted TLA+ problems in `data/benchmarks/benchmark_suite.json`:

| Domain | Count | Examples |
|--------|-------|---------|
| Consensus | 4 | Paxos, Raft leader election, Bakery, Dekker's |
| Scheduling | 4 | Mutex, Dining Philosophers, Peterson's, Token Ring |
| Transactions | 2 | Two-Phase Commit, Snapshot Isolation |
| Storage | 5 | KV Store, Allocator, G-Counter CRDT, Producer-Consumer, RW Lock |
| Networking | 5 | Chandy-Lamport, Gossip, BRP, Publish-Subscribe, Clock Sync |

Difficulty ranges from 2 (beginner) to 5 (research-grade).

---

## Research Notes

- **TLC as reward signal:** `TLCEvalCallback` runs TLC at every `eval_steps` and logs `tlc_clean_rate` to MLflow — the experiment's primary metric.
- **Repair-based GRPO:** The RL loop uses improvement reward (did repair fix the spec?) rather than absolute pass/fail, giving non-zero reward variance even on hard problems.
- **Self-annotation:** Local Ollama `gpt-oss:20b` annotates specs — zero cost, fully air-gapped. See `src/scraper/annotate.py`.
- **Harmony format** is mandatory for gpt-oss — applied at `dataset_builder.py` time.
- **Deduplication:** MinHash LSH (Jaccard ≥ 0.8) via `datasketch` prevents near-duplicate specs from inflating training quality.
- **License hygiene:** GitHub scraper filters to MIT/Apache/BSD/ISC/Unlicense only.

See [`docs/MODEL_QUALITY.md`](docs/MODEL_QUALITY.md) for quality targets and [`docs/TRAINING_PIPELINE_AUDIT.md`](docs/TRAINING_PIPELINE_AUDIT.md) for the full pipeline map.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HF_TOKEN` | For publishing | Hugging Face Hub write token |
| `GITHUB_TOKEN_1` | For Phase 1 scraping | GitHub API token (30 req/min authenticated) |
| `OLLAMA_HOST` | Optional | Ollama daemon URL (default: `http://localhost:11434`) |
| `CHATTLA_MODEL_DIR` | Optional | External path for merged model weights (default: `outputs/`) |
| `CUDA_VISIBLE_DEVICES` | Optional | GPU assignment |

Copy `.env.example` to `.env` and fill in values. Never commit `.env`.

---

## License

Apache 2.0. See [LICENSE](LICENSE).

Seed data from [FormaLLM](https://github.com/LUC-AI4FM/FormaLLM) (MIT).
Broader public TLA+ extraction/parsing metadata comes from [LUC-AI4FM/tla-dataset-pipeline](https://github.com/LUC-AI4FM/tla-dataset-pipeline).
