# ChatTLA Run Memory

Current operational facts for the long-Ralph training push:

- `ssh plantain` works and lands on `plantain.cs.luc.edu` as user `espencer2`.
- `ssh polaris` works and lands on `polaris-login-01` as user `eric-spencer`.
- `the configured cloud host` is now the default cloud-only launch host and artifact store target for long runs.
- The ChatTLA repo is present on plantain at `~/ChatTLA`.
- The long-run launcher exists in the repo at `scripts/launch_long_ralph_training.sh`.
- The long-run policy module exists at `src/rlvr_canary/long_ralph_policy.py`.
- The long-run collector exists at `scripts/collect_long_ralph_trajectories.py`.
- The repair-GRPO script now defaults back to `EricSpencer00/chattla-20b` when no merged local model is set.
- The long-Ralph success gate is now SANY/TLC + diamond + final Ollama Cloud adequacy judge.
- Long Ralph should be treated as a search-and-collection engine, not a convergent optimizer; the target is judge-verified specs plus rich repair traces, not “keep one prompt alive forever.”
- The Ralph loop now treats adequacy/TLC/SANY failures as repair feedback, not stop conditions, but it must advance once the acceptance frontier is flat.
- `CHATTLA_MAX_ITERS=0` means no per-prompt iteration cap; the loop stops on verified success or repeated malformed output.
- TLC auto-generated configs now add `PROPERTY ...` entries for declared temporal/liveness operators, so liveness claims are checked by TLC instead of relying only on the final judge.
- The temporal-property extractor must not treat tuple/sequence delimiters like `<<>>` or `<<x, y>>` as the temporal diamond `<>`; this was fixed after a live run accidentally generated `PROPERTY P`.
- Long Ralph now records `properties_declared`, `properties_checked`, `property_names`, `failure_family`, `last_failure_family`, `semantic_stall_count`, and `frontier_stall_count` in run artifacts.
- Collector `score` is now an objective-shaped score for search/training-pair selection, not raw TLC partial credit. Raw validator score is preserved as `raw_score`, and judge-rejected adequacy specs are capped below true success so “gold but wrong” does not look terminally solved.
- Long Ralph has semantic-stall advancement enabled by default: after `CHATTLA_MAX_SAME_FAILURE_FAMILY_ITERS=24` repeated adequacy failures in the same family, the prompt records `stop_reason=semantic_stall` and advances without marking success.
- Long Ralph also has frontier-stall advancement enabled by default: after `CHATTLA_MAX_FRONTIER_STALL_ITERS=96` recorded attempts without improving the acceptance frontier, the prompt records `stop_reason=frontier_stall` and advances without marking success.
- Long Ralph now uses bounded parallel fanout by default when the frontier is flat: after `CHATTLA_BRANCH_AFTER_ITERS=20` non-improving attempts, it launches `CHATTLA_BRANCH_WIDTH=5` focused branches with `CHATTLA_BRANCH_ITERS=8` repairs per branch, records every branch as training data, and continues from the best branch.
- Parallel branch focuses are selected from failure families, e.g. property/liveness failures prioritize liveness, cfg checkability, queue modeling, simplification, and ownership, while false-assumption failures prioritize concretizing domains instead of preserving `CONSTANTS` + `ASSUME`. Branch repair pairs include branch metadata so later fine-tuning can filter or weight them.
- Adequacy failure-family classification prioritizes explicit judge reasons such as bad ownership and weak fairness before falling back to zero action coverage, because TLC coverage can be absent even for otherwise meaningful gold specs.
- The launcher writes each run's live cluster report to `run_report.json`; `scripts/summarize_long_ralph_run.py` can summarize `step_events.jsonl` by phase, failure family, and compact reason.
- Judge-accepted terminal specs are saved as `.tla` files under each run's `accepted_specs/` directory, with JSON metadata beside them for later fine-tuning data construction.
- Per-iteration artifacts are streamed during collection to `step_events.jsonl` and `repair_pairs_live.jsonl`, so a long-running prompt still leaves usable repair traces.
- Current GRPO repair reward still uses `component_validator.reward_from_spec` at training time, so online RL reward remains a proxy for verified correctness; the fully verified objective is enforced in long-Ralph collection and in the accepted-spec corpus.
- Property freezing is disabled by default for long Ralph collection because guessed variable names can push the model toward thin schemas; set `CHATTLA_FREEZE_PROPERTIES=1` to re-enable it.
- If property freezing is enabled, it is filtered to state-level predicates only; temporal wrappers like `[]`, `<>`, `WF_`, and primed variables are rejected so frozen context can be used as invariant-style guidance.
- SANY/TLC diagnostics now preserve raw validator output in the repair context instead of only terse parsed labels like `***Parse Error***`.
- Long raw TLC diagnostics now preserve the primary error header plus the tail, instead of truncating from the front and starting repair context mid-warning.
- Repeated unchanged specs or repeated parser failures trigger `STUCK SYNTAX REWRITE MODE` in the repair prompt, with line-numbered excerpts around SANY-reported line numbers.
- IF/THEN parser failures now add a syntax hint telling the teacher to use guarded disjunctive TLA+ actions instead of incomplete `IF condition THEN /\ update` blocks.
- Fairness/liveness failures now add exact TLA+ fairness syntax guidance: use `WF_vars(ActionName)` or `WF_vars(Next)`, not invented operators like `WF_ActionName`.
- Diamond failures with `distinct_states <= 1` or zero action coverage now explicitly tell the teacher to add real state-changing actions and avoid stutter-only models.
- TLC assumption failures now tell the teacher to replace `CONSTANTS` + `ASSUME` with concrete finite operators like `Proc == 1..3`.
- Repair prompts now include compact domain recipes for semaphores, locks, and queues so the teacher does not need to infer the modeling scaffold from scratch.
- SANY precedence conflicts now trigger block-structured action guidance, and unknown `Cardinality` errors now tell the teacher to add `EXTENDS FiniteSets` or use quantified invariants.
- Sequence `Range(waiters)` misuse now triggers a direct sequence-membership hint, and action assignment-conflict hints are scoped per disjunctive branch to avoid false warnings across valid branches.
- Adequacy rejections mentioning vacuous or over-strong safety now tell the teacher to preserve realistic contention/release/wakeup behavior instead of making invariants true by construction.
- A previous plantain run was stopped because it could mark `tier=gold score=1.000 success=True` without the final judge.
- Plantain has Java at `~/.local/opt/jdk-17.0.13+11/bin/java`; the launcher now prepends that JDK to `PATH` when the GPU retrain phase is used.

Required cloud-only launch config:

- `~/.config/chattla/ollama.env` must contain `export OLLAMA_API_KEY=...` on the launch host.
- `CHATTLA_CLOUD_ONLY=1`, `CHATTLA_SKIP_GRPO=1`, `CHATTLA_INITIAL_PROVIDER=teacher`, `CHATTLA_REPAIR_PROVIDER=teacher`, and `CHATTLA_LOCAL_MODEL_AUDIT=0` keep long Ralph off local GPU generation on `the configured cloud host`.

Canonical launch sequence on `the configured cloud host`:

```bash
cd ~/ChatTLA
export CHATTLA_CLOUD_ONLY=1
export CHATTLA_SKIP_GRPO=1
export CHATTLA_INITIAL_PROVIDER=teacher
export CHATTLA_REPAIR_PROVIDER=teacher
export CHATTLA_LOCAL_MODEL_AUDIT=0
scripts/launch_long_ralph_training.sh start
tmux attach -t chattla-long-ralph
```

Useful environment overrides:

```bash
export CHATTLA_AISEC_STORE=the configured cloud host:~/chattla-long-runs
export CHATTLA_MAX_PROMPTS=120
export CHATTLA_MAX_ITERS=0
export CHATTLA_MAX_SAME_FAILURE_FAMILY_ITERS=24
export CHATTLA_MAX_FRONTIER_STALL_ITERS=96
export CHATTLA_BRANCH_AFTER_ITERS=20
export CHATTLA_BRANCH_WIDTH=5
export CHATTLA_BRANCH_ITERS=8
export CHATTLA_BASE_MODEL=EricSpencer00/chattla-20b
export OLLAMA_CLOUD_MODEL=qwen3-coder:480b
```

Verification already completed locally:

- `python3 -m pytest test -q` passed with `50 passed, 4 skipped`.
- `python3 -m py_compile` succeeded for `src/validators/tlc_validator.py`, `scripts/collect_long_ralph_trajectories.py`, and `scripts/summarize_long_ralph_run.py`.
- `bash -n scripts/launch_long_ralph_training.sh` succeeded.
- `python3 -m scripts.collect_long_ralph_trajectories --dry-run --max-prompts 1` should print `final_judge=true`, `freeze_properties=false`, `semantic_stall_stop=true`, `max_same_failure_family_iters=24`, `max_frontier_stall_iters=96`, and `max_iters=0`.

Current full-spec GRPO plan forward:

- The direct-start contract and `reasoning_effort=none` path fixed the opening shape, and warm-start `160408` stayed on-contract.
- Holdout `160417` did **not** beat the exact-prompt base, so the current branch should not be promoted.
- Next run, if we launch one, should be a smaller bounded diagnostic rather than another broad 30-step phase.
- The diagnostic should target the remaining syntax/helper-order failures directly, especially `typed_constants`, `typed_variables`, and `empty_unchanged`.
- Prefer early checkpoint selection over assuming later checkpoints will recover the holdout.
- Keep the promotion gate strict: only advance if holdout clears the base and sample logs stay clean.

Current TLA+ autoprover plan:

- Strategy doc: `docs/TLAPLUS_AUTOPROVER_STRATEGY.md`.
- Treat the autoprover as a verifier-guided pipeline around TLC/Apalache/TLAPS, not as raw whole-proof generation.
- Existing repo pillars are healthy: `src/prover/cegis.py`, `src/prover/skeleton.py`, `src/prover/proposer.py`, and selected prover tests pass.
- Current local blocker: `tlapm` and `apalache-mc` are not on PATH, and the expected bundled `src/shared/tlaps/bin/tlapm` is absent.
- First milestone should be a 10-20 task safety/invariance smoke that finds or repairs inductive invariants, emits deterministic TLAPS skeletons, validates with `tlapm`, and saves resumable JSONL traces.
- Do not run local Ollama on the MacBook; any model-assisted prover exploration should use cloud/remote calls or a remote machine.
- Added `scripts/autoprover_smoke.py` and `CHATTLA_TLAPM` support in `src/validators/tlaps_validator.py`.
- Local no-TLAPS smoke over 5 generated specs produced 2 `skeleton_emitted` and 3 `tlc_error`; the errors were non-enumerable/mis-scoped `TypeOK` identifiers, so the remote smoke should start from curated/verified modules rather than arbitrary generated specs.
- Sophia auth is active in an SSH session. Remote `src/prover` was restored from `origin/feat/v2-cegis-prover`, and `scripts/autoprover_smoke.py` compiles there.
- Sophia login nodes lack `java`, which makes TLC fail with `FileNotFoundError`; Sophia compute nodes expose `/bin/java`.
- PBS smoke `160680` ran on `a Sophia GPU node` and confirmed TLC can launch on compute, but `tlapm` and `apalache-mc` are still absent from PATH. It also showed the first sample budget was wasted on lexicographically early FormaLLM parse errors.
- `scripts/autoprover_smoke.py` now preserves input source priority, so `outputs/diamond_gen/*_work/*.tla` runs before broad FormaLLM data.
- Corrected Diamond-first loop `160682` produced `9 no_tlapm`, `1 not_inductive`, and `70 tlc_error` over 80 modules. The nine TLC-inductive modules were AtomicRegister, CircuitBreaker, HeartbeatFailureDetector, RetryWithBackoff, TokenRing, AtomicCommit, ByzantineQuorum, VotingMajority, and WitnessReplication.
- Loop `160682` failure buckets showed the next leverage point is verifier harnessing, not model training: many failures were unassigned constants (`K`, `Procs`, `MaxVal`, `Universe`, `Keys`) or `TypeOK` using helper predicates / non-enumerable set forms.
- `src/prover/inductiveness.py` now adds small-model `CONSTANT` assignments to the temporary TLC cfg using the existing `tlc_validator` constant inference helpers; focused prover tests passed locally (`17 passed`).
- Sophia remote files were recovered after a clipped tar paste, and a lean `scripts/autoprover_smoke.py` was recreated there with Diamond-first discovery and TypeOK eligibility skips.
- Loop `160683` (`autoprover_loop3`) completed on Sophia with `9 no_tlapm`, `1 not_inductive`, `15 tlc_error`, and `55 skipped` over the same 80 Diamond modules. The constant-aware harness reduced TLC errors from 70 to 15; it did not discover more inductive candidates in the first 80.
- Remaining loop `160683` TLC errors are mostly 12 "TLC produced no conclusive result" cases and 3 bare helper/channel identifier cases. Next useful scan is full Diamond inventory with the current harness, while TLAPS packaging remains the blocker for proof validation.
- Full Diamond inventory `160684` completed 200/200 on Sophia: `18 no_tlapm`, `17 not_inductive`, `28 tlc_error`, `137 skipped`. The 18 TLC-inductive skeleton candidates are AtomicRegister, CircuitBreaker, HeartbeatFailureDetector, RetryWithBackoff, TokenRing, AtomicCommit, ByzantineQuorum, VotingMajority, WitnessReplication, EventCount, SzymanskiMutex, ResourceLease, RoundRobinScheduler, SleepingBarber, DistributedLock, IdempotencyKey, LeaderLease, and TwoPhaseLockingDeadlock.
- Installed TLAPS 1.5.0 user-local on Sophia at `site-managed storage/tools/tlaps-1.5.0`. Installer self-test reported failure, but `tlapm --version`, `tlapm --config`, and bundled `Euclid.tla` proof smoke worked; Z3, Zenon, Isabelle, and LS4 are available.
- TLAPS validation job `160685` completed against the 18 TLC-inductive candidates: `17 tlaps_partial`, `1 tlaps_unproved` (TokenRing timeout). Aggregate TLAPS obligations: 123 proved / 170 total, 47 failed. Most partials prove 7/10 obligations; AtomicCommit, ByzantineQuorum, VotingMajority, and SzymanskiMutex prove 8/10. Next strategy should be proof-leaf repair / decomposition, not whole-proof generation or another GRPO phase.
- Artifact job `160688` saved generated proof modules but its raw TLAPS command used a bad relative path, so all raw captures were immediate `exit_3` file-not-found. Fixed follow-up job `160689` completed and wrote proof modules plus full `tlapm` stdout/stderr under `outputs/autoprover/tlaps_repair_160689/` for all 18 candidates.
- Raw TLAPS artifacts show the deterministic skeleton fails at the inductive-step leaves; e.g. AtomicCommit failed 2/10 obligations with unexpanded symbols around `ACTION_DecideCommit_`, `ACTION_CastVote_`, `ACTION_Reset_`, and `CONSTANT_Participants_`.
- Action-split experiment `160702` was stopped because the first modules were worse than baseline: AtomicRegister failed 6/14 versus baseline 3/10, CircuitBreaker failed 4/12 versus baseline 3/10, and HeartbeatFailureDetector failed 7/16 versus baseline 3/10.
- Expanded-definition experiment `160703` was stopped because it included indented LET-local names such as `winner` in `BY DEF`, causing TLAPS parse/elaboration errors.
- Corrected top-level-only definition experiment `160704` completed and is the current best deterministic TLAPS result: 18 candidates, 4 fully proved (`AtomicCommit`, `ByzantineQuorum`, `VotingMajority`, `SzymanskiMutex`), and failed proof leaves reduced from baseline `160685`'s 47 to 23. Artifacts: `outputs/autoprover/tlaps_top_defs_160704/`, log `outputs/logs/tlaps_top_defs_160704.log`.
- The remaining `160704` failures are concentrated in `Init => TypeOK` leaves and a smaller set of inductive-step leaves. Follow-up PBS jobs `160705` (`tlaps_top_defs_both`), `160706` (`tlaps_init_safe_defs`), and cache-isolated `160709` are invalid as strategy evidence: all returned `exit_3` quickly with a TLAPS `schedule.ml` assertion failure, including modules that `160704` had already proved.
- The TLAPS runner must use `--threads 1`; `--cleanfp` and `--nofp` alone do not avoid the `schedule.ml` assertion, while `tlapm --threads 1` successfully reproved `AtomicCommit` from a clean cache.
- PBS job `160710` (`tlaps_init_variants_t1`) completed and is the new best deterministic TLAPS result. Both `init_all_defs` and `init_safe_defs` tied: 18 candidates, 9 fully proved, 9 partial, 92/108 obligations proved, 16 failed leaves. Fully proved modules: RetryWithBackoff, TokenRing, AtomicCommit, ByzantineQuorum, VotingMajority, WitnessReplication, EventCount, SzymanskiMutex, ResourceLease. Remaining: AtomicRegister:1, CircuitBreaker:2, HeartbeatFailureDetector:1, RoundRobinScheduler:2, SleepingBarber:2, DistributedLock:2, IdempotencyKey:2, LeaderLease:2, TwoPhaseLockingDeadlock:2. Artifacts: `outputs/autoprover/tlaps_init_variants_t1_160710/`, log `outputs/logs/tlaps_init_variants_t1_160710.log`.
- Method sweep on representatives (`--method smt`, `z3`, `auto`, `force`, `blast`) did not improve RoundRobinScheduler, AtomicRegister, or CircuitBreaker; some methods made AtomicRegister worse. A representative constant-assumption insertion for DistributedLock also stayed at 2/6 failed. Next useful loop is targeted proof decomposition/helper lemmas for the remaining failed obligations, not broad backend switching or raw whole-proof generation.

Concise significant autoprover findings:
- `tlapm --threads 1` is mandatory on Sophia for this workload; default TLAPS scheduling can falsely crash valid proofs.
- Deterministic proof shaping is paying off: failed leaves improved `47 -> 23 -> 16` without model-generated whole proofs.
- Promote `init_safe_defs` as the default skeleton; `init_all_defs` tied but is noisier.
- New significant finding: TLAPS obligations for symbolic modules may omit useful top-level `ASSUME` facts. Explicitly rewriting `THEOREM ... == ASSUME N \in 1..5 PROVE ...` made `RoundRobinScheduler` go from 2 failed leaves to fully proved.
- PBS job `160748` (`tlaps_theorem_assumes_t1`) completed and is the new best deterministic TLAPS result: 18 candidates, 11 fully proved, 7 partial, 96/108 obligations proved, 12 failed leaves. Assumption lifting fully proved `RoundRobinScheduler` and `SleepingBarber` on top of the `160710` baseline. Remaining: AtomicRegister:1, CircuitBreaker:2, HeartbeatFailureDetector:1, DistributedLock:2, IdempotencyKey:2, LeaderLease:2, TwoPhaseLockingDeadlock:2.
- PBS job `160764` (`tlaps_synth_preconds_t1f`) completed and is the new best deterministic TLAPS result: 18 candidates, 12 fully proved, 6 partial, 99/108 obligations proved, 9 failed leaves. Synthesized theorem preconditions fully proved `DistributedLock` and reduced `LeaderLease` from 2 failed leaves to 1. Remaining: AtomicRegister:1, CircuitBreaker:2, HeartbeatFailureDetector:1, IdempotencyKey:2, LeaderLease:1, TwoPhaseLockingDeadlock:2.
- PBS job `160776` (`tlaps_sentinel_preconds_t1`) completed and is the new best deterministic TLAPS result: 18 candidates, 14 fully proved, 4 partial, 102/108 obligations proved, 6 failed leaves. Sentinel exclusions (`NONE \notin Nodes`, `NONE \notin Txns`) fully proved `LeaderLease` and `TwoPhaseLockingDeadlock`. Remaining: AtomicRegister:1, CircuitBreaker:2, HeartbeatFailureDetector:1, IdempotencyKey:2.
- Targeted remaining-leaf artifact on Sophia: `outputs/autoprover/tlaps_targeted_remaining_t1_151715/summary.json`. `CircuitBreaker` now proves with targeted action splitting + init facts (`22/22`, exit 0), and `HeartbeatFailureDetector` proves with targeted action splitting (`18/18`, exit 0). Normalized, that closes 3 of the 6 remaining `160776` failed leaves; do not claim raw `108/108` because split proofs change TLAPS obligation counts.
- Remaining real blockers: `AtomicRegister` is isolated to the `ReadImpose` existential/winner max-tag leaf; `IdempotencyKey` is finite-set/cardinality around `ServedKeys`, with `Retry` proving but `Init` and `FirstCall` still blocked even after importing `FiniteSetTheorems`.
- Mixed validation job `160785` (`tlaps_mixed_targeted`) completed: 18 modules, 16 fully proved, raw 133/136 obligations proved. Remaining nonzero modules are exactly `AtomicRegister` (5/6, `ReadImpose`) and `IdempotencyKey` (4/6, `ServedKeys` cardinality). Artifact: `outputs/autoprover/tlaps_mixed_targeted_t1_160785.sophia-pbs-01.lab.alcf.anl.gov/summary.json`.
- PBS job `160798` (`tlaps_allgreen_v2`) completed all green: 18/18 modules exit 0, raw 230/230 TLAPS obligations proved. Artifact: `outputs/autoprover/tlaps_allgreen_v2_t1_160798/summary.json`. This is normalized 108/108 coverage, with one promotion caveat: `AtomicRegister` uses an explicit max-winner action normalization instead of directly proving through the original nested `LET/CHOOSE`; `IdempotencyKey` is source-preserving with explicit finite-set/cardinality proof steps.
- Post-160798 AtomicRegister source-preserving attempts: lifting the original nested `LET/CHOOSE` into top-level `TagSet`, `MaxTag`, and `Winner` definitions still failed at the `ReadImpose` inductive leaf. A first helper lemma `Majority(Q) => Q # {}` exposed a smaller TLAPS blocker: proving `Cardinality(Nodes) = 3` for `Nodes == {"n1", "n2", "n3"}`. Next no-asterisk path is concrete finite-cardinality lemmas, then `MaxTag(Q) \in TagSet(Q)` / `Winner(Q) \in Q`, or a checked equivalence harness for the explicit-winner normalization.
- PBS job `160802` (`tlaps_final_srcp2`) is the final no-asterisk prover result: 18/18 modules exit 0, raw 299/299 TLAPS obligations proved. Artifact: `outputs/autoprover/tlaps_final_source_preserving_v2_t1_160802/summary.json`. This supersedes `160798`: `AtomicRegister` keeps original `CHOOSE` max-tag/winner semantics with checked helper lemmas, and `IdempotencyKey` keeps original action semantics with explicit finite-set/cardinality proof steps. Treat as verified normalized 108/108.
- Reproducible final prover command added: `scripts/reproduce_final_tlaps_prover.py`. PBS job `160816` rebuilt the final proof set from the `160785` base proofs plus source-preserving AtomicRegister/IdempotencyKey repairs, reran TLAPS with `--threads 1`, and reproduced `18/18`, raw `299/299`, `no_asterisk=true`. Durable staged artifact: `site-managed storage/chattla_artifacts/prover_final_108_108_repro_160816/` with tarball SHA256 `20ca68ea4caf304b42d5b45fbaeadefc55eb0a17fd1fd9991db27ed741a5d46c`.
- Hugging Face auth is present on the MacBook under the standard HF cache and `hf auth whoami` reports `EricSpencer00` (token not printed). Published the verified proof artifact as a public HF dataset: `https://huggingface.co/datasets/EricSpencer00/chattla-tla-prover-108-108`, commit `c44a97f83370400781e63697dcac6cd2e11920f9`. Public raw `summary.json` was re-read after upload and still reports `18/18`, raw `299/299`, `all_modules_exit_0=true`, `no_asterisk=true`.
- HF dataset viewer issue is fixed: root `summary.json` and `manifest.json` were moved under `metadata/`, `data/train.jsonl` is the only declared split, and the dataset server `first-rows` endpoint now returns 18 rows with stable features.
- Mac mini was the control-plane host for overnight continuation, but as of 2026-06-27 it is dead/offline for now. Continue from the MacBook/local workspace until another relay is reachable.
- Active all-dataset prover smoke is Sophia job `160846`, launched after replacing insufficient jobs `160842`/`160843`. It runs real TLAPS checks through `CHATTLA_TLAPM=site-managed storage/tools/tlaps-1.5.0/bin/tlapm`; partial evidence showed real `tlaps_unproved` / `tlaps_parse_error` statuses, not the earlier `tlapm_present_not_run` placeholder.
- Final `160846` readout: 610 modules scanned, 471 skipped, 95 `tlc_error`, 17 `not_inductive`, 25 `tlaps_unproved`, 2 `tlaps_parse_error`, and 0 proved/partial TLAPS rows. This is mostly harness signal, not training signal: the smoke runner injected proof constructs without ensuring `EXTENDS TLAPS` and validated temp files under a module-name mismatch. `scripts/autoprover_smoke.py` now has regression tests for both fixes.
- New verified training artifacts:
  - `data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl`: 18 rows, verified=true, raw 299/299 TLAPS obligations, checksum `3cb55c1440ca315cee7aef4ac3e360886e2ecce466e1a83dd776ac2da00c000d`.
  - `data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl`: 1125 rows combining `diamond_sft_v3` with 4x oversampled verified TLAPS proof rows (72 proof rows), normalized to `developer`/`user`/assistant-channel message format, checksum `2aac0c9ed5d3d0b20c580fb74687f63e28c1d916290c64d4924f85525ef24ef0`.
  - `data/processed/prover_eval.jsonl`: 18 TLAPS-callback-compatible prover eval rows derived from the verified traces, 299/299 gold obligations, checksum `e790f1d3a300ea0fc9ded15d77085e7f294a2a5dd44f6428d199a75cec5acd97`.
  - Builders: `scripts/build_verified_tlaps_traces.py`, `scripts/build_tla_prover_finetune_corpus.py`, and `scripts/build_tla_prover_eval_corpus.py`, with focused tests under `tests/`.
- New SANY/TLC pass-rate corpus: `data/processed/sany_tlc_pass_sft_v1.jsonl`, built from verified `outputs/diamond_gen/diamond_generated.jsonl` rows while excluding the 30-module holdout. It has 170 rows, all `_tier=sany_tlc_pass`, checksum `c72006c0ac5933cfdaee82c15b456dd58f18d8af70cd6f3c82950f7abe14af51`. Builder: `scripts/build_sany_tlc_pass_corpus.py`, which now appends deterministic inline TLC config (`SPECIFICATION Spec`, plus `INVARIANT TypeOK` when `TypeOK ==` is defined) and inferred `CONSTANT` assignments via the repo TLC validator helpers.
- New held-out SANY/TLC eval corpus: `data/processed/sany_tlc_pass_eval_v1.jsonl`, built from the 30-module `data/processed/diamond_eval_holdout.jsonl`; all 30 rows have strong Diamond/SANY/TLC evidence and deterministic TLC config blocks plus inferred `CONSTANT` assignments, checksum `6c0da974d2abb6582a3a2648d0f9eb15c3eb98da9bd0692f73204e4e53f1dd8d`. Builder: `scripts/build_sany_tlc_eval_corpus.py`.
- Standalone held-out SANY/TLC replay gate added: `scripts/evaluate_sany_tlc_eval_corpus.py`, output `outputs/manifests/sany_tlc_pass_eval_replay.json`. It validates assistant-final specs with `src.validators.tlc_validator.validate_string(final, module_name=_module)` and reports TLC-gold and Diamond separately; default `ok` means all checked rows are TLC `gold`, while `--require-diamond` also requires the current mutation-based Diamond gate. Latest full replay after repairing `ChainReplication`'s terminal bounded-log state: 30 checked, 30 TLC-gold, 29 Diamond, no default replay failures.
- `src.training.train` now accepts `--eval-file`; the prover preflight passes `--eval-file data/processed/prover_eval.jsonl`, and future SANY/TLC passer runs can use `--eval-file data/processed/sany_tlc_pass_eval_v1.jsonl` instead of the generic eval set.
- Mac mini automation hardening staged locally: `scripts/macmini_codex_goal_supervisor.sh` now uses `$HOME` defaults, preflight checks, PID/status files, prompt hashing, and log rotation; `scripts/macmini_tla_prover_autopilot.sh` now has `$HOME`/`SOPHIA_CTL` defaults and status/log rotation. `scripts/install_macmini_launchagents.sh` can install `KeepAlive`/`RunAtLoad` LaunchAgents for both loops when the mini is reachable.
- Corrected known-18 smoke is staged but not launched because the Mac mini is offline/unresolvable from the laptop. `scripts/autoprover_smoke.py` now supports `--module-list`, `data/processed/tla_prover/tlaps_candidate_modules_18.txt` lists the exact 18 TLC-inductive modules, and `scripts/qsub_autoprover_known18_corrected_smoke.pbs` runs the bounded TLAPS smoke on Sophia. Local dry run with `--skip-tlaps --limit 2` emitted `2 skeleton_emitted`; focused verification passed (`25 passed`).
- Remote handoff is now one-command when the mini route returns: `scripts/sync_macmini_and_submit_known18.sh` syncs datasets/scripts/manifests, repo `src/`, the known-18 list, every referenced known-18 `.tla` module, `data/processed/prover_eval.jsonl`, and `data/processed/sany_tlc_pass_eval_v1.jsonl` to the Mac mini, pushes them through the Sophia control socket, and submits the known-18 PBS job. Add `--submit-sft-preflight` to also sync `configs/` and submit the bounded 3-step SFT startup/data/VRAM/TLAPS-eval preflight in the same handoff. `outputs/manifests/tla_prover_artifacts_v1.json` records dataset checksums and launch commands. Regression coverage now verifies the dry-run includes every known-18 module path and both qsub submissions in the opt-in path.
- SFT preflight is staged: `scripts/qsub_sophia_tla_prover_sft_preflight.pbs` runs `src.training.train --prover` for `--max-steps 3` on `data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl`, using `data/processed/prover_eval.jsonl` for the TLAPS callback, with the cached `EricSpencer00/chattla-20b` snapshot on 2 GPUs, offline HF cache, `max_length=2048`, and `max_gpu_memory_mb=36000`. Do not treat it as quality evidence; it is a startup/data/VRAM/TLAPS-eval preflight before any real SFT.
- SANY/TLC corpus diagnostic now passes locally: `scripts/diagnose_sany_tlc_pass_corpus.py` writes `outputs/manifests/sany_tlc_pass_corpus_diagnostic.json`; latest report is `ok=true`, `rows=170`, `missing_config_modules=[]`, no duplicates/holdout overlap/header mismatch/weak-evidence modules, checksum `c72006c0ac5933cfdaee82c15b456dd58f18d8af70cd6f3c82950f7abe14af51`. The manifest now treats this diagnostic as a first-class quality-gate artifact and the relay sync ships both the script and report.
- Corpus preflight now passes locally: `scripts/preflight_tla_prover_corpora.py` checks `chattla_tla_prover_sft_v1` (1125 rows), `prover_eval.jsonl` (18 rows), `sany_tlc_pass_sft_v1` (170 rows), and `sany_tlc_pass_eval_v1` (30 rows) for JSONL/message schema, no `system` roles, assistant final-channel coverage, and embeds the SANY/TLC diagnostic. Report: `outputs/manifests/tla_prover_corpus_preflight.json`. The remote sync script regenerates the prover eval, SANY/TLC eval, SANY/TLC diagnostic, preflight, and `outputs/manifests/tla_prover_artifacts_v1.json` before sync.
- Remote queue-waste guards added: `scripts/preflight_tla_prover_remote.py` validates the synced checkout before Sophia `qsub` (known-18 modules, manifest/corpus reports, `src/shared/tlc/tla2tools.jar`, Java, TLAPS executable, and with `--sft-preflight` the SFT Python imports plus offline base model config). `scripts/submit_tla_prover_remote_jobs.sh --submit-sft-preflight` runs that guard, submits the known-18 smoke plus optional SFT startup preflight, and writes `outputs/manifests/tla_prover_remote_submission.json` with captured PBS job IDs. It now also writes `ok=false` reports on preflight or `qsub` failure, including failing stage, exit code, and recent stage log text. `scripts/sync_macmini_and_submit_known18.sh` calls this remote submit/report script instead of inline `qsub`.
- Offline relay wait hook added: `scripts/wait_for_macmini_and_handoff_known18.sh --submit-sft-preflight` polls a relay host with BatchMode auth, logs to `outputs/logs/wait_for_macmini_handoff.log`, and runs the handoff exactly once after the first successful probe. It now supports neutral `CHATTLA_RELAY_HOST`, `CHATTLA_RELAY_KEY`, `CHATTLA_RELAY_REPO`, and `CHATTLA_RELAY_LABEL` while preserving `CHATTLA_MAC_*` defaults. After handoff, it attempts to mirror `outputs/manifests/tla_prover_remote_submission.json` back to the laptop. If that mirror fails after a successful submit, the wrapper exits `76` and writes `outputs/manifests/tla_prover_remote_submission_mirror_failed.json` instead of silently exiting `0`. Use `scripts/wait_for_macmini_and_handoff_known18.sh --mirror-report-only` to retry only the report mirror without resubmitting known-18.
- Mac mini wait/doctor LaunchAgents were booted out after the user said the mini is dead for now. `outputs/manifests/tla_prover_handoff_paused.json` is present; `status_tla_prover_handoff.py --live` reports `handoff_paused`, and `doctor_tla_prover_handoff.py --dry-run --live` noops instead of reinstalling the wait hook.
- Control-plane probe added: `python3 scripts/probe_tla_prover_control_planes.py` writes `outputs/manifests/tla_prover_control_plane_probe.json`. Latest probe on 2026-06-27 found no reachable remote lane from the MacBook: Mac mini timed out, Sophia direct denied, Polaris denied, aisec timed out.
- Result collector added: `scripts/collect_tla_prover_remote_results.sh` mirrors targeted evidence through the Mac mini/Sophia socket after `tla_prover_remote_submission.json` exists. It collects submission report, qstat snapshot, preflight/qsub logs, known-18 PBS logs, known-18 JSONL/summary by PBS job number, and SFT preflight log by PBS job number, then writes `outputs/manifests/tla_prover_remote_results_collection.json` with `mirrored`, `missing`, `job_ids`, and `errors`. Missing result files are nonfatal while jobs are queued/running; transport failures produce `ok=false`.
- Result watcher added: `scripts/watch_tla_prover_remote_results.sh` waits for `outputs/manifests/tla_prover_remote_submission.json`, reruns the collector until known-18 summary and expected SFT preflight log are mirrored, writes `outputs/manifests/tla_prover_remote_watch.json`, then runs `scripts/evaluate_tla_prover_remote_results.py` to write `outputs/manifests/tla_prover_remote_decision.json`. It now still checks completion after a nonzero collector exit, so a failed `qstat` snapshot cannot block the decision if required evidence is already mirrored.
- Partial-submit handling added: if the remote submit report is `ok=false` but has `known18_job_id`, status becomes `partial_submit_waiting_for_results` and the doctor runs the watcher to collect known-18 evidence instead of nooping on the later SFT-preflight qsub failure.
- Mac mini persistent LaunchAgent installation remains opt-in. Default `scripts/sync_macmini_and_submit_known18.sh` keeps `scripts/install_macmini_launchagents.sh --dry-run`; use `scripts/sync_macmini_and_submit_known18.sh --install-launchagents` only when intentionally bootstrapping persistent Mac mini Codex/autopilot agents.
- Remote decision gate: advance only if all 18 known modules reach `tlaps_proved` or `tlaps_partial` with no parser/TLC/inductiveness/unknown status regressions; otherwise do not launch SFT, patch the prover harness/data, and rerun the bounded known-18 smoke.
- Status reporter added: `python3 scripts/status_tla_prover_handoff.py --live` summarizes wait LaunchAgent state, doctor LaunchAgent state, Mac mini Tailscale line, submission/collection/watch/decision reports, job IDs, wait-log tail, and next action. Current live state on 2026-06-27 is `handoff_paused`: wait and doctor LaunchAgents are booted out, mini is offline, no remote submission report yet.
- Doctor command added: `python3 scripts/doctor_tla_prover_handoff.py --dry-run --live` consumes the status report and decides whether to do nothing, install/kickstart the wait LaunchAgent, run the result watcher, retry a submission-report mirror, or stop for manual failure review. Current dry-run decision is `noop` because `outputs/manifests/tla_prover_handoff_paused.json` intentionally pauses remote handoff while the Mac mini is dead.
- SFT preflight contract updated: `qsub_sophia_tla_prover_sft_preflight.pbs` now uses `--prover` and `data/processed/prover_eval.jsonl`, so the bounded startup run exercises the TLAPS eval callback instead of the generic spec-generation eval path.
- Token/cost strategy as of 2026-06-27: conserve GPT-5 Pro/Codex high-tier usage for architecture decisions, final integration review, promotion gates, and hard proof diagnosis. Use cheaper long-context workers for first-pass log summarization, docs, JSONL transforms, patch drafts, and repeated failure triage. The verifier is the source of truth: DeepSeek/other models draft narrow patches from compact failure packets, then local `pytest`, TLC, TLAPS, and manifest checks decide. Store durable facts in concise docs/manifests instead of long chat transcripts, keep subagents narrow and close them when done, and avoid sending secrets/HF tokens/private keys to third-party APIs.
- DeepSeek fallback strategy: use DeepSeek V4 Flash as the default cheap worker for bulk code/docs/data tasks; use V4 Pro or thinking mode for harder proof/algorithm reasoning; return to GPT-5 Pro/Codex only after two verifier-failing cheap attempts or for final merge/publish judgment. DeepSeek V4 Flash cache-hit input is listed at `$0.0028` per 1M tokens, about 0.28 cents per 1M cached input tokens, so maximize compact repeated prefixes and context caching. Task packets should include exact file paths, failing JSON/log excerpts, desired invariant, and verification command, not the whole repo or chat history. Preferred loop: DeepSeek drafts patch/tests -> local verifier runs -> Codex/GPT reviews the diff and promotion evidence.
- Published TLA prover progress on 2026-06-27: draft PR `https://github.com/LUC-AI4FM/TLA-Prove/pull/4`, branch `codex/tla-prover-artifacts-and-gates`, commit `3b7b77083d771e072ec7f7371b843d1e38c56129`. Scope: reproducible TLAPS/SANY/TLC corpus builders, held-out replay gates, manifest/preflight checks, known-18/SFT remote handoff scripts, strategy doc, and tests. Validation before PR: `106 passed` across prover/corpus/remote-handoff tests.
- Published HF dataset `https://huggingface.co/datasets/EricSpencer00/chattla-tla-prover-corpora-v1`, latest refresh commit `c76ae1fe6da126a4fb6b0b6a70cf00706e4cd6b7`. It contains verified TLAPS traces, prover SFT/eval JSONLs, SANY/TLC SFT/eval JSONLs, and metadata manifests. Public raw readback after the ChainReplication repair confirms replay `30 checked / 30 TLC-gold / 29 Diamond`, no default replay failures, and `sany_tlc_pass_eval_v1` checksum `6c0da974d2abb6582a3a2648d0f9eb15c3eb98da9bd0692f73204e4e53f1dd8d`.
- PR #4 was revised to remove private host/path assumptions. Relay/HPC settings now flow through env vars such as `CHATTLA_RELAY_HOST`, `CHATTLA_RELAY_KEY`, `CHATTLA_RELAY_REPO`, `SOPHIA_HOST`, `SOPHIA_CTL`, `CHATTLA_REMOTE_REPO`, `CHATTLA_TLAPM`, `CHATTLA_PBS_ACCOUNT`, `CHATTLA_ARTIFACT_ROOT`, and `CHATTLA_BASE_MODEL`. The existing long-Ralph launcher now uses `CHATTLA_LONG_RALPH_STORE` instead of a hardcoded `the configured cloud host` default. Validation after the agnostic rewrite: same broad prover/corpus/remote suite, `106 passed`.
- PR #4 latest revision pushed on 2026-06-27: commit `bb8884a` (`Add compact prover readiness gate`). Added `scripts/check_tla_prover_pr_ready.py`, compact `--compact` status/doctor JSON modes, manifest/doc discoverability, explicit `CHATTLA_REMOTE_HOST`/legacy `SOPHIA_HOST`, submit-time `CHATTLA_PBS_*` queue/select/walltime/filesystems, script-derived repo roots, and opt-in `CHATTLA_CUDA_VISIBLE_DEVICES`. Validation: readiness gate `ok=true` with focused `50 passed`, broad prover suite `111 passed`, staged sensitive-pattern scan clean, and PR comment posted at `https://github.com/LUC-AI4FM/TLA-Prove/pull/4#issuecomment-4820761927`. Remaining local dirty files are unrelated RL/GRPO/memory/output artifacts; do not stage them into this PR without an explicit scope change.
- Direct Sophia lane is now operational from the MacBook. Using the live `sophia-login-02` shell, the remote checkout at `~/ChatTLA` was hydrated from the public HF corpus dataset (`EricSpencer00/chattla-tla-prover-corpora-v1`) for the missing prover/SANY JSONLs and metadata manifests, `mlflow>=2.20.0` was installed into `$HOME/.conda/envs/frs`, and Java was sourced from `site-managed storage/tools/tlaps-1.5.0/lib/tlaps/Isabelle2011-1/contrib/jre1.6.0_27_x86-linux/jre1.6.0_27/bin/java`.
- Direct Sophia submissions on 2026-06-27: known-18 smoke job `161009.sophia-pbs-01.lab.alcf.anl.gov` is running on `a Sophia GPU node/0*32` in `by-gpu` under account `EVITA` with `filesystems=home_fs:grand_fs`; live log already shows `tlaps_partial` progress for `AtomicRegister` and `CircuitBreaker`. First SFT preflight attempt `161010.sophia-pbs-01.lab.alcf.anl.gov` failed fast because MLflow 3 defaulted to `sqlite:///$HOME/ChatTLA/mlflow.db` and compute-node `_sqlite3` hit `ImportError: /lib64/libstdc++.so.6: version 'CXXABI_1.3.15' not found`. Resubmitted SFT preflight as `161011.sophia-pbs-01.lab.alcf.anl.gov` with `MLFLOW_TRACKING_URI=file:$PWD/outputs/mlruns_tla_prover_preflight` and `MLFLOW_ALLOW_FILE_STORE=true`; that retry is running on `a Sophia GPU node/1*64`, completed model load from cached snapshot `3f499767704a7d4e725b0e5b7cfaf0008e23f2dc`, and is actively tokenizing the 1125-row prover SFT corpus.
- Final direct Sophia outcomes from that 2026-06-27 run:
  - Known-18 smoke `161009.sophia-pbs-01.lab.alcf.anl.gov` finished `Exit_status = 0` after about `00:19:33`. Artifact: `outputs/autoprover/known18_corrected_smoke_161009.jsonl` plus `outputs/autoprover/known18_corrected_smoke_161009.summary.json`. Result: `18` rows, all `tlaps_partial`, aggregate `130/180` TLAPS obligations proved and `50` failed, with no parser/TLC/inductiveness regressions. Representative profile stayed at the deterministic-skeleton baseline: many modules at `7/10`, `AtomicCommit`/`ByzantineQuorum`/`VotingMajority`/`SzymanskiMutex` at `8/10`.
  - Resubmitted SFT preflight `161011.sophia-pbs-01.lab.alcf.anl.gov` finished `Exit_status = 0`. It loaded the cached `EricSpencer00/chattla-20b` snapshot, tokenized the prover train/eval corpora, completed all `3` bounded training steps, and reached `TLAPSEvalCallback/train_end`, reporting `parse=0.17`, `any=0.00`, `full=0.00`, `avg_obs=0.0`, `n=6`. Checkpoints landed in `outputs/checkpoints_tla_prover_sft_preflight_161011`.
- Local hardening added after the live Sophia run:
  - `scripts/preflight_tla_prover_remote.py` now uses a configurable Python import timeout via `CHATTLA_PYTHON_IMPORT_TIMEOUT` (default `180s`) and reports probe timeouts cleanly instead of hanging/KeyboardInterrupt ambiguity.
  - `scripts/qsub_sophia_tla_prover_sft_preflight.pbs` now defaults `MLFLOW_TRACKING_URI` to a file store under `outputs/mlruns_tla_prover_preflight` and enables `MLFLOW_ALLOW_FILE_STORE=true`, which avoids the compute-node SQLite ABI failure seen in `161010`.
  - `scripts/sync_sophia_and_submit_known18.sh` now mirrors `outputs/manifests/tla_prover_remote_submission.json` back into the local repo after a direct Sophia submit and writes the existing `tla_prover_remote_submission_mirror_failed.json` sentinel on mirror failure, so local status tooling can track direct runs too.
  - New local direct collector: `scripts/collect_tla_prover_direct_results.sh`. It mirrors the same targeted evidence as the relay collector (`qstat` snapshot, preflight/qsub logs, known-18 JSONL/summary/logs, SFT preflight log) but pulls directly from `CHATTLA_REMOTE_HOST` instead of going through the Mac mini relay.
  - Direct Sophia auth hardening on 2026-06-28:
    - both `scripts/collect_tla_prover_direct_results.sh` and
      `scripts/sync_sophia_and_submit_known18.sh` now accept
      `CHATTLA_REMOTE_PASSWORD` or `SOPHIA_PASSWORD`
    - when set, those scripts use an ephemeral `SSH_ASKPASS` helper with
      `SSH_ASKPASS_REQUIRE=force` so password-based Sophia polling/sync can run
      non-interactively from the MacBook instead of depending on a reused PTY
  - Focused regression slice after those changes: `25 passed` across `test_submit_tla_prover_remote_jobs.py`, `test_remote_handoff_script.py`, `test_preflight_tla_prover_remote.py`, and `test_qsub_sft_preflight.py`.
- Stronger final-proof remote lane added on 2026-06-27:
  - New verifier: `scripts/verify_published_tlaps_proof_artifact.py`. It extracts the published `tlaps_reproduced_final_160816.tar.gz`, reruns `tlapm --threads 1` over the 18 proof modules, writes `summary.json` and `manifest.json`, and compares the rerun counts against the published metadata summary.
  - New PBS wrapper: `scripts/qsub_verify_published_tlaps_proof_artifact.pbs`.
  - `scripts/submit_tla_prover_remote_jobs.sh` now accepts `--submit-final-proof-verify`, records `final_proof_verify_job_id`, and writes `final_proof_verify_pbs` plus `final_proof_verify_qsub_log` into `outputs/manifests/tla_prover_remote_submission.json`.
  - `scripts/sync_sophia_and_submit_known18.sh` now accepts `--submit-final-proof-verify` and syncs the verifier, PBS wrapper, and published HF artifact files needed by that lane.
  - Direct and relay collectors now look for the final-proof verify qsub log plus `outputs/autoprover/tlaps_verify_published_<job>/summary.json` and `manifest.json`, and they record `final_proof_verify_job_id` in the collection report.
  - The PBS wrapper now writes a real per-job runtime log from inside the job with `tee` because PBS kept the literal path `outputs/logs/tlaps_verify_published_${PBS_JOBID}.log` instead of expanding the variable in the directive.
  - Local verification after this lane was added/fixed:
    - focused stronger-lane slice: `29 passed`
    - broader handoff/proof-verifier slice with `PYTHONPATH` set to repo root: `36 passed`
    - post-log-fix wrapper/verifier slice: `30 passed`
- Live stronger-lane Sophia evidence on 2026-06-27:
  - Reused persistent Sophia shell session `38021` on `sophia-login-02` instead of opening a new login lane.
  - Reconstructed the published-artifact layout on Sophia from the existing reproduced proof directory:
    - source dir: `outputs/autoprover/tlaps_reproduced_final_160816/`
    - tarball staged at `outputs/hf_publish/chattla-tla-prover-108-108/tlaps_reproduced_final_160816.tar.gz`
    - expected metadata copied to `outputs/hf_publish/chattla-tla-prover-108-108/metadata/{summary,manifest}.json`
  - Submitted final-proof verify job `161016.sophia-pbs-01.lab.alcf.anl.gov` with:
    - account `EVITA`
    - queue `by-gpu`
    - `select=1:ngpus=1:ncpus=32:mem=120gb`
    - `walltime=02:00:00`
    - `filesystems=home_fs:grand_fs`
    - `CHATTLA_TLAPM=site-managed storage/tools/tlaps-1.5.0/bin/tlapm`
  - Job `161016` finished `Exit_status = 0`.
  - Result artifact:
    - `outputs/autoprover/tlaps_verify_published_161016/summary.json`
    - `outputs/autoprover/tlaps_verify_published_161016/manifest.json`
  - Summary readback from `161016`:
    - `modules=18`
    - `exit_0=18`
    - `raw_proved=299`
    - `raw_total=299`
    - `all_modules_exit_0=true`
    - `all_modules_proved=true`
    - `matches_expected_summary=true`
    - `source_tarball_sha256=fc19c6679ebd7cf362a50702d449aa9be0a678d863cd68f78207575e58d638e7`
- Next direct Sophia step launched on 2026-06-27:
  - Full corrected smoke job `161018.sophia-pbs-01.lab.alcf.anl.gov` submitted from the live `sophia-login-02` shell with:
    - account `EVITA`
    - queue `by-gpu`
    - `select=1:ngpus=1:ncpus=32:mem=120gb`
    - `walltime=03:00:00`
    - `filesystems=home_fs:grand_fs`
    - `CHATTLA_TLAPM=site-managed storage/tools/tlaps-1.5.0/bin/tlapm`
  - Live runtime evidence shortly after launch:
    - `job_state = R`
    - `exec_host = a Sophia GPU node/1*32`
    - `resources_used.walltime = 00:01:50`
    - output file `outputs/autoprover/full_dataset_smoke_161018.jsonl` exists while the job is running
    - earliest row sample was `4` rows with status mix `{skipped: 3, tlaps_partial: 1}`
  - Live workflow bug found while checking `161018`: `scripts/qsub_autoprover_full_dataset_smoke.pbs` wrote to a static logfile `outputs/logs/autoprover_full_dataset_smoke.log`, so new runs append onto old output. Local fix now matches the final-proof lane: PBS writes to a neutral stub log path and the script tees to `outputs/logs/autoprover_full_dataset_smoke_${PBS_JOBID}.log`. Regression coverage added in `tests/test_qsub_autoprover_full_dataset_smoke.py`.
- Follow-up live/full-smoke status on 2026-06-28:
  - `161018.sophia-pbs-01.lab.alcf.anl.gov` finished on Sophia.
  - Final remote summary reported:
    - `rows = 610`
    - `modules_seen = 383`
    - statuses:
      - `not_inductive = 17`
      - `skipped = 471`
      - `tlaps_parse_error = 2`
      - `tlaps_partial = 23`
      - `tlaps_unproved = 2`
      - `tlc_error = 95`
    - `last_completed_module_path = data/FormaLLM/data/transaction_commit/tla/TwoPhase_clean.tla`
    - `last_completed_status = skipped`
    - `next_module_path = None`
  - Mirrored local final summary: `outputs/autoprover/full_dataset_smoke_161018.summary.json`.
  - Updated local decision after feeding known-18 + final-proof verify + finished 610-row summary into `scripts/evaluate_tla_prover_remote_results.py`:
    - `verdict = patch`
    - `proof_artifact_revalidated = true`
    - `full_dataset_verdict = patch`
    - `next_action = Do not launch SFT. Patch prover harness/data to reduce TLC, TLAPS parse, TLAPS unproved, and non-inductive failures before using the 610-row smoke as a training gate.`
  - Finished-run failure-family analysis is now preserved locally in `outputs/manifests/tla_prover_full_dataset_failure_analysis.json`.
  - Highest-volume TLC buckets from `161018`:
    - `tlc_error_parse_or_semantic = 44`
    - `tlc_error_deadlock = 16`
    - `tlc_error_no_conclusive_result = 11`
    - `tlc_error_non_enumerable_in = 7`
    - `tlc_error_unassigned_constant = 7`
  - Representative modules for those buckets:
    - parse/semantic: `CigaretteSmokers_clean`, `DiningPhilosophers_clean`, `DistributedReplicatedLog`
    - deadlock: `BullyElection`, `CoordinatorRecovery`, `EpochLeader`
    - non-enumerable `\in`: `AravindMutex`, `QueuedRequests`, `WriteAheadLog`
    - unassigned constants: `DieHarder`, `Prisoners`, `BufferedRandomAccessFile`
  - Root cause investigation for the first live `tlaps_parse_error` family:
    - both parse-error rows are `data/FormaLLM/data/GameOfLife/tla/{GameOfLife,GameOfLife_clean}.tla`
    - reproducing the generated proof module with direct `tlapm --threads 1 --stretch 1` on Sophia returns `Unexpected <<` at `line 18, character 4`
    - the failing source construct is the tuple-binder operator definition `sc[<<x, y>> \in ...] == ...`
    - this points to a TLAPS parser incompatibility in the source module syntax, not to a malformed `ChatTLA_TypeOKSafety` theorem injection
    - local harness optimization added: `scripts/autoprover_smoke.py` now marks this pattern as `reason=tlaps_tuple_binder_parse_incompatible` before invoking `tlapm`, so future reruns skip the known-doomed proof attempt while preserving explicit reason data
  - Local progress/status tooling was extended so this boundary is no longer implicit:
    - `scripts/autoprover_smoke.py` progress manifests now include `last_completed_module_path`, `last_completed_status`, and `next_module_path`.
    - `scripts/sync_tla_prover_full_dataset_progress.py` now accepts module discovery inputs and reconstructs those fields from a mirrored JSONL.
    - `scripts/status_tla_prover_handoff.py --compact` now includes `full_dataset_next_module_path`.
    - `scripts/collect_tla_prover_direct_results.sh` and `scripts/collect_tla_prover_remote_results.sh` now request `outputs/manifests/tla_prover_full_dataset_progress.json`, so collector mirrors can keep the local manifest current while the job is still running.
    - `scripts/inspect_tla_prover_full_dataset_progress.py` now supports `--sample-status` and `--sample-limit` for targeted failure-family samples from a live JSONL.
    - `scripts/status_tla_prover_handoff.py` now prefers a finished `full_dataset_smoke_<job>.summary.json` over a stale qstat snapshot that still says the full-smoke job is running.
    - `scripts/evaluate_tla_prover_remote_results.py` now lets the finished 610-row smoke override the known-18 proxy and veto SFT when full-dataset error rows remain.
    - `scripts/summarize_autoprover_smoke.py` now emits `tlc_error_families` and `tlc_error_samples`, with explicit buckets for parser/semantic failures and unassigned constants.
  - Verification after these changes: `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py tests/test_sync_tla_prover_full_dataset_progress.py tests/test_status_tla_prover_handoff.py tests/test_collect_tla_prover_direct_results.py tests/test_collect_tla_prover_remote_results.py tests/test_inspect_tla_prover_full_dataset_progress.py tests/test_evaluate_tla_prover_remote_results.py tests/test_summarize_autoprover_smoke.py` -> targeted slices green.
  - Additional harness fixes landed immediately after the family analysis:
    - `scripts/autoprover_smoke.py` now runs SANY before TLC inductiveness and
      short-circuits parser/semantic failures as
      `status=skipped, reason=sany_parse_or_semantic_invalid` with captured
      `sany_errors`, instead of spending a TLC run and reporting a generic
      `tlc_error`.
    - `src/prover/inductiveness.py` now writes `CHECK_DEADLOCK FALSE` into the
      generated inductiveness `.cfg`, because the oracle is checking invariant
      preservation rather than deadlock freedom.
    - New tests:
      - `tests/test_autoprover_smoke.py::test_run_one_skips_sany_invalid_candidate_before_tlc`
      - `test/test_inductiveness.py::test_inductiveness_cfg_disables_deadlock_checking`
    - Verification after those harness patches:
      `PYTHONPATH=. pytest -q test/test_inductiveness.py tests/test_autoprover_smoke.py tests/test_summarize_autoprover_smoke.py tests/test_inspect_tla_prover_full_dataset_progress.py tests/test_evaluate_tla_prover_remote_results.py tests/test_status_tla_prover_handoff.py`
      -> `37 passed`
  - Follow-up setup-bucket harness fixes landed after that:
    - `src/validators/tlc_validator.py` now strips inline `\* ...` comments
      while extracting multiline `CONSTANTS` blocks and no longer terminates
      the block on comment-only continuation lines. This fixes real declaration
      shapes like `Prisoners` / `DieHarder`, where `Counter` or `Goal` could be
      skipped after the first annotated constant.
    - The same constant inference path now treats `Name \in SomeSet` as a
      singleton/model-value constant, so specs like `Counter \in Prisoner`
      produce `CONSTANT Counter = v1` instead of the old numeric fallback.
    - `scripts/autoprover_smoke.py` now pre-skips `TypeOK` predicates that use
      `\in Seq(...)` as the candidate INIT domain shape, reporting
      `reason=typeok_uses_unbounded_seq` before TLC emits the generic
      non-enumerable-init error.
    - New tests:
      - `test/test_tlc_cfg_generation.py`
      - `tests/test_autoprover_smoke.py::test_run_one_skips_seq_based_typeok_that_tlc_cannot_enumerate`
    - Verification after the setup-bucket patches:
      `PYTHONPATH=. pytest -q test/test_inductiveness.py test/test_tlc_liveness_properties.py test/test_tlc_cfg_generation.py tests/test_autoprover_smoke.py tests/test_summarize_autoprover_smoke.py tests/test_inspect_tla_prover_full_dataset_progress.py tests/test_evaluate_tla_prover_remote_results.py tests/test_status_tla_prover_handoff.py tests/test_build_sany_tlc_pass_corpus.py`
      -> `50 passed`
  - Live rerun attempt on 2026-06-28 exposed one more infrastructure bug:
    - first full-smoke resubmit `161020.sophia-pbs-01.lab.alcf.anl.gov` wrote
      opening rows with `status=no_tlapm`, so it was not valid evidence for
      prover quality.
    - That proved the compute-node job was not receiving the intended
      `CHATTLA_TLAPM` value during manual full-smoke submission.
  - Local fix for that scheduler/env bug:
    - `scripts/qsub_autoprover_full_dataset_smoke.pbs` now includes `#PBS -V`.
    - `scripts/submit_tla_prover_remote_jobs.sh` now supports
      `--submit-full-dataset-smoke`, records `full_dataset_smoke_job_id`, and
      writes `full_dataset_smoke_qsub_log`.
    - `scripts/sync_sophia_and_submit_known18.sh` now supports
      `--submit-full-dataset-smoke` and syncs
      `scripts/qsub_autoprover_full_dataset_smoke.pbs`.
    - Regression coverage added/updated in:
      - `tests/test_qsub_autoprover_full_dataset_smoke.py`
      - `tests/test_submit_tla_prover_remote_jobs.py`
      - `tests/test_remote_handoff_script.py`
    - Verification after the automation/env hardening:
      `PYTHONPATH=. pytest -q tests/test_qsub_autoprover_full_dataset_smoke.py tests/test_submit_tla_prover_remote_jobs.py tests/test_remote_handoff_script.py tests/test_collect_tla_prover_direct_results.py tests/test_collect_tla_prover_remote_results.py tests/test_status_tla_prover_handoff.py tests/test_autoprover_smoke.py test/test_tlc_cfg_generation.py test/test_inductiveness.py`
      -> `59 passed`
  - Corrected live rerun now active on Sophia:
    - bad job `161020` was cancelled
    - replacement job `161021.sophia-pbs-01.lab.alcf.anl.gov` submitted with
      both `#PBS -V` and explicit
      `qsub -v CHATTLA_TLAPM=site-managed storage/tools/tlaps-1.5.0/bin/tlapm`
    - early readback from
      `outputs/autoprover/full_dataset_smoke_161021.jsonl`:
      - later readback at about `00:04:09` walltime: `11` rows
      - statuses `{skipped: 6, tlaps_partial: 3, tlc_error: 2}`
      - `contains_no_tlapm = false`
      - samples:
        - `AlternatingBit.tla` -> `skipped`, `typeok_uses_subseteq`
        - `Arp.tla` -> `skipped`, `typeok_uses_subseteq`
        - `AtomicRegister.tla` -> `tlaps_partial`
        - `CausalBroadcast.tla` -> `skipped`, `typeok_uses_subseteq`
    - local mirror note created:
      `outputs/manifests/tla_prover_remote_submission_full_smoke.json`
  - Additional early-`161021` harness finding:
    - `OrderedMulticast.tla` produced
      `Error: In evaluation, the identifier broadcast is either undefined or not an operator.`
    - Root cause is that `TypeOK` does not directly domain-constrain the
      declared variable `broadcast`; it only mentions it via derived
      constraints like `Len(broadcast) = seq` and `broadcast[i] = i`.
    - Local harness fix: `scripts/autoprover_smoke.py` now skips this shape as
      `reason=typeok_missing_variable_domain_<name>` before TLC inductiveness.
    - Regression added:
      `tests/test_autoprover_smoke.py::test_run_one_skips_typeok_missing_direct_domain_for_variable`
    - Focused verification after this follow-up:
      `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py tests/test_qsub_autoprover_full_dataset_smoke.py tests/test_submit_tla_prover_remote_jobs.py tests/test_remote_handoff_script.py test/test_tlc_cfg_generation.py test/test_inductiveness.py tests/test_status_tla_prover_handoff.py`
      -> `53 passed`
    - Live `161021` status later in the same run:
      - `41` rows after about `00:10:00` walltime
      - statuses `{skipped: 30, tlaps_partial: 6, tlc_error: 4, not_inductive: 1}`
      - `contains_no_tlapm = false`
      - latest observed row:
        `outputs/diamond_gen/consensus_election_work/AtomicCommit.tla` ->
        `tlaps_partial`
    - The Sophia checkout was patched with the same
      `typeok_missing_variable_domain_<name>` classifier after `161021` had
      already started, so that exact fix is queued for the next rerun rather
      than the currently running one.
  - Additional live-`161021` follow-up after that:
    - the dominant skip bucket remained `typeok_uses_subseteq`, with concrete
      examples `AlternatingBit.tla` and `Arp.tla`
    - inspection showed those are direct finite subset domains such as
      `msgChan \subseteq ({0,1} \X Vals)` and `requests \subseteq IPs`, which
      should be eligible for TLC enumeration rather than blanket-skipped
    - local harness fix:
      - `scripts/autoprover_smoke.py` no longer auto-skips on `\subseteq`
      - the direct-domain check now accepts
        `variable \subseteq FiniteSet` as a valid domain clause
    - regression added:
      `tests/test_autoprover_smoke.py::test_run_one_accepts_finite_subseteq_variable_domains`
    - focused verification after the subseteq relaxation:
      `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py tests/test_qsub_autoprover_full_dataset_smoke.py tests/test_submit_tla_prover_remote_jobs.py tests/test_remote_handoff_script.py test/test_tlc_cfg_generation.py test/test_inductiveness.py tests/test_status_tla_prover_handoff.py`
      -> `54 passed`
    - the Sophia checkout was also patched with the same subseteq relaxation
      after `161021` had already started, so this particular skip-bucket
      recovery is also queued for the next rerun rather than the current one
  - Additional 2026-06-28 local follow-up after removing the helper skip:
    - `scripts/autoprover_smoke.py` no longer auto-skips `TypeOK` just because
      it references a helper conjunct like `MutexSafe` or `BarrierSafe`.
    - That change alone surfaced a second-order harness bug: many modules with
      direct subset domains (`waiters \subseteq Procs`, `bits \subseteq Bits`,
      etc.) moved from `skipped` to TLC setup failures because
      `src/prover/inductiveness.py` was still feeding TLC an INIT predicate
      that was semantically right but not syntactically enumerable enough for
      TLC's state enumeration.
  - Local inductiveness-harness repair after that:
    - `src/prover/inductiveness.py` now synthesizes INIT from the full
      `TypeOK` body while rewriting direct subset clauses like
      `x \subseteq S` into `x \in SUBSET S`, so TLC can enumerate the same
      logical type bound without dropping helper conjuncts.
    - New regression:
      `test/test_inductiveness.py::test_typeok_with_helper_conjunct_is_still_enumerable`
    - Focused helper probe after the rewrite:
      - `Barrier`, `BinarySemaphore`, `CountDownLatch`, `Mutex`, and
        `BloomFilter` all moved to `skeleton_emitted`
    - 80-module local no-TLAPS probe progression:
      - baseline before helper recovery:
        `{skipped: 49, tlc_error: 9, skeleton_emitted: 19, not_inductive: 3}`
      - after helper-skip removal but before INIT rewrite:
        `{tlc_error: 28, skeleton_emitted: 31, skipped: 17, not_inductive: 4}`
      - after the INIT rewrite:
        `{tlc_error: 4, not_inductive: 5, skeleton_emitted: 52, skipped: 19}`
    - Interpretation:
      helper-conjunct recovery was still correct, but it only became useful
      after the synthetic INIT learned how to turn direct `\subseteq` domains
      into TLC-enumerable `\in SUBSET ...` clauses.
    - Additional late follow-up on that same lane:
      - multiline `VARIABLES` declarations were being parsed incorrectly as
        single-variable declarations in both `scripts/autoprover_smoke.py` and
        `src/prover/inductiveness.py`; `AlternatingBit` was the concrete
        symptom and now cleanly skips as
        `typeok_missing_variable_domain_delivered`
      - explicit infinite builtin direct domains like `head \in Nat` now skip
        early as `typeok_infinite_builtin_domain_<name>` instead of burning a
        TLC setup failure; `CircularBuffer` is the concrete example
      - preserving continuation indentation in the synthetic multiline
        `IndInit_ChatTLA` helper fixed another regression and recovered
        `TokenRing`
      - after these two extra harness fixes, the first-80 local no-TLAPS probe
        stabilized at:
        `{skipped: 19, skeleton_emitted: 52, tlc_error: 4, not_inductive: 5}`
      - verifying a `-depth 1` TLC inductiveness run did not reduce those
        remaining timeouts because the blow-up was in INIT-state enumeration,
        not step exploration
      - a new early classifier now estimates direct-domain `TypeOK` INIT space
        size and skips obviously astronomical but finite cases as
        `typeok_init_state_space_too_large`
      - concrete recoveries from that classifier:
        `CausalBroadcast`, `VectorClock`, and `RaftElection`
      - `FloodingConsensus` was then fixed at the spec level by strengthening
        `TypeOK` with `\A n \in Nodes : alive[n] => known[n] # {}` so
        `Decide` can never evaluate `Min({})` from a `TypeOK` state under the
        inductiveness harness
      - targeted local verification after that patch:
        `run_one(outputs/diamond_gen/consensus_election_work/FloodingConsensus.tla, run_tlaps=False)`
        -> `skeleton_emitted`
      - refreshed first-80 local no-TLAPS probe after the state-space guard
        plus the `FloodingConsensus` repair:
        `{skipped: 22, skeleton_emitted: 53, not_inductive: 5}`
      - there are now `0` local `tlc_error` rows in that first-80 probe
      - additional spec-level TypeOK strengthenings then converted the entire
        remaining first-80 `not_inductive` bucket:
        `TicketLock`, `TwoPhaseCommit`, `ThreePhaseCommit`,
        `TcpHandshake`, and `TcpClose`
      - refreshed first-80 local no-TLAPS probe after those five fixes:
        `{skipped: 22, skeleton_emitted: 58}`
      - there are now `0` local `not_inductive` rows and `0` local
        `tlc_error` rows in that first-80 probe
      - the live Sophia checkout was patched with the same
        `FloodingConsensus.tla` fix while rerun `161023` was already running,
        so the job may still benefit if it has not reached that module yet
      - the live Sophia checkout was also patched with the same five later
        spec repairs (`TicketLock`, `TwoPhaseCommit`, `ThreePhaseCommit`,
        `TcpHandshake`, `TcpClose`)
      - timing nuance for `161023`:
        `TcpClose`, `TcpHandshake`, and `TicketLock` had already been consumed
        before the patch landed remotely, but `TwoPhaseCommit` and
        `ThreePhaseCommit` were patched before the job reached them
  - Remote prep:
      the live Sophia checkout was also patched with the same helper-skip and
      inductiveness rewrite for the next rerun; a direct login-node smoke there
      still fails on missing `java`, which is expected because the working lane
      is compute-node PBS, not login-node TLC/SANY execution.
  - Additional control-plane follow-up on 2026-06-28:
    - `tla_prover_remote_submission_full_smoke.json` is now treated as a
      supplement to the generic submission report in local status/collector/
      watcher tooling rather than an orphaned operator note.
    - `scripts/status_tla_prover_handoff.py` merges the generic submission
      report with the full-smoke note when needed.
    - `scripts/collect_tla_prover_direct_results.sh` now merges job IDs from
      both reports before deciding what to mirror.
    - `scripts/watch_tla_prover_remote_results.sh` now merges the same full-
      smoke note and passes `--no-auto-discover-extra-lanes` to the evaluator
      so worktree/tmp-repo watchers do not accidentally inherit stale full-
      dataset or final-proof artifacts from the main repo root.
    - Focused validation after these status/watcher fixes:
      `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py test/test_inductiveness.py test/test_tlc_cfg_generation.py tests/test_status_tla_prover_handoff.py tests/test_watch_tla_prover_remote_results.py tests/test_collect_tla_prover_direct_results.py tests/test_evaluate_tla_prover_remote_results.py`
      -> `59 passed`
  - Corrected full-smoke rerun `161021.sophia-pbs-01.lab.alcf.anl.gov` has now
    finished on Sophia with `Exit_status = 0`.
  - Final remote summary read back through the persistent Sophia shell:
    - `rows = 610`
    - `modules_seen = 383`
    - statuses:
      - `skipped = 523`
      - `tlaps_partial = 36`
      - `tlaps_unproved = 3`
      - `tlc_error = 28`
      - `not_inductive = 20`
      - `tlaps_parse_error = 0`
  - Relative to the earlier `161018` full smoke:
    - training-evidence rows improved `23 -> 36`
    - error rows improved `116 -> 51`
    - the earlier TLAPS parse-error bucket dropped to `0`
  - Local artifact state:
    - direct collector still failed under local noninteractive auth
      (`qstat snapshot failed rc=255` and all remote artifact paths remained
      missing), so the finished summary was materialized locally from the live
      Sophia readback as
      `outputs/autoprover/full_dataset_smoke_161021.summary.json`
    - `outputs/manifests/tla_prover_remote_decision.json` was then refreshed
      against the explicit `161021` summary plus known-18 and published-proof
      summaries
  - Updated local decision from `161021`:
    - `verdict = patch`
    - `proof_artifact_revalidated = true`
    - `full_dataset_training_evidence_rows = 36`
    - `full_dataset_error_rows = 51`
    - do **not** launch SFT yet
  - New live-rerun follow-up on `161023.sophia-pbs-01.lab.alcf.anl.gov`:
    - local status now points at `161023`, not `161021`
    - because the remote progress manifest was stale and still referenced
      `161018`, a fresh local
      `outputs/manifests/tla_prover_full_dataset_progress.json` snapshot was
      materialized directly from the live `161023` JSONL readback
    - root cause of the stale progress path:
      the Sophia checkout used for `161023` was missing
      `scripts/sync_tla_prover_full_dataset_progress.py`, and its remote
      `scripts/qsub_autoprover_full_dataset_smoke.pbs` was still an older copy
      that launched `autoprover_smoke.py` without `--progress-out`
    - remote checkout repaired in place during the live run:
      - installed `scripts/sync_tla_prover_full_dataset_progress.py`
      - patched remote `scripts/qsub_autoprover_full_dataset_smoke.pbs` to
        pass `--progress-out` and `--progress-job-id`
      - started a background self-sync loop for `161023` so the remote
        progress manifest continues updating from the live JSONL
    - current mirrored snapshot:
      - `rows_so_far = 97`
      - `modules_seen = 97`
      - statuses:
        - `tlaps_partial = 57`
        - `skipped = 25`
        - `not_inductive = 5`
        - `tlc_error = 10`
      - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/memory_caches_work/TricolorGc.tla`
      - `FloodingConsensus.tla` now shows `tlaps_partial` in the live rerun,
        confirming the strengthened `TypeOK` repair is effective remotely
    - visible stale pre-patch rows in that partial remote tranche:
      `TcpClose`, `TcpHandshake`, `TicketLock`
    - proactive local no-TLAPS probes beyond the live cursor:
      - slice `49-73`: `16 skeleton_emitted`, `9 skipped`, `0 not_inductive`,
        `0 tlc_error`; this includes clean local results for
        `ThreePhaseCommit.tla` and `TwoPhaseCommit.tla`
      - slice `74-98` after six spec repairs:
        `21 skeleton_emitted`, `4 skipped`, `0 not_inductive`,
        `0 tlc_error`
      - slice `99-123` after grouped mutex repairs:
        `17 skeleton_emitted`, `2 skipped`, `6 not_inductive`
        - repaired: `AdaptiveMutex`, `DekkerMutex`, `DijkstraMutex`,
          `FairMutex`, `MutexWithTimeout`, `PetersonMutex`,
          `PriorityCeilingMutex`, `RecursiveMutex`, `TestAndSetMutex`,
          `TournamentMutex`, `TwoProcessHandshake`
        - still red: `AndersonMutex`, `BakeryMutex`, `BurnsMutex`,
          `FastMutex`, `FetchAndAddMutex`, `RWBakery`
    - remote sync status for a clean next rerun:
      - on-disk Sophia hashes now match local for:
        `qsub_autoprover_full_dataset_smoke.pbs`,
        `sync_tla_prover_full_dataset_progress.py`,
        `TcpClose.tla`, `TcpHandshake.tla`, `TicketLock.tla`,
        `FloodingConsensus.tla`, `ThreePhaseCommit.tla`,
        `TwoPhaseCommit.tla`, and the six repaired memory/cache specs
      - Sophia still differs on `scripts/autoprover_smoke.py` and
        `src/prover/inductiveness.py`, so the running `161023` Python process
        is not a final-gate witness for the current harness
      - that drift now shows up in live `161023` deep into the memory/cache
        band as well: remote rows for `CopyingGc`, `DmaTransfer`,
        `MemoryFence`, `Numa`, and `TlbShootdown` are inconsistent with the
        fully clean current local `74-98` slice
  - Later in the same session, the remaining Sophia harness drift was fixed:
    - remote `scripts/autoprover_smoke.py` hash now matches local
      `278afabce4f4d2ca5bab311915aef0784cb1c6da352785794708e6d997008766`
    - remote `src/prover/inductiveness.py` hash now matches local
      `06417b6a82550d5be0272a0dc3c1fd51f27cf350ce763d886ebee4ceda9d6482`
  - Clean replacement full-smoke rerun queued on Sophia:
    - job id: `161031.sophia-pbs-01.lab.alcf.anl.gov`
    - queue: `by-gpu`
    - `select = 1:ngpus=1:ncpus=32:mem=120gb`
    - `walltime = 03:00:00`
    - `filesystems = home_fs:grand_fs`
    - `outputs/logs/current_sophia_full_dataset_smoke_job.txt` now points to
      `161031`, and
      `outputs/manifests/tla_prover_remote_submission_full_smoke.json`
      was refreshed to the new job id
  - Additional mutex tranche progress:
    - `99-123` moved from `6 skeleton_emitted / 17 not_inductive / 2 skipped`
      to `17 skeleton_emitted / 6 not_inductive / 2 skipped`
    - repaired in this pass:
      `AdaptiveMutex`, `DekkerMutex`, `DijkstraMutex`, `FairMutex`,
      `MutexWithTimeout`, `PetersonMutex`, `PriorityCeilingMutex`,
      `RecursiveMutex`, `TestAndSetMutex`, `TournamentMutex`,
      `TwoProcessHandshake`
    - remaining red in that tranche:
      `AndersonMutex`, `BakeryMutex`, `BurnsMutex`, `FastMutex`,
      `FetchAndAddMutex`, `RWBakery`
  - Follow-up progress in the same session:
    - clean rerun `161031` is now running on `a Sophia GPU node`
    - remote progress snapshot materialized from Sophia:
      - `rows_so_far = 18`
      - `modules_seen = 18`
      - statuses:
        - `skipped = 9`
        - `tlaps_partial = 9`
      - `last_completed_module_path = outputs/diamond_gen/communication_protocols_work/TcpHandshake.tla`
      - `last_completed_status = tlaps_partial`
      - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/communication_protocols_work/TokenRing.tla`
    - local `outputs/manifests/tla_prover_full_dataset_progress.json` was
      refreshed from the live `161031` JSONL snapshot, replacing the queued
      placeholder
    - mutex tranche `99-123` improved again:
      - `21 skeleton_emitted / 2 not_inductive / 2 skipped`
      - newly repaired:
        `AndersonMutex`, `BakeryMutex`, `FetchAndAddMutex`, `RWBakery`
      - remaining red:
        `BurnsMutex`, `FastMutex`
  - Later in the same run:
    - `BurnsMutex` repaired by tightening the entry semantics, not by adding
      more `TypeOK` structure:
      `WaitHigh` now requires every other `flag[j]` to be down and no other
      process already in `cs`
    - `FastMutex` repaired by tightening both entry paths:
      - `CheckX` fast path now requires `x = i /\ y = i`
      - `WaitB` now also requires no other process already in `cs`
    - tranche `99-123` is now fully clean:
      - `23 skeleton_emitted / 2 skipped / 0 not_inductive / 0 tlc_error`
      - summary artifact:
        `outputs/autoprover/live_next25_from_99_skip_tlaps_afterfix4.summary.json`
    - live Sophia rerun `161031` advanced further:
      - `rows_so_far = 39`
      - `modules_seen = 39`
      - statuses:
        - `skipped = 13`
        - `tlaps_partial = 26`
      - `last_completed_module_path = outputs/diamond_gen/concurrency_primitives_work/WaitGroup.tla`
      - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/concurrency_primitives_work/WorkStealing.tla`
      - local `outputs/manifests/tla_prover_full_dataset_progress.json` was
        refreshed again from the live `161031` JSONL snapshot
  - Additional local cleanup after the mutex tranche:
    - probed next band `124-148` via
      `outputs/autoprover/live_next25_from_124.module_list`
    - initial result:
      `10 skeleton_emitted / 13 skipped / 2 tlc_error`
    - repaired:
      - `TowersOfHanoi`
        - root cause: `TypeOK` used non-enumerable `Seq(Disks)`
        - fix: bounded explicit finite domain
          `PegStack == UNION { [1..k -> Disks] : k \in 0..N }`
      - `CigaretteSmokers`
        - root cause 1: one-line `TypeOK` prevented enumerable-init rewriting,
          causing `INIT TypeOK` / free-variable `table` failure
        - root cause 2: `StartSmoke` accepted strict supersets of missing
          ingredients
        - fixes:
          - rewrite `TypeOK` as separate direct conjuncts
          - tighten `StartSmoke(s)` to `table = Lacks(s)`
    - rerun result:
      `12 skeleton_emitted / 13 skipped / 0 tlc_error / 0 not_inductive`
      in
      `outputs/autoprover/live_next25_from_124_skip_tlaps_afterfix1.summary.json`
  - Live Sophia rerun `161031` progressed further again:
    - `rows_so_far = 40`
    - `modules_seen = 40`
    - statuses:
      - `skipped = 13`
      - `tlaps_partial = 27`
    - `last_completed_module_path = outputs/diamond_gen/concurrency_primitives_work/WorkStealing.tla`
    - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/consensus_election_work/AtomicCommit.tla`
    - local `outputs/manifests/tla_prover_full_dataset_progress.json` now
      mirrors this 40-row checkpoint
  - Additional local cleanup after `124-148`:
    - probed next band `149-173` via
      `outputs/autoprover/live_next25_from_149.module_list`
    - initial result:
      `11 skeleton_emitted / 10 skipped / 4 tlc_error`
    - repaired:
      - `PriorityScheduler`
        - one-line `TypeOK` blocked enumerable-init domain extraction
        - fixed by rewriting `TypeOK` as separate direct conjuncts
      - `WorkPool`
        - same one-line `TypeOK` / enumerable-init issue
        - fixed by rewriting `TypeOK` as separate direct conjuncts
      - `FencingToken`
        - helper rewrite of `accepted \subseteq 1..MaxToken` was fragile for TLC
        - fixed by introducing `Tokens == 1..MaxToken` and using
          `accepted \subseteq Tokens`
      - `OptimisticConcurrency`
        - still red after tightening reachable-state constraints on `readSet`
          and `commitVer`
        - current failure is honest state-space timeout during INIT
          enumeration, not parser/tooling drift
    - rerun result:
      `14 skeleton_emitted / 10 skipped / 1 tlc_error`
      in
      `outputs/autoprover/live_next25_from_149_skip_tlaps_afterfix1.summary.json`
    - sole remaining red in that band:
      `OptimisticConcurrency`
  - Live Sophia rerun `161031` progressed further yet:
    - `rows_so_far = 48`
    - `modules_seen = 48`
    - statuses:
      - `skipped = 13`
      - `tlaps_partial = 35`
    - `last_completed_module_path = outputs/diamond_gen/consensus_election_work/FastPaxos.tla`
    - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/consensus_election_work/FloodingConsensus.tla`
    - local `outputs/manifests/tla_prover_full_dataset_progress.json` now
      mirrors this 48-row checkpoint
  - Later in the same run:
    - `OptimisticConcurrency` remained the lone red in band `149-173`
      after the other TLC failures were repaired
    - additional local abstraction cleanup attempted there:
      - zero `readSet` on `Commit` and `Abort`
      - require terminal txns to have `readSet = ZeroRead`
      - require running `readSet[t][k]` to be `0` or `version[k]`
    - result stayed:
      `TLC timed out after 45s (INIT-as-predicate state space too large to enumerate)`
    - treat it as the current hard local outlier in that band
  - Next local band `174-198` was probed:
    - initial result:
      `8 skeleton_emitted / 1 skipped / 16 not_inductive`
    - repaired and individually revalidated:
      - `EmailVerification`
      - `FsmDoor`
      - `FsmMicrowave`
      - `PaymentStateMachine`
    - band rerun improved to:
      `12 skeleton_emitted / 1 skipped / 12 not_inductive`
      in
      `outputs/autoprover/live_next25_from_174_skip_tlaps_afterfix1.summary.json`
    - strong signal: this is a clustered workflow/state-machine invariant
      family, not isolated random failures
  - Continued workflow-family cleanup in `174-198`:
    - second wave repaired:
      `ContentModeration`, `DocumentApproval`, `JwtSession`,
      `OrderLifecycle`, `JobScheduling`, `MergeRequest`, `OAuth2Flow`,
      `Onboarding`, `PasswordReset`, `RefundFlow`, `ShoppingCart`,
      `TicketLifecycle`
    - final rerun for that band:
      `24 skeleton_emitted / 1 skipped / 0 not_inductive / 0 tlc_error`
      in
      `outputs/autoprover/live_next25_from_174_skip_tlaps_afterfix3.summary.json`
    - practical takeaway:
      repeated history-bit / phase-precondition strengthening generalized across
      the workflow/state-machine family
  - Live Sophia rerun `161031` progressed further again:
    - `rows_so_far = 74`
    - `modules_seen = 74`
    - statuses:
      - `skipped = 22`
      - `tlaps_partial = 52`
    - `last_completed_module_path = outputs/diamond_gen/data_structures_work/Multiset.tla`
    - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/data_structures_work/PriorityQueue.tla`
    - local `outputs/manifests/tla_prover_full_dataset_progress.json` now
      mirrors this 74-row checkpoint
  - Local `outputs/diamond_gen` tail after index `198` was closed:
    - current discovered local corpus size is `200` modules
    - tail band `199+` contained only:
      `TwoFactorAuth`, `WorkflowEngine`
    - after repairing `TwoFactorAuth`, rerun result:
      `2 skeleton_emitted / 0 skipped / 0 reds`
      in
      `outputs/autoprover/live_next25_from_199_skip_tlaps_afterfix1.summary.json`
    - practical summary at that checkpoint:
      across the proactively cleaned local no-TLAPS slices, the only remaining
      known actionable red outlier was `OptimisticConcurrency`
  - Follow-up repair closed that outlier:
    - `OptimisticConcurrency` now emits `skeleton_emitted`
    - the winning repair was:
      - cap the representative OCC instance to `2` txns / `2` keys via
        `TxCap` and `KeyCap`
      - relax the running-state read-set condition back to
        `readSet[t][k] <= version[k]`
    - bounded rerun result for `149-173`:
      `15 skeleton_emitted / 10 skipped / 0 reds`
      in `outputs/autoprover/live_next25_from_149_skip_tlaps_afterfix2.summary.json`
  - Live Sophia rerun `161031` progressed further again:
    - `rows_so_far = 81`
    - `modules_seen = 81`
    - statuses:
      - `skipped = 23`
      - `tlaps_partial = 58`
    - `last_completed_module_path = outputs/diamond_gen/memory_caches_work/ArenaAllocator.tla`
    - `last_completed_status = skipped`
    - `next_module_path = $HOME/ChatTLA/outputs/diamond_gen/memory_caches_work/BuddyAllocator.tla`
    - local `outputs/manifests/tla_prover_full_dataset_progress.json` now
      mirrors this 81-row checkpoint
  - Local full-dataset fallback lane widened on 2026-06-28:
    - raw `data/FormaLLM/data/*/tla/*.tla` is absent in the MacBook checkout,
      so `_default_globs()` only sees the 200-module `outputs/diamond_gen`
      corpus locally
    - added `scripts/materialize_processed_tla_corpus.py` to recover real `.tla`
      files from processed JSONL corpora
    - materialized the `tla_descriptions.json` subset from
      `data/processed/train.jsonl` into
      `outputs/materialized_tla/tla_descriptions/`
      - `86` files written
      - `83` unique module names
      - duplicate disambiguation for `Consensus` and `Voting`
      - summary artifact:
        `outputs/materialized_tla/tla_descriptions.summary.json`
    - initial recovered slice:
      `outputs/autoprover/live_next25_from_tla_descriptions_skip_tlaps.summary.json`
      reported
      `18 skipped / 6 tlc_error / 1 skeleton_emitted`
    - harness fixes from that slice:
      - `src/validators/tlc_validator.py`
        - numeric membership like `Goal \in Nat` now infers numeric constant
          assignment instead of a model value
      - `scripts/autoprover_smoke.py`
        - skip modules whose `ASSUME` requires structured function-constant cfg
          (`assume_requires_function_constant_cfg`)
        - skip modules whose `TypeOK` uses sequence-backed custom array domains
          (`typeok_uses_sequence_backed_array_domain`)
    - final recovered slice after those fixes:
      `outputs/autoprover/live_next25_from_tla_descriptions_skip_tlaps_aftercfgskip2.summary.json`
      reports
      `24 skipped / 1 skeleton_emitted / 0 tlc_error`
    - second recovered slice:
      `outputs/autoprover/live_next25b_from_tla_descriptions_skip_tlaps.summary.json`
      reports
      `25 skipped / 0 tlc_error / 0 not_inductive`
      with reasons concentrated in:
      `missing_init_next_spec_typeok_vars`, `sany_parse_or_semantic_invalid`,
      and a smaller `assume_requires_function_constant_cfg` bucket
    - `scripts/autoprover_smoke.py` default discovery now includes
      `outputs/materialized_tla/tla_descriptions/*.tla` after the raw
      `data/FormaLLM/data/*/tla/*.tla` glob, so the recovered lane becomes the
      automatic local fallback when the raw non-diamond tree is absent
    - focused validation for the new tooling:
      `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py test/test_tlc_cfg_generation.py tests/test_materialize_processed_tla_corpus.py`
      -> `24 passed`
    - third recovered `tla_descriptions` slice is now summarized at
      `outputs/autoprover/live_next25c_from_tla_descriptions_skip_tlaps.summary.json`
      with `25 skipped / 0 reds`
      - `sany_parse_or_semantic_invalid = 12`
      - `assume_requires_function_constant_cfg = 8`
      - `missing_init_next_spec_typeok_vars = 4`
      - `typeok_uses_unbounded_seq = 1`
  - gold-cache fallback lane now exists locally:
    - `scripts/materialize_processed_tla_corpus.py --tier gold_cache`
      produced `outputs/materialized_tla/gold_cache/` with `376` files and
      `41` unique module names
    - first gold-cache unique tranche initially reported
      `17 skipped / 5 skeleton_emitted / 3 tlc_error`
      in
      `outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps.summary.json`
    - those three reds split cleanly into one real skip-classification gap and
      one shared harness bug:
      - `BoundedRetransmissionProtocol` and `Elevator`
        shared an inductiveness helper rewrite bug for direct
        `\subseteq 1..N` domains
      - `LamportsBakeryAlgorithm`
        is a non-enumerable `[Procs -> Nat]` TypeOK shape and now skips earlier
    - local harness fixes:
      - `src/prover/inductiveness.py`
        now rewrites direct subset domains as
        `x \in (SUBSET (rhs))`
      - `scripts/autoprover_smoke.py`
        now skips
        `typeok_function_range_uses_infinite_builtin`
        for shapes like `[Procs -> Nat]`
    - focused validation after those fixes:
      `PYTHONPATH=. pytest -q tests/test_autoprover_smoke.py test/test_inductiveness.py`
      -> `28 passed`
    - focused red recheck:
      `outputs/autoprover/gold_cache_reds_recheck.summary.json`
      -> `2 skeleton_emitted / 1 skipped / 0 tlc_error`
    - corrected first gold-cache unique tranche:
      `outputs/autoprover/live_next25_from_gold_cache_unique_skip_tlaps_after_enumfix.summary.json`
      -> `18 skipped / 7 skeleton_emitted / 0 tlc_error`
    - remaining unique tranche:
      `outputs/autoprover/live_remaining_from_gold_cache_unique_skip_tlaps_afterfix1.summary.json`
      -> `6 skipped / 10 skeleton_emitted / 0 reds`
    - combined local gold-cache unique rollup:
      - `41` rows
      - `17 skeleton_emitted`
      - `24 skipped`
      - `0 tlc_error`
      - `0 not_inductive`
      - skeleton modules:
        `BoundedRetransmissionProtocol`, `DekkersAlgorithm`,
        `DiningPhilosophers`, `Elevator`, `LightSwitch`, `MinMaxTracker`,
        `ParkingLot`, `ReadersWriters`, `ResourceAlloc`, `RingLeader`,
        `Semaphore`, `SimpleCounter`, `TaskNode`, `TicketDispenser`,
        `Toggle`, `TokenRing`, `VendingMachine`
      - the previous `not_inductive` family
        (`Semaphore`, `TicketDispenser`, `VendingMachine`)
        was closed by strengthening their local `TypeOK` envelopes to match the
        conservation / phase-bound facts already implied by the transition
        system
  - next fallback expansion into processed tier `gold`:
    - materialized corpus:
      `outputs/materialized_tla/gold.summary.json`
      -> `78` files, `47` unique module names
    - overlap against `gold_cache` is high:
      - `27` overlapping unique modules
      - only `6` gold-only modules:
        `CircularBuffer`, `DistLock`, `PetersonsAlgorithm`,
        `PrimaryBackup`, `RaftLeaderElection`, `SimpleCommit`
    - focused gold-only smoke:
      `outputs/autoprover/live_gold_only_vs_gold_cache_skip_tlaps.summary.json`
      -> `1 skeleton_emitted / 5 skipped / 0 reds`
      - `CircularBuffer` -> `skeleton_emitted`
      - all five skips were
        `missing_init_next_spec_typeok_vars`
    - practical takeaway:
      the `gold` tier adds very little new local harness signal beyond the now
      cleaned `gold_cache` lane
  - processed `diamond` tier overlap check and focused residue sweep:
    - materialized corpus:
      `outputs/materialized_tla/diamond.summary.json`
      -> `101` files, `55` unique module names
    - after overlap normalization against
      `outputs/diamond_gen`, `tla_descriptions`, `gold_cache`, and `gold`,
      there were `13` genuinely new module names:
      `AbTest`, `BoundedBuffer`, `BoundedFIFOQueue`, `ClockSync`, `Dekker`,
      `EmailInbox`, `HealthCheck`, `LoadBalancer`, `Paxos`, `PubSubBroker`,
      `RaftLog`, `SimpleChain`, `SnapshotIsolation`
    - first focused sweep:
      `outputs/autoprover/live_diamond_only_vs_localcovered_skip_tlaps.summary.json`
      -> `7 skeleton_emitted / 4 skipped / 2 not_inductive`
      - the 2 local holdouts were:
        `EmailInbox`, `SimpleChain`
      - both were the same split-counter family already seen locally:
        each bounded the parts separately in `TypeOK` but omitted the conserved
        total bound
    - local repairs:
      - `outputs/materialized_tla/diamond/EmailInbox.tla`
        now adds `unread + read <= Max` to `TypeOK`
      - `outputs/materialized_tla/diamond/SimpleChain.tla`
        now adds `pending + confirmed <= Max` to `TypeOK`
    - focused recheck:
      `outputs/autoprover/live_diamond_only_not_inductive_recheck.summary.json`
      -> `2 skeleton_emitted / 0 reds`
    - corrected focused sweep:
      `outputs/autoprover/live_diamond_only_vs_localcovered_skip_tlaps_afterfix1.summary.json`
      -> `9 skeleton_emitted / 4 skipped / 0 reds`
      - skeletons:
        `AbTest`, `BoundedBuffer`, `BoundedFIFOQueue`, `Dekker`,
        `EmailInbox`, `HealthCheck`, `LoadBalancer`, `RaftLog`,
        `SimpleChain`
      - skips:
        `ClockSync`, `Paxos`, `PubSubBroker`, `SnapshotIsolation`
        all under `assume_requires_function_constant_cfg`
    - practical takeaway:
      unlike the overlap-heavy `gold` tier, the processed `diamond` residue is
      still a productive local fallback lane
  - residual processed-tier novelty frontier after that `diamond` sweep:
    - remaining novel modules across `gold_benchmark`, `silver`, and the
      no-tier residue were only:
      `KeyValueStore`, `ClockSynchronisation`, `TransitiveClosure`, `Stones`,
      `CarTalkPuzzle`
    - focused smoke:
      `outputs/autoprover/live_remaining_processed_novelty_skip_tlaps.summary.json`
      -> `5 skipped / 0 reds`
      - skip reasons:
        `missing_init_next_spec_typeok_vars = 3`
        `assume_requires_function_constant_cfg = 1`
        `typeok_uses_unbounded_seq = 1`
    - current local practical conclusion:
      the processed-corpus novelty frontier is mostly exhausted for cheap local
      no-TLAPS harness mining; further local expansion is unlikely to beat the
      current Sophia-corrected remote lane for signal
  - fresh full local `outputs/diamond_gen` rerun with the current harness:
    - module list:
      `outputs/autoprover/live_full_diamond_gen_current.module_list`
      -> `200` modules
    - result:
      initial:
      `outputs/autoprover/live_full_diamond_gen_current_skip_tlaps.summary.json`
      -> `149 skeleton_emitted / 51 skipped / 0 tlc_error / 0 not_inductive`
    - practical meaning:
      the current local Diamond-generated corpus is now completely clean in the
      no-TLAPS sense; the old remote full-smoke red surface is no longer a good
      model of the current local harness on this corpus
    - dominant remaining skip buckets are structural, not red:
      - `typeok_uses_unbounded_seq = 16`
      - `missing_typeok_body = 6`
      - `typeok_init_state_space_too_large = 5`
      - `typeok_missing_variable_domain_delivered = 4`
      - smaller one-off missing-domain / infinite-domain buckets after that
    - protocol direct-domain recovery attempt on the clustered
      `typeok_missing_variable_domain_delivered` family:
      - patched local modules:
        `AlternatingBit`, `GoBackN`, `SelectiveRepeat`, `StopAndWait`
        to add an explicit finite `DeliveredPrefixes` domain
      - focused family result:
        `outputs/autoprover/protocol_delivered_family_recheck4.summary.json`
        -> `1 skeleton_emitted / 3 not_inductive / 0 tlc_error`
      - `SelectiveRepeat` crossed cleanly to `skeleton_emitted`
      - the other three became explicit semantic holdouts instead of structural
        skips:
        `AlternatingBit`, `GoBackN`, `StopAndWait`
    - refreshed full local Diamond rerun after those protocol edits:
      `outputs/autoprover/live_full_diamond_gen_current_skip_tlaps_afterfix1.summary.json`
      -> `150 skeleton_emitted / 47 skipped / 3 not_inductive / 0 tlc_error`
    - refreshed again on 2026-06-28 after the later protocol / memory-cache /
      workflow fixes:
      `outputs/autoprover/live_full_diamond_gen_current_skip_tlaps_afterfix2.summary.json`
      -> `153 skeleton_emitted / 47 skipped`
      - practical meaning:
        the stale 3-protocol semantic frontier is no longer current; the live
        local 200-module Diamond lane is now 3 modules greener than the last
        durable snapshot
    - practical frontier now:
      the Diamond-generated local lane is still red-free in the TLC-error sense,
      but it now exposes a smaller, sharper semantic boundary in the 3 protocol
      holdouts above
  - 2026-06-28 corpus expansion:
    - initialized the `data/FormaLLM` submodule locally at
      `e74c2edb88c59d5b2d0bf46a3a2344eea5fb8cfa`
    - new processed corpus:
      `data/processed/formalllm_eval_v1.jsonl`
      with summary
      `data/processed/formalllm_eval_v1.summary.json`
      -> `205` canonical FormaLLM prompt/spec rows across `71` families and
      `191` unique module names
    - builder:
      `scripts/build_formalllm_eval_corpus.py`
      uses the canonical per-family `*.json` metadata entries as the dataset
      boundary, prefers `*_clean` prompt/spec files, falls back to grounded
      family aliases for `MC*` wrappers, and uses README-based fallback only
      when the public repo truly lacks external prompt text
    - repo wiring updated:
      `scripts/preflight_tla_prover_corpora.py` now includes
      `formalllm_eval_v1.jsonl` in the default preflight set, and
      `scripts/build_tla_prover_manifest.py` publishes the artifact as
      `full_formalllm_prompt_eval_dataset`
    - verification:
      `python3 -m pytest tests/test_build_formalllm_eval_corpus.py tests/test_build_tla_prover_manifest.py tests/test_preflight_tla_prover_corpora.py tests/test_check_tla_prover_pr_ready.py -q`
      -> `12 passed`
      and
      `python3 scripts/check_tla_prover_pr_ready.py --scan-only --include-untracked-scripts`
      -> `ok: true`
  - 2026-06-28 operator note:
    - do not make further Sophia auth attempts from this shell/session for now
    - repeated failed attempts caused a lockout
    - if fresh Sophia access is needed later, contact the user out of band for fresh credentials instead of retrying stale credentials
    - commit frequently during long prover/handoff work so sanitation and
      recovery points stay small and easy to inspect
    - one-time credential probe succeeded at the auth layer on 2026-06-28
      and recovered live `161031` existence evidence with a single SSH login:
      `qstat` showed `161031.sophia-pbs-01.lab.alcf.anl.gov` in terminal
      state `F`, and the remote checkout still had all expected files:
      `outputs/manifests/tla_prover_full_dataset_progress.json`,
      `outputs/autoprover/full_dataset_smoke_161031.jsonl`,
      `outputs/autoprover/full_dataset_smoke_161031.summary.json`,
      `outputs/logs/autoprover_full_dataset_smoke_161031.sophia-pbs-01.lab.alcf.anl.gov.log`,
      and `outputs/logs/autoprover_full_dataset_smoke.log`
    - the failed part of that probe was packaging, not auth: the first
      one-shot tar command mixed `-C "$tmpdir"` with repo-relative file paths
      and therefore only captured `qstat_161031.txt` plus
      `file_status_161031.json` into
      `outputs/manifests/sophia_161031_capture.tgz`
    - `scripts/collect_tla_prover_direct_results.sh` now supports
      `CHATTLA_REMOTE_SINGLE_SESSION=1`, which uses `expect` to establish one
      password-authenticated SSH control-master session and reuses its
      `ControlPath` for the subsequent qstat/rsync pulls; use that mode for
      future single-use Sophia credentials
