# ChatTLA Run Memory

Current operational facts for the long-Ralph training push:

- `ssh plantain` works and lands on `plantain.cs.luc.edu` as user `espencer2`.
- `ssh polaris` works and lands on `polaris-login-01` as user `eric-spencer`.
- `aisec-102.cs.luc.edu` is now the default cloud-only launch host and artifact store target for long runs.
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
- `CHATTLA_CLOUD_ONLY=1`, `CHATTLA_SKIP_GRPO=1`, `CHATTLA_INITIAL_PROVIDER=teacher`, `CHATTLA_REPAIR_PROVIDER=teacher`, and `CHATTLA_LOCAL_MODEL_AUDIT=0` keep long Ralph off local GPU generation on `aisec-102`.

Canonical launch sequence on `aisec-102`:

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
export CHATTLA_AISEC_STORE=aisec-102.cs.luc.edu:~/chattla-long-runs
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
