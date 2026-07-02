# Pre-committed public claims

This file fixes the exact public claims for `EricSpencer00/chattla-20b` *before* publication,
per the project rule that the numbers must be made to match the claim — never the reverse.
Each claim is labeled by kind. Anything published (HF card, README, paper text) must quote
these strings or weaker ones; never stronger ones.

## Claim 1 — generalization (primary)

> `chattla-20b` (the `fc128best` checkpoint), evaluated on the 20-problem ChatTLA benchmark
> with the benchmark regenerated within 24 hours of publication, produces **14/20 SANY-valid**
> and **9/20 TLC-verified (gold)** specifications under the harness's best-of-5 + self-correct
> inference mode, and **4/20 SANY-valid / 1/20 TLC-verified** single-shot. Every TLC-gold row
> re-verifies from the published benchmark CSV alone.

Evidence, all checked in:
- `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json` (`ready_to_publish=true`,
  execution metadata records the inference mode),
- `outputs/benchmark_results/benchmark_results_fc128best_full_20260701_163601.csv` (+ `.meta.json`),
- `outputs/manifests/benchmark_gold_replay.json` via `scripts/replay_benchmark_gold_rows.py`
  (9/9 recorded golds reproduce under a fresh SANY/TLC run).

Conditions that keep this a generalization claim:
- The 20 benchmark problem statements and their gold specs must not appear in any training
  corpus of the evaluated checkpoint. This holds for `fc128best` (trained on diamond/FormaLLM
  action corpora predating the benchmark repair pairs).
- The freshness window (<24h) and inference-mode label come from the readiness manifest, not prose.

## Claim 2 — coverage (secondary; must always carry this label)

> The ChatTLA autoprover reproduces machine-verified TLAPS proofs for **18 known specification
> modules, 299/299 obligations proved, every module exiting 0**, re-checked by rerunning `tlapm`
> over the archived proofs (artifact dataset `EricSpencer00/chattla-tla-prover-108-108`).

This is a *coverage/reproduction* claim about known specs. It may not be presented as
generalization, and its rows may never enter a generalization benchmark number.

## Guard rails for future checkpoints

The repair-GRPO lane (`proof_repair_primary`, 35 rows) trains on repair pairs **derived from
the 20 benchmark problems**. Any checkpoint that has seen those pairs:
- must not be evaluated on the 20-row benchmark for a generalization claim — those numbers are
  coverage-labeled by construction;
- needs a disjoint held-out set (extend `diamond_eval_holdout` / the memo-vs-eval partition)
  before any new generalization number is published.
