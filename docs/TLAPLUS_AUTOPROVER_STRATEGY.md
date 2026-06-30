# TLA+ Autoprover Strategy

**Date**: 2026-06-26

## Question

How should ChatTLA explore a practical TLA+ autoprover path?

The decision this research informs: whether to invest next in proof generation,
invariant generation, better model training, or toolchain setup.

## Verdict

Pursue a verifier-guided autoprover pipeline, not raw proof generation.

The practical shape is:

1. generate or extract a candidate safety property / invariant;
2. use TLC or Apalache to check inductiveness and produce counterexamples;
3. use a model only for narrow repair steps, lemma suggestions, and proof
   decomposition;
4. emit deterministic TLAPS skeletons;
5. validate every candidate with `tlapm`.

This aligns with the repo's existing `src/prover` design and with the external
tool landscape. Free-form TLAPS proof generation has already shown the same
failure mode as full-spec GRPO: the model writes analysis/prose instead of a
checkable proof.

## Evidence

| Source | Evidence | Implication |
| --- | --- | --- |
| `src/prover/cegis.py` | Existing CEGIS loop already searches for inductive invariants using TLC counterexamples and emits proof skeletons. | We have the right architecture seed. |
| `src/prover/skeleton.py` | Existing deterministic hierarchical safety proof skeleton generator. | Keep proof shape deterministic; use model only for missing predicates/lemmas. |
| `src/validators/tlaps_validator.py` | Wrapper expects `src/shared/tlaps/bin/tlapm`, parses proved/partial/unproved/parse_error. | Validation surface exists, but the local TLAPS binary is currently missing. |
| Local check | `tlapm` and `apalache-mc` are not on PATH; `src/shared/tlaps/bin/tlapm` is absent. | First blocker is tool packaging, not model training. |
| `outputs/prover_diagnose*.json` | Current prover generations frequently leak analysis prose and fail parse or prove zero obligations. | Raw proof SFT is not enough; force structure and verifier feedback. |
| Selected local tests | `test_inductiveness.py`, `test_cegis.py`, `test_skeleton.py`, `test_proposer.py`, `test_obligation_router.py` pass: `32 passed`. | Deterministic prover pillars are currently healthy. |
| TLAPS docs | TLAPS mechanically checks TLA+ proofs, uses backend verifiers, and is suitable for non-trivial safety proofs but does not perform full temporal reasoning in the current release. | Scope first milestone to safety/invariance, not arbitrary liveness proofs. |
| TLAPS tactics docs | Default TLAPS behavior tries SMT/Z3, Zenon, and Isabelle-style backends; complex obligations should be decomposed into simpler obligations. | Autoprover should decompose obligations instead of hoping one backend proves a large leaf. |
| Apalache docs | Apalache supports bounded model checking and inductiveness checking via SMT solvers such as Z3/CVC5. | Apalache is useful as a second invariant oracle, especially for finite domains and larger symbolic spaces. |
| RAG TLAPS proof-generation paper | Recent TLAPS LLM work combines obligation decomposition with retrieval from verified proofs; it reports limits on complex theorems. | Use RAG over verified TLAPS snippets and decomposition as core strategy. |

## Tool Roles

### TLC

Use TLC for:

- SANY/parse sanity;
- finite-state executable model checking;
- concrete counterexamples;
- current `check_inductive` oracle.

TLC is the default operational oracle because it is already wired in and passes
tests.

### Apalache

Use Apalache for:

- SMT-backed bounded model checking;
- inductiveness checks over fixed or bounded parameters;
- examples where explicit-state TLC blows up.

Do not make Apalache the first dependency unless packaging is easy. Add it as a
parallel oracle after TLAPS packaging is fixed.

### TLAPS / `tlapm`

Use TLAPS for:

- final proof validation;
- proof-obligation feedback;
- measuring whether generated proofs are actually machine-checkable.

TLAPS should be the promotion gate, not the generator.

### Model

Use the model for narrow synthesis:

- propose one invariant strengthening from a CTI;
- propose a small lemma or sub-obligation;
- choose relevant facts from the fact library;
- repair a failed proof leaf using the exact `tlapm` output.

Avoid asking the model to produce a whole complex proof in one shot.

## Recommended Architecture

The first autoprover loop should be:

1. Parse module and classify theorem with `obligation_router`.
2. Reject or defer unsupported liveness-heavy obligations.
3. Extract or select a base invariant: `TypeOK`, declared invariant, or target
   state predicate.
4. Run TLC inductiveness check.
5. If not inductive, feed CTI to the proposer for one additional conjunct.
6. Repeat for a small bounded number of iterations.
7. If inductive, emit deterministic TLAPS safety skeleton.
8. Run `tlapm`.
9. If a leaf fails, retrieve similar verified proof steps and ask the model for
   a small repair.
10. Save the full trace: module, theorem, candidate invariant, CTI, skeleton,
    TLAPS output, and repair attempts.

## Current Experimental Result

The strongest result so far is the corrected top-level definition expansion
experiment on Sophia:

| Job | Result | Decision |
| --- | --- | --- |
| `160685` | Baseline deterministic TLAPS skeleton over 18 TLC-inductive candidates: 17 partial, 1 unproved/timeout, 123/170 obligations proved, 47 failed. | Good enough to prove the harness; not enough to promote. |
| `160689` | Re-ran the same proof modules and preserved full `tlapm` stdout/stderr under `outputs/autoprover/tlaps_repair_160689/`. | Keep raw TLAPS output as required evidence for every repair loop. |
| `160702` | Action-split proof experiment was worse on the first modules: AtomicRegister 6/14 failed vs 3/10 baseline, CircuitBreaker 4/12 vs 3/10, HeartbeatFailureDetector 7/16 vs 3/10. | Reject broad action splitting as the next default. |
| `160703` | Expanded all regex-matched operator names, including indented LET-local names such as `winner`, causing TLAPS elaboration errors. | Reject naive definition extraction; only use top-level definitions. |
| `160704` | Top-level-only `BY DEF` expansion completed: 18 candidates, 4 fully proved (`AtomicCommit`, `ByzantineQuorum`, `VotingMajority`, `SzymanskiMutex`), failed leaves reduced from 47 to 23. | Accept as the current deterministic skeleton baseline. |
| `160705` / `160706` / `160709` | Tried init-leaf expansion variants. Every module returned `exit_3` quickly with a TLAPS `schedule.ml` assertion failure, including modules fully proved by `160704`. Direct reruns showed `--cleanfp` and `--nofp` alone still crash, while `tlapm --threads 1` re-proves `AtomicCommit` from a clean cache. | Treat these jobs as invalid harness evidence. Every TLAPS variant run must use `--threads 1`; cache isolation alone is insufficient. |
| `160710` | Re-ran init-leaf variants with `tlapm --threads 1`. `init_all_defs` and `init_safe_defs` tied: 18 candidates, 9 fully proved, 9 partial, 92/108 obligations proved, 16 failed leaves. Fully proved: `RetryWithBackoff`, `TokenRing`, `AtomicCommit`, `ByzantineQuorum`, `VotingMajority`, `WitnessReplication`, `EventCount`, `SzymanskiMutex`, `ResourceLease`. | Promote `init_safe_defs` plus `--threads 1` as the new deterministic skeleton baseline. |

The key lessons are narrow and actionable:

- TLAPS 1.5.0 must run with `--threads 1` for this workload.
- Expanding top-level definitions in the inductive leaf improves the baseline.
- Expanding non-transition/domain/helper definitions in the init leaf improves
  it again.
- `init_all_defs` and `init_safe_defs` tied in `160710`; prefer
  `init_safe_defs` because it is smaller and avoids unnecessary transition
  expansion in `Init => TypeOK`.

## Next Experiment

Adopt the `160710` `init_safe_defs` skeleton as the new default:

- generate deterministic proof leaves with top-level defs in the inductive
  step;
- add only non-transition constants/domain/helper definitions to
  `Init => TypeOK`;
- run `tlapm --threads 1`;
- preserve exact raw `tlapm` output and flags.

Next repair loop: target the 16 remaining failed leaves with decomposition or
small helper lemmas. Remaining modules are:

- `AtomicRegister`: 1 failed inductive leaf;
- `CircuitBreaker`: 2 failed leaves;
- `HeartbeatFailureDetector`: 1 failed inductive leaf;
- `RoundRobinScheduler`, `SleepingBarber`, `DistributedLock`,
  `IdempotencyKey`, `LeaderLease`, `TwoPhaseLockingDeadlock`: 2 failed leaves
  each.

Rejected near-term alternatives:

- broad method switching (`--method smt`, `z3`, `auto`, `force`, `blast`) did
  not improve representative failures and sometimes worsened them;
- broad constant-assumption insertion did not improve a representative
  `DistributedLock` run;
- whole-proof generation remains lower priority than failed-leaf
  decomposition because deterministic repair already improved failed leaves
  from 47 to 16.

## Significant Findings

- Run TLAPS as `tlapm --threads 1`; default scheduling can crash otherwise
  valid proof attempts in `schedule.ml`.
- Deterministic proof shaping is currently higher leverage than more GRPO or
  whole-proof generation: failed leaves improved `47 -> 23 -> 16`.
- Use `init_safe_defs`, not `init_all_defs`, as the default. They tied in
  `160710`, but `init_safe_defs` is smaller and avoids transition expansion in
  the init leaf.
- The next useful experiment is narrow failed-leaf decomposition/helper lemmas
  over the remaining 16 leaves.
- New finding to test broadly: top-level module `ASSUME` facts may not appear
  in generated TLAPS obligations. Lifting them into the theorem body made
  `RoundRobinScheduler` fully prove in a direct `--threads 1` test.

PBS `160748` (`tlaps_theorem_assumes_t1`) confirms this is worth promoting:
18 candidates, 11 fully proved, 7 partial, 96/108 obligations proved, 12 failed
leaves. Assumption lifting fully proved `RoundRobinScheduler` and
`SleepingBarber` on top of the `160710` baseline.

New default skeleton:

- `init_safe_defs`;
- top-level defs in the inductive leaf;
- lift top-level module `ASSUME` facts into the theorem body;
- run `tlapm --threads 1`.

Remaining target set: `AtomicRegister:1`, `CircuitBreaker:2`,
`HeartbeatFailureDetector:1`, `DistributedLock:2`, `IdempotencyKey:2`,
`LeaderLease:2`, `TwoPhaseLockingDeadlock:2`.

## 160764 Result

`160764` promotes synthesized theorem preconditions for symbolic constants:
18 candidates, 12 fully proved, 6 partial, 99/108 obligations proved, 9 failed
leaves. It fully proved `DistributedLock` and reduced `LeaderLease` from 2
failed leaves to 1.

Current remaining target set: `AtomicRegister:1`, `CircuitBreaker:2`,
`HeartbeatFailureDetector:1`, `IdempotencyKey:2`, `LeaderLease:1`,
`TwoPhaseLockingDeadlock:2`.

## 160776 Result

`160776` promotes sentinel-exclusion theorem preconditions: 18 candidates,
14 fully proved, 4 partial, 102/108 obligations proved, 6 failed leaves.
Adding `NONE \notin Nodes` fully proved `LeaderLease`; adding
`NONE \notin Txns` fully proved `TwoPhaseLockingDeadlock`.

Current remaining target set: `AtomicRegister:1`, `CircuitBreaker:2`,
`HeartbeatFailureDetector:1`, `IdempotencyKey:2`.

## Targeted Remaining-Leaf Findings

Sophia artifact:
`outputs/autoprover/tlaps_targeted_remaining_t1_151715/summary.json`.

- `CircuitBreaker` proves with targeted action splitting plus init facts:
  `22/22` obligations, exit 0.
- `HeartbeatFailureDetector` proves with targeted action splitting:
  `18/18` obligations, exit 0.
- These close 3 of the 6 remaining `160776` failed leaves in normalized terms,
  but raw TLAPS obligation denominators change after splitting. Do not claim
  `108/108` until a normalized verifier or full mixed sweep reports it.
- `AtomicRegister` action splitting isolates the only failure to
  `ReadImpose`: `TypeOK /\ (\E n, Q : ReadImpose(n, Q)) => TypeOK'`.
- `IdempotencyKey` is a finite-set/cardinality proof problem. `Retry` proves;
  `Init` and `FirstCall` remain blocked, and importing `FiniteSetTheorems`
  alone does not close them.
- Mixed validation job `160785` confirms the promoted state: 18 modules,
  16 fully proved, raw `133/136` obligations proved. The only remaining
  nonzero modules are `AtomicRegister` (`5/6`) and `IdempotencyKey` (`4/6`).
  Artifact:
  `outputs/autoprover/tlaps_mixed_targeted_t1_160785.sophia-pbs-01.lab.alcf.anl.gov/summary.json`.

Next decision: build a mixed deterministic proof generator that applies
targeted splits only for modules whose broad leaf is known to need it, then
target `AtomicRegister` with a `ReadImpose` winner/max-tag lemma and
`IdempotencyKey` with explicit `ServedKeys` cardinality lemmas.

## 160798 All-Green Candidate

PBS `160798` (`tlaps_allgreen_v2`) completed with all 18 modules exiting 0:
raw `230/230` TLAPS obligations proved.

Artifact:
`outputs/autoprover/tlaps_allgreen_v2_t1_160798/summary.json`.

What changed beyond `160785`:

- `IdempotencyKey` is source-preserving and proves with explicit
  `FiniteSetTheorems` steps for `ServedKeys = {}`, `ServedKeys' =
  ServedKeys \cup {k}`, `FS_AddElement`, and the stutter branch.
- `AtomicRegister` proves after normalizing the nested `LET/CHOOSE`
  max-tag/winner expression into an explicit max-winner existential action.

Interpretation: this is the first all-green prover candidate. Treat it as
normalized `108/108` module coverage, but keep one promotion caveat:
`AtomicRegister` still needs either a source-preserving `CHOOSE` max/winner
lemma or a documented/proved semantic-equivalence pass for the explicit-winner
normalization.

Follow-up source-preserving AtomicRegister tests did not yet remove that
caveat:

- lifting the nested `LET` definitions to top-level `TagSet(Q)`, `MaxTag(Q)`,
  and `Winner(Q)` kept the same `CHOOSE` semantics but still failed at the
  `ReadImpose` inductive leaf;
- adding a first helper lemma, `Majority(Q) => Q # {}`, exposed a smaller
  TLAPS arithmetic blocker: proving `Cardinality(Nodes) = 3` for
  `Nodes == {"n1", "n2", "n3"}`.

Next no-asterisk path: add/prove small finite-cardinality lemmas for concrete
node sets, then prove `MaxTag(Q) \in TagSet(Q)` and `Winner(Q) \in Q`; or build
a checked equivalence harness between the original nested `LET/CHOOSE` action
and the explicit-winner normalized action.

## 160802 Final Source-Preserving Result

PBS `160802` (`tlaps_final_srcp2`) completed the no-asterisk proof sweep:
18/18 modules exited 0 and raw `299/299` TLAPS obligations proved.

Artifact:
`outputs/autoprover/tlaps_final_source_preserving_v2_t1_160802/summary.json`.

This supersedes `160798` because both previously special modules now preserve
their source semantics:

- `AtomicRegister` keeps the original `CHOOSE` max-tag/winner semantics and
  proves helper lemmas for `Nodes` cardinality, majority nonempty, finite-set
  maximum existence, `MaxTag(Q)`, and `Winner(Q)`.
- `IdempotencyKey` keeps the original action semantics and proves explicit
  finite-set/cardinality steps for `ServedKeys`.

Promotion interpretation: this is the verified no-asterisk normalized `108/108`
prover result.

## Final Reproduction Package

The final proof result is now reproducible from source proof artifacts with:

```bash
python3 scripts/reproduce_final_tlaps_prover.py \
  --tlapm "${CHATTLA_TLAPM:-tlapm}" \
  --out-dir outputs/autoprover/tlaps_reproduced_final_${JOBNUM} \
  --package outputs/autoprover/tlaps_reproduced_final_${JOBNUM}.tar.gz \
  --threads 1 \
  --timeout 900 \
  --expected-modules 18
```

The command copies the `160785` mixed-targeted proof base, overwrites
`AtomicRegister.tla` and `IdempotencyKey.tla` with the final source-preserving
repairs, reruns TLAPS, writes raw logs plus `summary.json`, and can produce a
tarball. Regression coverage lives in
`tests/test_reproduce_final_tlaps_prover.py`.

Reproduction job `160816` passed on Sophia:

- `modules`: 18
- `exit_0`: 18
- `exit_nonzero`: 0
- `raw_proved`: 299
- `raw_total`: 299
- `all_modules_exit_0`: true
- `no_asterisk`: true

Durable staged artifact: set `CHATTLA_ARTIFACT_ROOT` when running
`scripts/qsub_reproduce_final_tlaps_prover.pbs`; the job writes
`$CHATTLA_ARTIFACT_ROOT/prover_final_108_108_repro_${JOBNUM}/`.

Public Hugging Face dataset:
`https://huggingface.co/datasets/<HF_NAMESPACE>/chattla-tla-prover-108-108`.
For local runs, set `CHATTLA_HF_NAMESPACE` (or `CHATTLA_HF_PROVER_DATASET`) for your namespace.
Upload commit: `c44a97f83370400781e63697dcac6cd2e11920f9`.

Key checksums:

- `tlaps_reproduced_final_160816.tar.gz`:
  `20ca68ea4caf304b42d5b45fbaeadefc55eb0a17fd1fd9991db27ed741a5d46c`
- `reproduce_final_tlaps_prover.py`:
  `872fd29967728325d766070a09b1166594bf39ec27ccc6b7b278c030fdf5efd6`
- `summary.json`:
  `f7ef4dd131b17dd14d0c691bef0c43c1c2e81c23b02308fcf5f987d30c78af93`

Harness lesson: the failed first reproduction job `160815` passed repo-relative
proof paths while also setting `cwd` to the proof directory, causing immediate
TLAPS `File not found` errors. The reproducer now resolves module paths before
invoking `tlapm`.

## First Smoke Baseline

Run a small autoprover smoke on 10-20 safety/invariance tasks.

Prerequisites:

- install or bundle TLAPS so `src/shared/tlaps/bin/tlapm` exists or expose a
  configurable `CHATTLA_TLAPM` path;
- keep all model calls cloud/remote; do not run local Ollama on the MacBook;
- optionally install Apalache after the TLAPS smoke is passing.

Dataset:

- start with tiny internal tests and simple FormaLLM safety theorems;
- include only modules with finite domains, `Init`, `Next`, `vars`, and a
  clear invariant-style theorem;
- exclude liveness theorems in the first pass.

Command shape:

```bash
python -m scripts.autoprover_smoke \
  --limit 20 \
  --theorem-kind safety \
  --max-cegis-iters 3 \
  --tlapm-timeout 60 \
  --out outputs/autoprover/smoke_YYYYMMDD.jsonl
```

This script does not exist yet. The fastest implementation is a wrapper around
`src.prover.cegis.prove_safety`, `src.validators.tlaps_validator`, and the
existing proposer abstraction.

## Success Gates

For the first smoke:

- toolchain works on at least one machine with `tlapm --help` and one known
  TLAPS example;
- 20/20 tasks produce structured JSONL traces;
- at least 50% of supported safety tasks find an inductive invariant or report
  a useful CTI-backed failure;
- at least 20% produce a TLAPS skeleton that parses;
- at least one task proves at least one nonzero TLAPS obligation.

For promotion to a larger run:

- no local GPU/Ollama dependency;
- resumable JSONL output;
- exact TLAPS stdout/stderr preserved;
- failures bucketed into parse, unsupported theorem, non-enumerable domain,
  no inductive invariant, TLAPS leaf failure, timeout.

## Abort Gates

Stop and revise if:

- TLAPS cannot be installed reliably on Sophia or the launch host;
- generated proofs still contain analysis prose after direct-output prompting;
- most failures are non-enumerable constants/domains rather than proof logic;
- CTI-to-invariant proposals repeat or make invalid predicates;
- no task proves any obligation after the first 20-task smoke.

## Implementation Notes

- Add `CHATTLA_TLAPM` support to `tlaps_validator.py`; hard-coding
  `src/shared/tlaps/bin/tlapm` makes the current local checkout unusable.
- Some login nodes do not expose `java`, but compute nodes may provide it
  (`/bin/java` was observed in the original PBS smoke), so TLC-backed
  prover smoke runs should go through PBS instead of the login shell.
- Preserve source priority when discovering smoke inputs: generated
  `outputs/diamond_gen/*_work/*.tla` modules should run before broad FormaLLM
  data. The first Sophia smoke (`160680`) accidentally sorted absolute paths and
  spent the sample budget on lexicographically early FormaLLM modules with parse
  errors.
- As of the PBS smoke, `tlapm` and `apalache-mc` are still absent from Sophia
  PATH. TLC is available on compute; TLAPS packaging remains the next toolchain
  blocker before real proof validation.
- Corrected Diamond-first PBS loop `160682` found 9/80 generated modules whose
  `TypeOK` was TLC-inductive, 1 genuine non-inductive case, and 70 TLC setup or
  data errors. The dominant fix is harness quality: synthesize small-model
  `CONSTANT` cfg assignments and skip non-enumerable/helper-dependent `TypeOK`
  forms before spending model budget.
- `src/prover/inductiveness.py` now emits small-model `CONSTANT` assignments
  using the repo's existing TLC config inference helpers; focused prover tests
  passed locally after this change. Sophia loop `160683` is the follow-up
  measurement.
- Sophia loop `160683` reduced TLC errors from 70/80 to 15/80 on the same
  Diamond prefix by turning unsuitable cases into explicit skips. It did not
  increase inductive candidates in that prefix: still 9 `TypeOK` skeleton
  candidates, 1 genuine non-inductive case. Next experiment should inventory
  the full Diamond set and then package TLAPS; more GRPO is premature until
  `tlapm` can validate emitted proof modules.
- Full Diamond inventory `160684` found 18 TLC-inductive skeleton candidates
  out of 200 generated modules. TLAPS 1.5.0 was installed on the remote host
  and exposed via `CHATTLA_TLAPM`; `tlapm --config` saw Z3, Zenon, Isabelle,
  and LS4, and the bundled Euclid example checked.
- TLAPS validation (`160685`) converts the milestone from "can we run TLAPS?"
  to "can we repair proof leaves?": 18 TLC-inductive candidates yielded
  17 partial proofs and 1 timeout/unproved case, with 123/170 obligations
  proved by the deterministic skeleton. The next model loop should consume
  exact failed obligations and propose small leaf/decomposition repairs.
- Run TLAPS 1.5.0 with `--threads 1` for this workload. The default scheduler
  can abort in `schedule.ml` even on modules that previously proved; `--cleanfp`
  and `--nofp` do not fix it, while `--threads 1` reproved `AtomicCommit` from
  a clean cache. Long-running jobs should preserve raw output and record the
  exact `tlapm` flags used.
- Add a no-local-Ollama mode to `scripts/overnight_cegis.py` or write a new
  `scripts/autoprover_smoke.py` that requires an explicit cloud chat function.
- Keep `test_inductiveness.py` and `test_cegis.py` as the regression base.
- Treat liveness as phase 2. TLAPS docs explicitly frame the current release as
  suitable for safety properties, while liveness needs specialized reasoning.
- Build a retrieval index from verified TLAPS snippets before doing more prover
  SFT. The existing prover diagnosis shows direct generation is not reliable
  enough.

## Source Links

- TLAPS repository: https://github.com/tlaplus/tlapm
- TLAPS docs: https://proofs.tlapl.us/doc/web/content/Home.html
- TLAPS tactics: https://proofs.tlapl.us/doc/web/content/Documentation/Tutorial/Tactics.html
- Apalache site: https://apalache-mc.org/
- Apalache repository: https://github.com/apalache-mc/apalache
- RAG TLAPS proof generation paper: https://arxiv.org/html/2501.03073v1

## 2026-06-26 Control-Plane Handoff

The overnight control plane is relay-host agnostic. Configure it with
`CHATTLA_RELAY_HOST`, `CHATTLA_RELAY_KEY`, `CHATTLA_RELAY_REPO`,
`SOPHIA_HOST`, `SOPHIA_CTL`, and `CHATTLA_REMOTE_REPO`; a Mac mini, login node,
or any SSH-reachable machine can fill the relay role.

Current action:

- poll Sophia job `160846`, the corrected all-dataset TLAPS-running smoke;
- summarize `outputs/autoprover/full_dataset_smoke_160846.jsonl` when complete;
- use the result distribution to choose the next bounded loop: SANY/TLC repair
  data, TLAPS leaf repair data, harness eligibility patches, or another safe
  Sophia run.

Dataset state:

- `<HF_NAMESPACE>/chattla-tla-prover-108-108` viewer is fixed: root metadata JSON
  files moved under `metadata/`, `data/train.jsonl` is the declared split, and
  the dataset server now returns 18 stable rows.
- `scripts/build_verified_tlaps_sft.py` builds the verified TLAPS SFT seed from
  the final `160816` proof tarball.

Do not promote or publish a new model artifact until fresh eval evidence beats
or matches the base without syntax/module regressions.

## 2026-06-27 Artifact Readout

`160846` completed successfully as an all-dataset smoke, but it is not proof
training data yet:

- 610 rows scanned;
- 471 skipped;
- 95 `tlc_error`;
- 17 `not_inductive`;
- 25 `tlaps_unproved`;
- 2 `tlaps_parse_error`;
- 0 proved or partial TLAPS rows.

The useful conclusion is a harness fix, not a model conclusion. The smoke
runner was generating malformed proof-checking inputs for TLAPS: injected proof
modules did not always `EXTEND TLAPS`, and temporary validation filenames did
not match the original module header. `scripts/autoprover_smoke.py` now has
regression coverage for both cases.

New trainable artifacts:

- `data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl`
  contains 18 structured verified proof traces from the all-green `160816`
  archive, raw 299/299 TLAPS obligations, checksum
  `5444bd7da9a1946380877202f48658376df0c8e77bbf5328b9547c9eecb78e35`.
- The generated local prover SFT file
  `data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl` contains 1330
  SFT rows: `diamond_sft_v3`, the full `205`-row `formalllm_eval_v1`, plus 4x
  oversampled verified TLAPS proof rows, normalized to
  `developer`/`user`/assistant-channel message format, checksum
  `3b4350956d94d214f1e1d8c2225bc7ecbcdf438b8cb1d23ac9f75464ccfb446e`.
- The committed public copy of that same corpus lives at
  `outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl`.
- `data/processed/prover_eval.jsonl` contains 18 TLAPS-callback-compatible
  prover eval rows derived from the verified proof traces, 299/299 gold TLAPS
  obligations, checksum
  `2a0e846e5ff7cfd1c4fae282a9ae1a64e8b3f677dac27fe32379dd839c710357`.
- `data/processed/sany_tlc_pass_sft_v1.jsonl` contains 170 verified
  SANY/TLC-pass rows from `outputs/diamond_gen/diamond_generated.jsonl`, with
  the 30-module holdout excluded. The builder now appends deterministic inline
  TLC config plus inferred `CONSTANT` assignments; checksum
  `c72006c0ac5933cfdaee82c15b456dd58f18d8af70cd6f3c82950f7abe14af51`.
- `data/processed/sany_tlc_pass_eval_v1.jsonl` contains the 30-module held-out
  SANY/TLC-pass eval split from `data/processed/diamond_eval_holdout.jsonl`,
  with the same deterministic config/constant policy, checksum
  `6c0da974d2abb6582a3a2648d0f9eb15c3eb98da9bd0692f73204e4e53f1dd8d`.
- `scripts/evaluate_sany_tlc_eval_corpus.py` is the standalone held-out replay
  gate. The latest full replay checked all 30 rows: 30 reached TLC gold and
  29 reached the stricter Diamond gate.

`src.training.train` now accepts `--eval-file`, so future SANY/TLC passer runs
can evaluate against `data/processed/sany_tlc_pass_eval_v1.jsonl` instead of
the generic eval set, while the prover preflight explicitly uses
`data/processed/prover_eval.jsonl`.

Next bounded remote action, once the Mac mini or Sophia route is reachable
again: rerun a small corrected smoke on the known 18 candidate modules before
repeating the full 610-row scan. Treat only `tlaps_proved` / `tlaps_partial`
with preserved raw logs as model-training evidence.

The bounded rerun is now staged:

- exact module list:
  `data/processed/tla_prover/tlaps_candidate_modules_18.txt`;
- PBS wrapper:
  `scripts/qsub_autoprover_known18_corrected_smoke.pbs`;
- local dry check:
  `python3 scripts/autoprover_smoke.py --module-list data/processed/tla_prover/tlaps_candidate_modules_18.txt --limit 2 --skip-tlaps ...`
  emitted `2 skeleton_emitted`.

Launch command on Sophia after syncing:

```bash
cd ~/ChatTLA
qsub scripts/qsub_autoprover_known18_corrected_smoke.pbs
```

Preferred one-command handoff from the MacBook when direct Sophia login is
available:

```bash
CHATTLA_REMOTE_HOST=user@remote-login \
scripts/sync_sophia_and_submit_known18.sh
```

This is the primary lane when the relay path is paused and a direct remote
checkout is reachable from the current workstation. Authenticate using the
standard SSH flow for your environment, then use
`scripts/sync_sophia_and_submit_known18.sh --submit-sft-preflight`,
`--submit-final-proof-verify`, or `--submit-full-dataset-smoke` for the
bounded remote variants.

Legacy relay handoff from the MacBook, once the Mac mini route is reachable:

```bash
scripts/sync_macmini_and_submit_known18.sh
```

This syncs the corrected smoke runner, repo `src/`, known-18 list plus the
referenced `.tla` modules, dataset artifacts, manifest, and Mac mini keepalive
scripts to the mini, then uses the mini's Sophia control socket to sync into
`~/ChatTLA` and submit the known-18 PBS job.
Use `scripts/sync_macmini_and_submit_known18.sh --submit-sft-preflight` when
we want the same handoff to also submit the bounded 3-step SFT startup
preflight; that mode additionally syncs `configs/` and uses
`data/processed/prover_eval.jsonl` for the TLAPS eval callback.
After syncing, the handoff now delegates to a Sophia-side submit/report script:

```bash
scripts/submit_tla_prover_remote_jobs.sh --submit-sft-preflight
```

That script runs the preflight, submits the corrected known-18 smoke, optionally
submits the bounded SFT startup preflight, and writes
`outputs/manifests/tla_prover_remote_submission.json` with the captured PBS job
IDs. It writes the same JSON report on preflight or `qsub` failure with
`ok=false`, the failing stage, exit code, and recent stage log output.

Before any `qsub`, the submit script runs a Sophia-side guard:

```bash
CHATTLA_TLAPM=/path/to/tlapm \
  python3 scripts/preflight_tla_prover_remote.py --require-tools \
    --tlapm "$CHATTLA_TLAPM"
```

With `--submit-sft-preflight`, that guard also checks SFT Python imports and
the configured `CHATTLA_BASE_MODEL` before taking a GPU allocation.

If the relay is offline, use the local wait wrapper instead of polling
manually:

```bash
CHATTLA_RELAY_HOST=user@relay.example \
CHATTLA_MACMINI_WAIT_SLEEP=60 \
scripts/wait_for_macmini_and_handoff_known18.sh --submit-sft-preflight
```

The transport layer accepts neutral relay variables:

```bash
CHATTLA_RELAY_HOST=user@relay.example \
CHATTLA_RELAY_KEY=/path/to/key \
CHATTLA_RELAY_REPO=/path/to/ChatTLA \
CHATTLA_RELAY_LABEL="remote relay" \
SOPHIA_HOST=sophia \
SOPHIA_CTL=/path/to/control-socket \
CHATTLA_REMOTE_REPO=ChatTLA \
CHATTLA_TLAPM=/path/to/tlapm \
CHATTLA_PBS_ACCOUNT=<allocation> \
scripts/wait_for_macmini_and_handoff_known18.sh --submit-sft-preflight
```

The sync and collector scripts honor the same `CHATTLA_RELAY_*` variables.

It probes relay SSH with BatchMode auth, logs to
`outputs/logs/wait_for_macmini_handoff.log`, and runs the handoff exactly once
after the first successful probe. After the remote submit step, it attempts to
mirror `outputs/manifests/tla_prover_remote_submission.json` back to the laptop
through the relay so job IDs or failure stage are visible locally. If that
mirror step fails after a successful submit, the wrapper exits nonzero instead
of silently treating the handoff as complete, and writes
`outputs/manifests/tla_prover_remote_submission_mirror_failed.json`.

To recover that state without risking duplicate known-18 submission, run:

```bash
scripts/wait_for_macmini_and_handoff_known18.sh --mirror-report-only
```

The doctor LaunchAgent uses that same mirror-only path for
`submission_mirror_failed`.

If the relay is intentionally unavailable, pause the remote handoff by writing
`outputs/manifests/tla_prover_handoff_paused.json`. While this file exists,
`status_tla_prover_handoff.py` reports `handoff_paused` and the doctor noops
instead of reinstalling the wait hook. Keep that sentinel local; it is operator
state and should not be committed.

Probe available control planes from the laptop with:

```bash
python3 scripts/probe_tla_prover_control_planes.py
```

It writes `outputs/manifests/tla_prover_control_plane_probe.json` and checks
only the configured `CHATTLA_RELAY_HOST`, `SOPHIA_HOST`,
`CHATTLA_POLARIS_HOST`, `CHATTLA_AISEC_HOST`, or explicit `--candidate`
entries using BatchMode SSH.

For OS-owned waiting on the laptop, install the one-shot LaunchAgent:

```bash
scripts/install_wait_handoff_launchagent.sh --mac-host user@relay.example
```

Use `--mac-host` for a one-off relay target, or set `CHATTLA_RELAY_HOST` /
`CHATTLA_MAC_HOST` in the LaunchAgent environment. The LaunchAgent waits until
SSH succeeds, then executes the guarded handoff once.

Install the periodic local repair loop as well:

```bash
scripts/install_handoff_doctor_launchagent.sh --interval 300
```

`com.chattla.handoff-doctor` runs every five minutes. It leaves a healthy wait
hook alone, reinstalls/kickstarts the wait hook if it exits before submission,
starts the result watcher after submission, and stops for manual review only on
a hard remote-submit failure with no known-18 job ID.

After `outputs/manifests/tla_prover_remote_submission.json` exists, collect
job evidence with:

```bash
scripts/collect_tla_prover_remote_results.sh
```

The collector mirrors only decision evidence: submission report, qstat snapshot,
remote preflight/qsub logs, known-18 PBS logs, known-18 JSONL/summary keyed by
PBS job number, and the SFT preflight log keyed by PBS job number. It writes
`outputs/manifests/tla_prover_remote_results_collection.json`; missing result
files are recorded as `missing` while queued/running jobs settle, and transport
failures become `ok=false` with an error entry.

The wait hook now starts:

```bash
scripts/watch_tla_prover_remote_results.sh
```

after it mirrors the submission report. The watcher reruns the collector until
`known18_corrected_smoke_${JOBNUM}.summary.json` is mirrored, and until
`sft_preflight_${JOBNUM}.log` is mirrored when an SFT preflight job was
submitted. It writes `outputs/manifests/tla_prover_remote_watch.json`. If the
collector returns nonzero only because side evidence such as `qstat` failed, the
watcher still checks whether required known-18/SFT evidence is present and can
complete the decision report.

On completion, the watcher also runs:

```bash
python3 scripts/evaluate_tla_prover_remote_results.py
```

That writes `outputs/manifests/tla_prover_remote_decision.json`. The current
gate is deliberately conservative: advance only when all 18 known modules reach
`tlaps_proved` or `tlaps_partial`, with no parser/TLC/inductiveness/unknown
status regressions. Otherwise, do not launch SFT; patch the prover harness or
data and rerun the bounded known-18 smoke.

If the remote submit report is `ok=false` after known-18 already launched
(for example SFT preflight qsub failed), status reports
`partial_submit_waiting_for_results` and the doctor still runs the watcher to
collect known-18 evidence.

For a single current-state readout, run:

```bash
python3 scripts/status_tla_prover_handoff.py --live
python3 scripts/status_tla_prover_handoff.py --no-live --compact
```

It summarizes LaunchAgent state, Mac mini Tailscale state, local submission /
collection / watch / decision reports, job IDs, recent wait-log lines, the
periodic doctor LaunchAgent state, and the next action.

For a next-action / repair decision, run:

```bash
python3 scripts/doctor_tla_prover_handoff.py --dry-run --live
python3 scripts/doctor_tla_prover_handoff.py --dry-run --no-live --compact
```

It decides whether to leave the wait hook alone, reinstall/kickstart the wait
LaunchAgent, run the result watcher, or stop for manual review of a failed
remote submission.

Before publishing PR updates, run:

```bash
python3 scripts/check_tla_prover_pr_ready.py
```

The readiness gate scans tracked PR files for private hosts, site-specific
paths, fixed PBS accounts, hard-coded compute nodes, and then runs the focused
prover handoff test suite. Keep machine names, queue/account choices, filesystem
mounts, and GPU masks behind `CHATTLA_*`, `SOPHIA_*`, or PBS submit-time
environment variables.

SFT startup preflight is also staged:

```bash
cd ~/ChatTLA
qsub scripts/qsub_sophia_tla_prover_sft_preflight.pbs
```

That wrapper runs only `--max-steps 3` on
`data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl` against the cached
`EricSpencer00/chattla-20b` snapshot, with `--prover` enabled so
`data/processed/prover_eval.jsonl` drives the TLAPS eval callback. Treat it as
a data/VRAM/startup/TLAPS-eval preflight, not as model-quality evidence.

Local corpus schema preflight now passes before remote handoff:

```bash
python3 scripts/preflight_tla_prover_corpora.py
```

Reports: `outputs/manifests/tla_prover_corpus_preflight.json` and
`outputs/manifests/sany_tlc_pass_corpus_diagnostic.json`; they currently check
1330 mixed-prover SFT rows, 18 prover-eval rows, 170 SANY/TLC-pass train rows,
and 30 held-out SANY/TLC eval rows with no schema or diagnostic errors. The
remote sync script regenerates the prover eval, SANY/TLC eval, both reports,
and the manifest before relay handoff.

The SANY/TLC-pass corpus now has a stricter local diagnostic:

```bash
python3 scripts/diagnose_sany_tlc_pass_corpus.py
```

It writes `outputs/manifests/sany_tlc_pass_corpus_diagnostic.json` and checks
for duplicate modules, holdout overlap, module/header mismatch, missing
assistant finals, missing `SPECIFICATION Spec` config blocks, weak Diamond/TLC
evidence, and summary checksum drift. This caught and fixed a real stale
artifact issue: most checked-in SANY/TLC-pass targets lacked the config block
promised by the prompt. `scripts/build_sany_tlc_pass_corpus.py` now appends a
deterministic inline config, including `INVARIANT TypeOK` when `TypeOK ==` is
defined.

Queue-waste guard added after audit: dry-run coverage now asserts that every
path in `tlaps_candidate_modules_18.txt` is synced and that SFT preflight
runtime dependencies are present when `--submit-sft-preflight` is used.
Additional guard coverage checks the wait wrapper retry behavior and the
remote preflight's required-file/tool failure paths.

Automation hardening staged for the Mac mini:

- `macmini_codex_goal_supervisor.sh` now uses `$HOME` defaults, preflight
  checks, PID/status files, prompt hashing, and capped logs.
- `macmini_tla_prover_autopilot.sh` now uses `$HOME` and `SOPHIA_CTL` defaults
  with status/log rotation.
- `install_macmini_launchagents.sh` writes two user LaunchAgents with
  `RunAtLoad` and `KeepAlive` so the loops can survive shell/session loss once
  installed on the mini.

The normal handoff keeps Mac mini LaunchAgent installation as a dry-run safety
check. To explicitly install persistent Mac mini Codex/autopilot LaunchAgents
as part of a handoff, use:

```bash
scripts/sync_macmini_and_submit_known18.sh --install-launchagents
```

This is opt-in because the Mac mini agents are persistent and can launch
`codex exec` from the synced prompt file.
