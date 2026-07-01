# TLA Prover Status and Next Move

## Current Position

ChatTLA now has two separate quality questions:

1. whether the prover lane can produce checkable proof artifacts; and
2. whether the model can generate benchmark-quality TLA+ specs strongly enough
   to justify a fresh public release.

Those should not be conflated.

## What Is Already True

- The repo has a prover-oriented toolchain under `src/prover` and
  `src/validators/tlaps_validator.py`.
- Public proof-oriented artifacts exist and can be validated as their own lane.
- The broader repo still uses benchmark and readiness manifests as the source
  of truth for release claims.

## What Is Not Yet True

The checked-in release gates for `EricSpencer00/chattla-20b` are still blocked.
The current issue is not documentation or packaging; it is benchmark evidence.

See:

- `outputs/manifests/hf_publish_readiness.json`
- `outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json`

As checked in today, both benchmark lanes remain stale and record zero SANY and
zero TLC passes on the full 20-problem benchmark surface.

## Recommendation

Treat the next move as benchmark-first:

1. improve actual generated-spec behavior on blocked benchmark rows;
2. keep the readiness manifests honest and current;
3. only promote a fresh public model release when the checked-in benchmark
   evidence supports it.

## Practical Rule

The prover lane can inform repair strategy, but it does not by itself justify a
new public `chattla-20b` release. Public release readiness is still determined
by the benchmark and publish-gate artifacts.
