# FC128Best Benchmark Diagnosis

## Verdict

`chattla:20b-fc128best` is currently non-deployable. A fresh full benchmark on
2026-06-28 reproduced `0/20` SANY and `0/20` TLC, and the failures are
primarily model-side parse corruption rather than a broken validator/runtime.

## Evidence

- Fresh full benchmark:
  - `outputs/benchmark_results/benchmark_results_fc128best_full_20260628_235102.csv`
  - `20` rows, `0/20` SANY, `0/20` TLC
- Publish gate:
  - `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json`
  - blocks publish with `latest full benchmark has zero SANY and zero TLC passes; do not publish this model`
- Representative parse failures from generated specs:
  - `BM002`: invented `CONSTDEF`
  - `BM003`: C-like assignment forms such as `STATE_THINKING = 1`
  - `BM011`: C-style `/* ... */` comments
  - `BM019`: placeholder syntax ending in `?`
- Historical comparison:
  - `outputs/benchmark_results/benchmark_results_fc128best_full_20260624_1640.csv`
  - the older run was partial/stale, but the new full rerun confirms the same
    outcome on completed cases rather than weakening it
- Local model/tag state:
  - local Ollama registration is `chattla:20b-fc128best`, not canonical
    `chattla:20b`
  - this can confuse benchmark claims, but it does not explain the `0/20`
    because the fresh rerun explicitly targeted `chattla:20b-fc128best`

## Repo Fixes Landed

- `scripts/inspect_hf_publish_readiness.py` now blocks publish on a fresh
  benchmark that still scores `0/20`.
- `scripts/inspect_hf_publish_readiness.py` and `src.training.publish_hf` now
  accept a benchmark-model lane, so canonical `chattla:20b` readiness and
  candidate-specific lanes such as `chattla:20b-fc128best` no longer get
  flattened into one ambiguous “latest full benchmark” story.
- `src.training.publish_hf` now finds the local fallback GGUF under
  `outputs/gguf_fc128_best/` during dry-run/readiness checks, matching the
  readiness inspector instead of falsely reporting “GGUF missing”.
- `src/inference/benchmark.py` now zeros `structural_score` when SANY parsing
  fails, so unparsable pseudo-TLA no longer looks structurally healthy.

## Canonical Lane Status

The new benchmark-model split makes the current repository state clearer:

- Canonical publish lane:
  - `python3 scripts/inspect_hf_publish_readiness.py`
  - benchmark model: `chattla:20b`
  - current source: `outputs/benchmark_results_v14_full_20260404.csv`
  - current verdict: still blocked, because the latest canonical full benchmark
    is both stale and `0/20`
- Candidate lane:
  - `python3 scripts/inspect_hf_publish_readiness.py --benchmark-model chattla:20b-fc128best`
  - current source: `outputs/benchmark_results/benchmark_results_fc128best_full_20260628_235102.csv`
  - current verdict: fresh but still blocked at `0/20`

## Interpretation

The model is producing specs that preserve superficial section structure but
collapse syntactically: malformed declarations, foreign comment syntax, bogus
operators, and placeholder fragments. This is consistent with a bad checkpoint
or bad candidate model, not with a TLC/SANY environment regression.

## Next Move

Do not publish `fc128best`. Treat it as a rejected candidate and continue from
the full-spec GRPO / next-candidate path. The repair loop can now consume the
fresh benchmark failures directly via:

- `python3 scripts/build_benchmark_repair_pairs.py --benchmark-model chattla:20b-fc128best`
- `python3 scripts/build_tla_prover_repair_corpus.py`
- `python3 -m scripts.train_rl_repair --include-benchmark-repair-pairs`

If a local long-Ralph run exists, the tracked repair-corpus builder also folds
in `data/processed/ralph_repair_pairs_long_latest.jsonl` automatically.

Any future comparison should record the exact Ollama tag used and should
benchmark a canonically registered model tag if the result is meant to speak
for `chattla:20b`.
