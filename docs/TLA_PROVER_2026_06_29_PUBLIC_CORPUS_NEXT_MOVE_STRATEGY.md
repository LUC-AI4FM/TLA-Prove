# TLA Prover Public Corpus Next Move Strategy

**Date**: 2026-06-29

## Question

Given the current public AI4FM corpus work, what should ChatTLA do next to
improve the prover model without weakening the Hugging Face publish path?

The decision this research informs: whether the next bounded experiment should
change the default prover training lane, switch to the broader committed-public
lane, or treat the new seed-module lanes as repair/eval surfaces instead of
training data.

## Verdict

Keep the current default prover SFT lane unchanged.

Use the public-corpus work in three different ways:

1. keep `data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl` as the
   default training lane;
2. use the two non-default public-expanded prover corpora only for bounded
   comparisons;
3. use the new `shape_ready_not_sany` lane as a repair/eval target set, not as
   a training lane.

The repo now has enough public corpus coverage. The gating problem is model
quality: current publish readiness is still blocked by fresh `0/20` or stale
`0/20` benchmark results, not by missing public data.

## Evidence

| Source | Evidence | Implication |
| --- | --- | --- |
| `data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json` | Current default prover SFT is `1330` rows and already includes the full `205`-row `FormaLLM` layer. | The original `30`-row concern is resolved for the prover training lane itself. |
| `data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json` | Non-default tracked-public expanded lane is `2459` rows: `1330` base stack + `1005` normalized public import + `124` SANY-clean seed candidates. | This is the main public-expanded training candidate already materialized. |
| `data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json` | Broader committed-public lane is `2464` rows with `1010` normalized public-import rows. | The full committed-public `TLA-Prove` surface only buys `5` extra unique normalized rows beyond the tracked-public lane. |
| `outputs/manifests/ai4fm_public_seed_prover_funnel.json` | `2108` usable seed modules -> `168` shape-ready rows -> `144` SANY-clean rows, leaving `24` shape-ready-but-not-SANY-clean rows. | The strongest remaining public-data headroom is in verifier/repair work on the narrowed `24`-row residual queue, not in scraping more JSONLs. |
| `data/processed/ai4fm_public_seed_prover_shape_ready_v1.summary.json` | Shape-ready public seed lane is `168` rows with `114` unique modules. | This lane is useful as an analysis/eval surface for autoprover-shaped modules. |
| `data/processed/ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json` | Repair-target lane is `24` rows with `18` unique modules after excluding the `144` SANY-clean rows. | These are immediate repair targets, but not safe training inputs under the current syntax/verification problems. |
| `outputs/manifests/hf_publish_readiness.json` | Canonical `chattla:20b` lane is blocked because the newest full benchmark is stale and also `0` SANY / `0` TLC. | The canonical public model is not publishable. |
| `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json` | `chattla:20b-fc128best` has a fresh full benchmark but still `0` SANY / `0` TLC. | Freshness alone does not clear the gate; candidate quality is also non-deployable. |
| `docs/TLA_PROVER_2026_06_29_FC128BEST_DIAGNOSIS.md` | Representative failures are parse corruption (`CONSTDEF`, C-style assignment/comment syntax, placeholder fragments). | Training on known non-SANY rows right now is more likely to worsen the current blocker than to help it. |

## Decision

### Training lanes

Keep these roles:

- `chattla_tla_prover_sft_v1` (`1330` rows):
  current default and the only lane that should be treated as the stable
  baseline.
- `chattla_tla_prover_sft_public_expanded_v1` (`2459` rows):
  the main bounded public-expansion training comparison.
- `chattla_tla_prover_sft_public_all_v1` (`2464` rows):
  a secondary bounded comparison for testing whether the extra `5` normalized
  rows help at all.

### Eval / repair-target lanes

Use these as non-training surfaces for now:

- `ai4fm_public_seed_prover_shape_ready_v1` (`168` rows):
  shape-compatible public modules that can support verifier-side analysis and
  future targeted experiments.
- `ai4fm_public_seed_prover_shape_ready_not_sany_v1` (`24` rows):
  the immediate repair-target surface for syntax/SANY cleanup work.

### Explicit non-decision

Do **not** switch any default training path to the full committed-public lane
or to either shape-ready seed lane at this point. None of those moves address
the current publish blocker directly, and one of them would inject known
non-SANY data into a model family that is already failing basic parse gates.

## Rejected Alternatives

### 1. Promote the `2464`-row full-public lane to the default immediately

Rejected because the delta over `2459` is only `5` unique normalized public
rows. That is too small to justify changing the default before there is any
verifier-backed model evidence.

### 2. Train directly on the `168` shape-ready public seed rows

Rejected for now because the lane intentionally includes the `24`
shape-ready-but-not-SANY-clean rows. The current public blocker is parse /
verification quality, so mixing known invalid rows into the next training lane
is poorly aligned.

### 3. Train directly on the `24` repair-target rows

Rejected. These are useful because they isolate the remaining public headroom,
but they are not safe as training inputs until we know why they fail SANY and
whether those failures are recoverable without introducing more syntax noise.

## Next Experiment

Run bounded comparisons in this order:

1. Keep `chattla_tla_prover_sft_v1` as the baseline control.
2. Compare against `chattla_tla_prover_sft_public_expanded_v1`.
3. Compare against `chattla_tla_prover_sft_public_all_v1` only if step 2 shows
   a real gain or at least no regression.
4. Keep `ai4fm_public_seed_prover_shape_ready_not_sany_v1` as a sidecar repair
   queue for syntax/SANY cleanup experiments, not as a supervised fine-tune
   input.

The public-corpus-specific commands already materialized in the repo are:

```bash
python3 scripts/build_tla_prover_finetune_corpus.py \
  --public-import-weight 1 \
  --public-seed-candidates-weight 1 \
  --out data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl

python3 scripts/build_tla_prover_finetune_corpus.py \
  --public-import data/processed/ai4fm_public_tlaprove_import_all_public_v1.jsonl \
  --public-import-weight 1 \
  --public-seed-candidates-weight 1 \
  --out data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl

python3 scripts/build_ai4fm_public_seed_prover_shape_corpora.py
```

The evaluation emphasis should stay on verifier-backed outcomes:

- canonical/full benchmark freshness and nonzero SANY/TLC;
- no syntax regression versus the current baseline lane;
- prover-side evidence on the existing TLAPS/known18 surfaces;
- targeted analysis of the `24` repair-target modules outside the training path.

## Promotion Gates

Do not publish a new public model unless all of the following are true:

1. `python3 scripts/inspect_hf_publish_readiness.py` reports
   `ready_to_publish: true` for the canonical lane; and
2. the latest fresh full benchmark is not another `0/20` SANY / `0/20` TLC
   outcome; and
3. the chosen candidate matches or beats the baseline on verifier-backed
   metrics without introducing syntax/module regressions.

## Abort Gates

Abort or demote a public-corpus experiment if any of the following appear:

1. full benchmark remains `0/20` SANY / `0/20` TLC;
2. syntax quality regresses versus the baseline lane;
3. improvements are explainable only by the extra `5` full-public normalized
   rows but do not survive a fresh verifier-backed evaluation;
4. training on shape-ready-but-not-SANY-clean rows worsens parse or verification
   quality.

## Recommendation

The public corpus side is now sufficiently built out. The next real win is to
use the repo's new public lanes to run disciplined, bounded comparisons while
keeping the publish gate strict. The best immediate experiment is the existing
`2459`-row public-expanded lane, with the `2464`-row full-public lane as a
small follow-up and the `24` repair-target rows reserved for verifier-side
cleanup work.
