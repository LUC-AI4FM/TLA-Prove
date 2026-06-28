# GRPO Action Loop Strategy

**Date**: 2026-06-23  
**Goal**: Turn the first successful Polaris GRPO action run into a higher-signal
overnight loop that can actually move the adapter.

## 2026-06-24 Sophia phase-2 result

Sophia job `160107` completed the full fresh-scheduler continuation from the
Polaris `checkpoint-80` adapter.

- Machine: Sophia `by-gpu`, 4x A100 on `a Sophia GPU node`
- Input adapter: `outputs/checkpoints_grpo_action_tok1200_g4/checkpoint-80`
- Output: `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia`
- Final checkpoint: `checkpoint-240`
- Saved checkpoints: every 20 steps from `checkpoint-20` through
  `checkpoint-240`
- Runtime: `3521s` training, about `14.7s/step`
- Fresh LR schedule worked: first LR `3e-6`, final LR `1.25e-8`
- Mean reward: `0.0609`
- Reward was nonzero on `162/240` logged steps
- Reward std was nonzero on `129/240` logged steps
- Mean `frac_reward_zero_std`: `0.4625`
- Mean KL: `0.002424`; max KL: `0.0085`
- Mean clipped ratio: `0.9792`
- Only `20/240` logged steps had clipped ratio below `1.0`
- Only `20/240` logged steps had any naturally terminated completions

Grade: **A- infrastructure, C+/B- learning**.

Interpretation: the Sophia lane is viable, the adapter-only warm start fixed the
near-zero-LR full-resume problem, and reward variance is present often enough
that GRPO is not completely blind. The remaining blocker is the output contract:
the model still usually spends the entire 192-token budget, so more long runs
will mostly accumulate capped generations unless we inspect and tighten what it
is asked to emit.

## Current grade

Overall after Sophia phase 2: **A- as an engineering run, C+/B- as a learning
run**.

The latest run proved that the trainer, Polaris environment, save path, and
action-harness reward loop can complete end to end. Sophia also proved that a
second A100 lane can run the same code faster than the stuck Polaris
preemptable path. It still did not prove that continuing this exact recipe is
the best use of GPU time, because clipped completions remain the dominant
failure mode.

## Evidence

| Attempt | Result | Main lesson |
|---------|--------|-------------|
| DPO job `7212589` | Failed during model load with CUDA illegal memory access | The initial DPO path was not a useful overnight bet on Polaris. |
| GRPO job `7212595` | Reached step 16/50, then OOM allocating ~22.7 GiB | Model load was fine; later prompt/generation memory was the failure mode. |
| GRPO short job `7213633` | Completed 40/40 and saved checkpoints 5 through 40 | The action-loop path is runnable with shorter inputs and early saves. |
| Polaris debug chunks `7214626`, `7214655` | Reached `checkpoint-80` | Debug chunks were more reliable than stuck preemptable jobs. |
| Sophia job `160107` | Completed fresh-scheduler phase to `checkpoint-240` | Sophia is a good CUDA lane; local/offline HF cache is required on compute nodes. |

Latest successful run details:

- Corpus: `data/processed/diamond_sft_v3_short.jsonl`
- Loaded action harnesses: `571`
- Output: `outputs/checkpoints_grpo_action_short_overnight`
- Steps: `40`
- Generations: `2`
- Completion cap: `256`
- Saved: `checkpoint-5`, `checkpoint-10`, `checkpoint-15`, `checkpoint-20`,
  `checkpoint-25`, `checkpoint-30`, `checkpoint-35`, `checkpoint-40`, plus final
  adapter files at the output root.

Observed learning problems:

- `completions/clipped_ratio` stayed effectively `1.0`, so the model almost
  always ran into the completion cap.
- `completions/mean_terminated_length` stayed `0`, which means generated
  samples were not naturally ending under the current output contract.
- Rewards were usually `0`, `0.075`, or `0.15`.
- `reward_std` was often `0`, and many batches had `frac_reward_zero_std=1`.
- KL stayed tiny, roughly `0.001` to `0.006`; losses were around `1e-4`.

Interpretation: this was mostly an integration success, not a reinforcement
learning success. The next loop should optimize for reward variance and
inspectable completions before spending a full night on scale.

Scheduler note from the latest incident:

- the main job was terminated by PBS with `Exit_status = 143`;
- the debug hedge completed cleanly;
- the main run did not show a Python exception or OOM before the scheduler
  stopped it.

This points to queue/preemption behavior, not a bad training command. The
strategy should assume preemption and make every submission rerunnable.

## Root causes

1. The first OOM was caused by generation-time memory, not the scheduler or a
   basic model-load problem.
2. The short-corpus run avoided the OOM but still allowed prompts and answers
   that consumed the whole completion budget.
3. Character-count filtering is too crude. The next corpus should be filtered by
   the actual tokenizer/chat-template prompt length.
4. `num_generations=2` is survivable but weak for GRPO. It gives too little
   within-prompt comparison signal when rewards are sparse.
5. We need sample logging or frequent evaluation so we can tell whether clipped
   answers are malformed, verbose, stuck in commentary, or simply too long.

## Next-run objective

Run one more overnight attempt that is still conservative on memory but better
for learning signal:

- filter the action corpus by actual prompt tokens;
- increase `num_generations` back to `4`;
- lower completion length to reduce memory pressure;
- save early enough that a partial run is useful;
- make the PBS job rerunnable and split training into smaller checkpoints so a
  SIGTERM only costs a slice of progress;
- use explicit health gates so we can stop bad loops quickly next time.

## Completed next attempt

Polaris reached `checkpoint-80` in debug chunks. Do not continue the same
trainer resume past that point as the default learning path: the optimizer and
LR scheduler state are also restored, and the LR is at or near floor by step
80. For a new phase, warm-start only the adapter weights and reset the trainer
state.

Proposed next-phase run:

```bash
python -u -m scripts.train_rl_20b \
  --model EricSpencer00/chattla-20b \
  --corpus data/processed/diamond_sft_v3_action_tok1200.jsonl \
  --output-dir outputs/checkpoints_grpo_action_tok1200_g4_phase2 \
  --max-steps 60 \
  --num-generations 4 \
  --max-completion-length 192 \
  --save-steps 10 \
  --learning-rate 3e-6 \
  --beta 0.04 \
  --adapter-checkpoint outputs/checkpoints_grpo_action_tok1200_g4/checkpoint-80
```

Why this shape:

- `tok1200` reduces prompt memory using the tokenizer that the model actually
  sees.
- `num_generations=4` should improve per-prompt reward ranking and variance.
- `max_completion_length=192` reduces generation memory after increasing
  generations.
- `save_steps=10` preserves useful adapters even if the job is preempted or
  fails after the early phase.
- `--adapter-checkpoint` loads the learned LoRA weights but starts a fresh
  optimizer and LR schedule, avoiding the near-zero-LR trap from full trainer
  resume.
- `max_steps=60` is a fresh phase length, not an absolute global step target.

Operationally, the more durable shape is likely:

1. run in `preemptable` for throughput;
2. set the job rerunnable;
3. checkpoint frequently;
4. full-resume within a phase after interruption, but start each new phase from
   the latest adapter with a fresh scheduler.

## Machine choice

Sophia is the better second lane tonight.

- Sophia `by-gpu` gave immediate 4x A100 access in smoke tests.
- The existing `frs` conda environment works on Sophia compute nodes with CUDA.
- The shared checkpoint path can see the Polaris `checkpoint-80` adapter.
- Model load on Sophia was slower than Polaris, roughly five minutes in the
  smoke run, so avoid tiny two-step jobs unless debugging.
- Aurora is less attractive for this exact script because it is Intel/PVC/XPU
  rather than the current CUDA/NVIDIA path.

Use Sophia for real chunks when Polaris preemptable is stuck on `queue_tags`.
Use Polaris debug for short verified chunks when available.

Sophia operational lessons from job `160107`:

- Use the local cached model snapshot path on Sophia compute nodes, not the HF
  repo ID. The first attempt (`160105`) hung in an outbound HTTPS connection
  while loading `EricSpencer00/chattla-20b`.
- Set `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and
  `HF_DATASETS_OFFLINE=1` for Sophia training jobs.
- Use Sophia filesystem names in PBS: `filesystems=home_fs:grand_fs`.
- Do not request `place=scatter` on Sophia `by-gpu`; PBS rejects it.
- Keep using `--adapter-checkpoint` for new phases. Use
  `--resume-from-checkpoint` only to continue an interrupted phase with the
  same scheduler.

## Next decision

Do **not** launch another full 240-step continuation with the same prompt,
completion cap, and reward only. The next useful run is a diagnostic run that
answers what the model is writing and whether a shorter output contract can
reduce clipping without destroying reward.

Recommended order:

1. Add completion sample logging to `scripts/train_rl_20b.py`.
2. Evaluate `checkpoint-80`, `checkpoint-160`, and `checkpoint-240` on the same
   fixed action holdout.
3. Run a short Sophia diagnostic matrix from `checkpoint-240`, not a long
   overnight run:
   - completion caps: `96`, `128`, `160`
   - steps: `20` per cap
   - generations: `4`
   - LR: `2e-6` to `3e-6`
   - save every `10`
   - log raw completions for at least 8 prompts per run
4. Choose the next real phase only after reading samples and holdout scores.

Expected promote condition for the next real phase:

- clipped ratio mean below `0.8`;
- reward std nonzero on at least half of logged steps;
- holdout score does not regress versus `checkpoint-80`;
- sampled completions are compact action-level artifacts, not full-spec or
  commentary continuations.

If the diagnostic matrix still clips at `160`, stop tuning length and change the
prompt/output format first. The current model is likely obeying the old SFT
habit of continuing a full TLA+ spec.

## 2026-06-24 active diagnostic

Submitted the next diagnostic matrix to Sophia:

- Job: `160220.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `single-node`
- Requested resources: `1:ngpus=4:ncpus=128:mem=480gb`
- Walltime: `02:00:00`
- Status at submit check: queued, `Not Running: Insufficient amount of resource:
  queue_tags`
- Script: `scripts/qsub_grpo_sophia_diag_caps_single_node.pbs`
- Base model: local cached `EricSpencer00/chattla-20b` snapshot
- Adapter: `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240`
- Corpus: `data/processed/diamond_sft_v3_action_tok1200.jsonl`
- Runs: caps `96`, `128`, `160`, each `20` GRPO steps with `4` generations
- Sample logs:
  `outputs/logs/grpo_diag_cap{cap}_single_node_${PBS_JOBNUM}_samples.jsonl`
- Main log:
  `outputs/logs/grpo_diag_caps_single_node_${PBS_JOBNUM}.log`

When it starts, first verify:

- the job sees at least 4 A100 GPUs;
- `scripts.train_rl_20b --help` on Sophia includes `--sample-log-path`;
- cap `96` reaches at least step 1;
- the cap `96` sample JSONL has rows with `raw_completion` and
  `extracted_next`.

When it finishes, parse:

- clipped ratio mean per cap;
- reward mean and reward-std-nonzero count per cap;
- termination count per cap;
- several raw samples per cap, especially zero-reward clipped samples.

Parser command:

```bash
python scripts/analyze_grpo_diag_caps.py \
  --log outputs/logs/grpo_diag_caps_single_node_160220.log \
  --samples outputs/logs/grpo_diag_cap*_single_node_160220_samples.jsonl
```

Current scheduler note:

- As of `2026-06-24 18:26 UTC`, job `160220` is still queued with the same
  `queue_tags` blocker.
- A 2-GPU single-node test (`160224`) also queued on `queue_tags`, so the issue
  is not specific to the 4-GPU request.
- A 1-GPU single-node job (`160218`) did start, but it exposed only one A100 and
  was killed before training because that script expected the full 4-GPU matrix.
- `qstat -answ1` shows active Sophia `by-gpu` placements using
  `1:ngpus=1:ncpus=32:mem=120gb`, and `pbsnodes -aSj` shows free full GPU nodes,
  so the current blocker looks like queue tag/routing/account fit rather than
  raw absence of GPUs.
- Added a scheduler hedge:
  `scripts/qsub_grpo_sophia_diag_caps_1gpu_probe.pbs`.
- Submitted the hedge as job `160226.sophia-pbs-01.lab.alcf.anl.gov`.
- As of `2026-06-24 18:29 UTC`, `160226` is also queued on `by-gpu` with
  `Not Running: Insufficient amount of resource: queue_tags`.
- As of `2026-06-24 18:32:52 UTC`, `160226` started on
  `a Sophia GPU node/0*32` as a 1-GPU A100 40 GB job.
- As of `2026-06-24 18:35 UTC`, `160226` is still running and loading model
  weights for cap `96`; no sample JSONL has been produced yet.
- At `2026-06-24 18:38 UTC`, `160226` failed during base model load on the
  one-GPU A100 40 GB slice:
  `torch.OutOfMemoryError: Tried to allocate 33.27 GiB ... 5.77 GiB is free`.
  That confirms the 20B bf16 path needs at least a 2-GPU split on Sophia.
- Added the next fallback:
  `scripts/qsub_grpo_sophia_diag_caps_2gpu_probe.pbs`, using
  `select=1:ngpus=2:ncpus=64:mem=240gb`.
- Submitted the 2-GPU fallback as job
  `160230.sophia-pbs-01.lab.alcf.anl.gov`.
- As of `2026-06-24 18:39 UTC`, `160230` is queued on `by-gpu` with
  `Not Running: Insufficient amount of resource: queue_tags`.
- Corrected the original 4-GPU `by-gpu` diagnostic script:
  `scripts/qsub_grpo_sophia_diag_caps.pbs` now requests
  `select=1:ngpus=4:ncpus=128:mem=480gb` instead of `select=4`. This matches
  the resource shape seen in successful Sophia 4-GPU by-gpu jobs.
- Submitted the corrected 4-GPU by-gpu diagnostic as job
  `160232.sophia-pbs-01.lab.alcf.anl.gov`.
- As of `2026-06-24 18:41 UTC`, `160232` is queued on `by-gpu` with
  `Not Running: Insufficient amount of resource: queue_tags`.
- Live queue policy: keep `160230` as the smaller 2-GPU contract probe and keep
  one 4-GPU diagnostic lane. If either 4-GPU job starts, cancel or ignore the
  other duplicate 4-GPU lane to avoid wasting GPU time.
- Watcher policy: the Codex heartbeat now checks every 5 minutes. If `160220`
  or `160232` starts, it should cancel the other queued 4-GPU diagnostic before
  it also starts. Keep `160230` because it answers a different question: whether
  the shorter two-cap contract probe can run on a smaller 2-GPU slice.
- Queue observation at `2026-06-24 18:42 UTC`: active by-gpu jobs are occupying
  the available `prod` slices as they open, including 1-GPU and 2-GPU jobs on
  `a Sophia GPU node` and 4-GPU jobs on `a Sophia GPU node`. Our queued jobs are still
  blocked on contiguous `queue_tags` resources, not on allocation exhaustion.
- The apparently free nodes are not usable by these jobs: `a Sophia GPU node` is
  tagged `infer-svc-test`, `a Sophia GPU node/18/22` are tagged `infer-svc`, and
  `a Sophia GPU node` is tagged `bigmem`. The corresponding queues are ACL-limited
  or disabled, so EVITA should stay on the `prod` queues.
- Tried to shorten queued job walltimes to `01:00:00` with `qalter`, but PBS
  rejected the changes with `Exception in account_check hook encountered`; the
  submitted jobs remain at `02:00:00`.
- At `2026-06-24 18:46 UTC`, the scheduler started both:
  - `160220` 4-GPU single-node diagnostic on `a Sophia GPU node`
  - `160230` 2-GPU by-gpu contract probe on `a Sophia GPU node`
- Submitted a one-GPU quantized inference-only contract probe as
  `160238.sophia-pbs-01.lab.alcf.anl.gov`; it started at
  `2026-06-24 18:48 UTC` on `a Sophia GPU node`.
- Canceled duplicate queued 4-GPU by-gpu diagnostic `160232` after `160220`
  started, to avoid wasting another 4-GPU diagnostic slot.

Quantized probe purpose:

- Script: `scripts/probe_action_contract_quantized.py`
- PBS: `scripts/qsub_sophia_quantized_contract_probe.pbs`
- Job: `160238`
- This is inference-only, not training and not promotion-grade proof.
- It loads the base model in 4-bit with the `checkpoint-240` adapter and scores
  generated samples with the same per-action TLC reward.
- It writes:
  - `outputs/eval/grpo_quant_contract_probe_160238.jsonl`
  - `outputs/eval/grpo_quant_contract_probe_160238_summary.json`
- Use this to inspect whether caps `96` and `128` produce compact `Next`
  operators while the real GRPO diagnostics run.
- First quantized attempt `160238` failed before generation because
  `device_map="auto"` dispatched some 4-bit modules to CPU/disk, which
  Transformers rejects for this bitsandbytes path. Patched
  `scripts/probe_action_contract_quantized.py` to default to
  `device_map={"": 0}` for the one-GPU probe.
- Submitted quantized retry as `160240.sophia-pbs-01.lab.alcf.anl.gov`.
- `160240` also failed before generation. Forcing `device_map={"": 0}` got past
  the CPU/disk dispatch error, but after loading all weights the model occupied
  about `38.6 GiB` on the 40 GB A100 and Transformers allocator warmup tried to
  allocate another `37.86 GiB`, producing CUDA OOM.
- Stop the one-GPU quantized lane for this model/checkpoint. It is not a useful
  path for contract evidence on Sophia A100 40 GB.

Early cap-96 diagnostic evidence:

- `160230` 2-GPU probe completed cap `96`:
  - steps: `12`
  - clipped mean: `1.0`
  - naturally terminated completions: `0`
  - reward mean: `0.00625`; max reward: `0.075`
  - reward std nonzero: `1/12`
  - sample rows: `24`
  - empty extracted `Next`: `23/24`
- `160230` 2-GPU probe completed cap `128`:
  - steps: `12`
  - clipped mean: `1.0`
  - naturally terminated completions: `0`
  - reward mean: `0.00625`; max reward: `0.075`
  - reward std nonzero: `1/12`
  - sample rows: `24`
  - empty extracted `Next`: `23/24`
- `160230` recommendation: do not promote. Increasing from cap `96` to `128`
  did not reduce clipping or materially improve extraction/reward.
- `160220` 4-GPU diagnostic partial cap `96` at 15 logged steps:
  - clipped mean: `1.0`
  - naturally terminated completions: `0`
  - reward mean: `0.025`; max reward: `0.1125`
  - reward std nonzero: `6/15`
  - sample rows: `60`
  - empty extracted `Next`: `50/60`
- `160220` completed cap `96` and partially reached cap `128`; early cap `128`
  still has clipped mean `1.0`, zero natural terminations, and many empty
  extracted `Next` samples. Let `160220` finish the short cap matrix for the
  final record, but do not start another continuation from this recipe.
- `160240` produced no sample JSONL.
- Sample inspection shows the dominant failure: completions start with
  `analysis...` prose and often never emit a usable `Next ==` block inside the
  cap. A few partial `Next == ...` lines appear, but most are commentary about
  what the action should be.

## 2026-06-25 full-spec diagnostic postmortem

The corrected full-spec lane is alive, but the last visible job (`160391`) was
not a clean signal run.

- `qstat -xf 160391` shows `job_state = F`, `Exit_status = 271`, and the PBS
  comment says the job was terminated by `<user>@sophia-login-02`.
- The runtime log lives under the old home-tree path:
  `/home/<user>/ChatTLA/outputs/logs/grpo_fullspec_diag_160391.log`.
- The log shows the old wrapper layout:
  `OUT=outputs/checkpoints_grpo_fullspec_diag_160391` and
  `SAMPLES=outputs/logs/grpo_fullspec_diag_160391_samples.jsonl`.
- There is no explicit `No space left on device` line in the visible logs.
- Home quota on Sophia is not the bottleneck: `df -h /home/<user>`
  reports roughly `160T` free and `quota -s` reports no limited resources.
- The grand filesystem is much fuller but still usable:
  `/lus/grand` shows roughly `15T` free and about `91%` used.

Interpretation:

- This looks more like a stale-wrapper / cleanup incident than a genuine disk
  exhaustion failure from the current corrected lane.
- The real fix is still the one we already made: keep the run and samples under
  `/grand/<ACCOUNT>/<user>/chattla_artifacts/fullspec/${PBS_JOBNUM}` and
  leave the home-tree outputs out of the training path.
- To make future postmortems sharper, the PBS wrapper should print `df -h` for
  both home and grand before training starts.

Implication:

- Do **not** promote cap `96`.
- If caps `128` and `160` still show analysis prose, stop cap-tuning and change
  the output contract first.
- Next run should either train/evaluate with a generation prompt that begins in
  the final/action channel, or postprocess/score only final-channel content if
  Harmony channel markers are present. The current reward mostly teaches around
  the old analysis habit instead of forcing direct `Next ==` emission.
- Because both the 4-GPU `single-node` diagnostic and 1-GPU `by-gpu` probe
  initially blocked on the same scheduler resource, the queue delay looked like
  queue-tag/account/routing fit, not simply the number of GPUs requested. The
  later `160226` placement confirms the smaller by-gpu shape can break through.
- `sbank-list-allocations` shows EVITA still has about `1,999.4` Sophia
  node-hours available, so this does not look like an exhausted allocation.
- PBS estimated `160226` would place on `a Sophia GPU node` and start around
  `2026-06-24 18:34:39 UTC`; wait for that window before canceling or changing
  this probe.

## 2026-06-25 replacement diagnostic

Submitted a clean replacement job after the stale-wrapper postmortem:

- Job: `160396.sophia-pbs-01.lab.alcf.anl.gov`
- Host: `a Sophia GPU node`
- Artifact root:
  `/grand/<ACCOUNT>/<user>/chattla_artifacts/fullspec/160396`
- Log snapshot at start:
  home `/home` about `34%` used, grand `/lus/grand` about `91%` used
- The job is now loading weights with the corrected grand-backed wrapper.

This is the run to watch for the next real signal.

Early signal from `160396`:

- step 1: reward mean `0.645`, reward std `0.294`, clipped ratio `0.25`,
  mean terminated length `538`
- step 2: reward mean `0.25`, reward std `0.116`, clipped ratio `0.25`
- sample log already contains clean module matches with no syntax issues on the
  first few rows

Interpretation:

- the corrected wrapper is now producing useful completions instead of the old
  home-tree artifact failure mode;
- the current reward shaping is at least capable of producing some gold-tier
  samples, so the next judgment point is whether that holds across the full
  6-step diagnostic and the holdout eval;
- reward shaping has now been tightened so the next bounded pass can test
  whether syntax-hygiene regressions actually get clipped.

Full-batch result from `160396`:

- completed cleanly in `298.5s` over 6 steps;
- final step reward mean `0.1962`, reward std `0.05822`;
- overall sample mean reward `0.345625`;
- every sample started with the correct module name;
- 23/24 samples had a terminator;
- 10/24 samples still had syntax issues;
- issue mix: `typed_variables` 4, `empty_unchanged` 4,
  `typed_constants` 3, `forward_reference_terminating` 2.

Decision:

- patch reward shaping so syntax-hygiene-violating completions cannot keep
  winning high partial-credit scores;
- keep the next phase bounded, because the model is learning something real
  but it is still too willing to spend reward on malformed full-spec forms;
- do not stop yet, but do not promote anything from this diagnostic alone.

Replacement run:

- Job: `160400.sophia-pbs-01.lab.alcf.anl.gov`
- Status: running on `a Sophia GPU node`
- Purpose: same bounded full-spec diagnostic under the tightened reward cap
  so we can compare the batch shape directly against `160396`.

Early signal from `160400`:

- step 1: reward mean `0.645`, reward std `0.294`, clipped ratio `0.25`,
  mean terminated length `538`
- step 2: reward mean `0.21`, reward std `0.08083`, clipped ratio `0.25`,
  mean terminated length `625`

Interpretation:

- the tightened cap is taking effect on the weaker batch, but the run still
  clips hard and keeps producing long completions;
- this is evidence to keep the bounded diagnostic running, not evidence to
  promote or to stop;
- if the final batch still looks like `160396`, the next move should be a
  prompt/channel contract change rather than another reward-only tweak.

Full-batch result from `160400`:

- completed cleanly in `310.7s` over 6 steps;
- final step reward mean `0.1575`, reward std `0.035`;
- final step clipped ratio `0.5`;
- overall sample mean reward `0.3915`;
- 20 sample rows logged at the time of the mid-run snapshot, with only `3`
  syntax-issue rows there;
- issue mix in the mid-run snapshot: `typed_constants` 2, `typed_variables` 0,
  `empty_unchanged` 0, `forward_reference_terminating` 0;
- the final batch still hit the 1024-token cap, so the tightened reward helped
  hygiene but did not solve the long-form completion habit.

Decision:

- stop reward-only tuning for now;
- the next experiment should change the output contract / channel prompt so the
  generation starts in a direct artifact shape, not another full-spec prose
  continuation;
- use `reasoning_effort=none` in the full-spec trainer/eval wrappers and make
  the prompt explicitly demand that the first generated bytes are
  `---- MODULE`;
- keep the current model artifacts, but do not promote or publish from this
  diagnostic alone.

## 2026-06-25 contract diagnostic

Launched the next bounded full-spec diagnostic with the contract change wired
through the trainer/eval wrappers and PBS launcher:

- Job: `160404.sophia-pbs-01.lab.alcf.anl.gov`
- Host: `a Sophia GPU node`
- Purpose: test whether `reasoning_effort=none` plus the direct-start prompt
  reduces prose preambles and improves the full-spec sample shape
- Script: `scripts/qsub_grpo_sophia_fullspec_diag.pbs`
- Status at submit: running

Early signal:

- the first GRPO batch starts directly with `---- MODULE` on every sampled
  completion seen so far;
- first-step reward mean is `0.5625` with `completions/mean_length = 314.5`;
- the same run still produced a second batch at `completions/mean_length = 475`,
  so the contract change may be fixing the opening shape without fully solving
  long-output drift yet;
- no syntax-issue rows were present in the first few logged samples.

Full-batch result:

- completed all 6 steps cleanly;
- the run stayed on-contract the whole way: `starts_module = 24/24`,
  `module_match = 24/24`, `has_terminator = 22/24`;
- sample mean reward was `0.328333`;
- `7/24` samples still carried syntax issues, so the prompt change fixed the
  opening shape but did not fully eliminate malformed bodies;
- mean sample length was `1521.62` chars, which is shorter than the old prose
  habit but still not truly compact.

Decision:

- keep the direct-start contract and warm-start from the diagnostic adapter;
- launch a bounded follow-up phase rather than going back to reward-only
  tuning or restarting from the base model;
- do not promote or publish yet, because the body-level syntax hygiene still
  needs another check.

Follow-up submission:

- the first PBS submit ignored the adapter env vars, so I killed that base-model
  run and resubmitted with explicit `qsub -v` exports;
- warm-start job: `160408.sophia-pbs-01.lab.alcf.anl.gov`;
- adapter checkpoint:
  `/grand/<ACCOUNT>/<user>/chattla_artifacts/fullspec/160404/checkpoints_grpo_fullspec_diag_160404`;
- target shape: 30 steps, lower temperature, same direct-start contract.

Early warm-start signal:

- `160408` is now in-flight on `a Sophia GPU node`;
- the first four logged sample rows are all clean: `starts_module = 4/4`,
  `has_terminator = 4/4`, `module_match = 4/4`, `syntax_issue_rows = 0/4`;
- those first rows all scored `1.0`, which is the first evidence that the
  diagnostic adapter can transfer the direct-start contract into a stronger
  warm-start phase rather than merely repeating the base run;
- continue watching for whether that stays true once the batch gets deeper and
  the reward stops being so perfectly sparse.

Full warm-start result:

- `160408` completed cleanly in `30` steps;
- the contract held through the entire run: `starts_module = 24/24`,
  `has_terminator = 24/24`, `module_match = 24/24`;
- syntax-hygiene regressions were reduced but not gone: `3/24` rows still had
  syntax issues;
- mean sample reward was `0.487917`, and mean completion length was `1154.67`
  chars, which is materially better than the earlier long-form drift but still
  leaves room for tightening;
- next move is a holdout eval of `160408` against the exact-prompt base and
  the three phase checkpoints before deciding whether this is promotion-grade
  or just a good-but-not-yet-final step forward.

One-GPU probe purpose:

- This is **not** a promotion-grade continuation.
- It runs caps `96` and `128`, `12` steps each, `2` generations, from the same
  Sophia `checkpoint-240` adapter.
- It uses the by-gpu single-slice shape:
  `select=1:ngpus=1:ncpus=32:mem=120gb`.
- It should produce raw completion JSONL quickly if placed, answering whether
  shorter caps produce compact action-level completions before the 4-GPU
  diagnostic starts.

Probe parser command after completion:

```bash
python scripts/analyze_grpo_diag_caps.py \
  --log outputs/logs/grpo_diag_caps_1gpu_probe_${PBS_JOBNUM}.log \
  --samples outputs/logs/grpo_diag_cap*_1gpu_probe_${PBS_JOBNUM}_samples.jsonl
```

Decision after this diagnostic:

- If cap `128` or `160` has clipped mean below `0.8` without reward collapse,
  promote that cap to a real fresh-scheduler phase.
- If all caps still clip heavily or samples show full-spec continuation, change
  the prompt/output contract before more training.
- If rewards collapse at `96`, keep `96` only as a diagnostic bound, not a
  training cap.

## 2026-06-24 diagnostic final result

Sophia job `160220` completed the full 4-GPU single-node cap matrix. Do **not**
promote any checkpoint from this matrix to a real phase.

Final parser command:

```bash
python scripts/analyze_grpo_diag_caps.py \
  --log outputs/logs/grpo_diag_caps_single_node_160220.log \
  --samples outputs/logs/grpo_diag_cap*_single_node_160220_samples.jsonl
```

Final metrics:

| Cap | Steps | Clipped mean | Terminated nonzero | Reward mean | Reward max | Reward std nonzero | Empty extracted `Next` |
|-----|-------|--------------|--------------------|-------------|------------|--------------------|------------------------|
| `96` | `20` | `1.0000` | `0` | `0.036875` | `0.25` | `8/20` | `66/80` |
| `128` | `20` | `0.9875` | `1` | `0.051875` | `0.325` | `10/20` | `58/80` |
| `160` | `20` | `1.0000` | `0` | `0.0575` | `0.2875` | `13/20` | `55/80` |

Sample audit:

- All `240/240` logged samples start with `analysis...`.
- Only `13/80`, `22/80`, and `25/80` samples for caps `96`, `128`, and `160`
  contain `Next ==` anywhere in the raw completion.
- The first samples are explanations like "analysisWe need to write Next
  operator..." rather than bare TLA+ action definitions.

Decision:

- Stop cap tuning for this recipe. The failure is not primarily the cap; it is
  the output contract/channel habit.
- The next loop should be a **small direct-output contract diagnostic**, not a
  long continuation. It should keep the same checkpoint, corpus, reward, and
  sample logging, but change the action prompt so generation starts directly
  with a bare `Next ==` artifact.

Recommended next-loop design:

1. Change the per-action GRPO prompt from `Reasoning: medium` to a direct
   answer contract, preferably `Reasoning: none`, with explicit text that the
   first generated bytes must be `Next ==`.
2. Add a short reward precheck or analysis penalty only if needed after the
   prompt diagnostic. The first experiment should isolate the prompt/channel
   variable.
3. Run a short Sophia diagnostic from
   `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240`:
   caps `96` and `128`, `12` steps each, `4` generations, sample logging every
   reward call.
4. Promote only if samples no longer start with `analysis`, empty extracted
   `Next` falls below `25%`, clipped mean drops below `0.8`, and reward does
   not collapse.

Abort gates for the direct-output diagnostic:

- kill after cap `96` if more than half of samples still start with `analysis`;
- kill after cap `96` if empty extracted `Next` is still above `50%`;
- do not launch any overnight continuation until the direct-output diagnostic
  has compact action-level samples.

## 2026-06-24 direct-output diagnostic

Submitted the direct-output contract diagnostic as the next loop:

- Job: `160244.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `single-node`
- Requested resources: `1:ngpus=4:ncpus=128:mem=480gb`
- Walltime: `01:00:00`
- Script: `scripts/qsub_grpo_sophia_direct_contract_diag.pbs`
- Prompt mode: `CHATTLA_ACTION_PROMPT_MODE=direct`
- Prompt role: `developer` instead of the legacy action-dataset `system` role
- Prompt reasoning: `Reasoning: none`
- Adapter:
  `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240`
- Corpus: `data/processed/diamond_sft_v3_action_tok1200.jsonl`
- Runs: caps `96` and `128`, each `12` GRPO steps with `4` generations
- Main log: `outputs/logs/grpo_direct_contract_160244.log`
- Sample logs:
  `outputs/logs/grpo_direct_cap{cap}_160244_samples.jsonl`

Status at launch check:

- `160244` started immediately at `2026-06-24 19:06:15 UTC` on
  `a Sophia GPU node/0*128`.
- The job sees four A100 40 GB GPUs.

Parser command after completion:

```bash
python scripts/analyze_grpo_diag_caps.py \
  --log outputs/logs/grpo_direct_contract_160244.log \
  --samples outputs/logs/grpo_direct_cap*_160244_samples.jsonl
```

This job answers one narrow question: does moving the action prompt to
developer-role, no-analysis, direct `Next ==` output materially reduce the
`analysis...` failure and improve extraction? If not, do not keep spending GRPO
steps; add an explicit analysis-start penalty or move to final-channel-aware
generation/extraction.

Early result:

- `160244` was aborted after cap `96` produced `16` sample rows.
- `16/16` samples still started with `analysis`.
- `0/16` samples started with `Next ==`.
- `4/16` contained `Next ==` somewhere in the raw completion.
- `12/16` had empty extracted `Next`.
- Mean sample reward was `0.0375`.

Interpretation:

- Prompt wording alone does not solve this. The model is following the Harmony
  chat template and choosing the analysis channel after the default
  `add_generation_prompt=True` suffix, which ends at bare `<|start|>assistant`.
- The repo already solved this shape in `scripts/train_rl_fullspec.py` by
  pre-formatting prompts and appending `<|channel|>final<|message|>`.

Follow-up launched:

- Job: `160245.sophia-pbs-01.lab.alcf.anl.gov`
- Same script, checkpoint, corpus, caps, and resources as `160244`.
- Added trainer flag: `--force-final-channel`
- Added template kwarg: `--chat-template-reasoning-effort none`
- Status at launch check: running on `a Sophia GPU node/0*128` as of
  `2026-06-24 19:09:58 UTC`.
- Main log: `outputs/logs/grpo_direct_contract_160245.log`
- Sample logs:
  `outputs/logs/grpo_direct_cap{cap}_160245_samples.jsonl`

Parser command after completion:

```bash
python scripts/analyze_grpo_diag_caps.py \
  --log outputs/logs/grpo_direct_contract_160245.log \
  --samples outputs/logs/grpo_direct_cap*_160245_samples.jsonl
```

Early abort gate for `160245`:

- if the first 8 to 16 cap-96 samples still start with `analysis`, stop the job;
- if samples start directly with TLA+ but extraction is still poor, inspect the
  extractor before more GRPO.

Early evidence:

- `160245` reached cap `96` step 3 quickly after model load.
- The trainer log confirms prompts were pre-formatted with final-channel suffix
  and `reasoning_effort='none'`.
- First `20` cap-96 sample rows:
  - `0/20` start with `analysis`;
  - `20/20` start with `Next ==`;
  - `20/20` contain `Next ==`;
  - `0/20` have empty extracted `Next`;
  - mean sample reward is `0.3125`.
- Training metrics improved immediately versus `160244`:
  - step 1 reward mean `0.2375`, reward std `0.175`;
  - step 3 reward mean `0.3625`, reward std `0.425`;
  - step 3 clipped ratio dropped to `0.75`.

This is the first strong evidence that the main bottleneck was the Harmony
generation channel, not the model's inability to write action-level TLA+.

Final `160245` result:

| Cap | Steps | Clipped mean | Terminated nonzero | Reward mean | Reward max | Reward std nonzero | Empty extracted `Next` | `analysis` start | `Next ==` start |
|-----|-------|--------------|--------------------|-------------|------------|--------------------|------------------------|------------------|-----------------|
| `96` | `12` | `0.604167` | `7` | `0.267708` | `0.6625` | `6/12` | `0/48` | `0/48` | `48/48` |
| `128` | `12` | `0.604167` | `8` | `0.35625` | `0.575` | `10/12` | `0/48` | `0/48` | `48/48` |

Decision:

- Promote cap `128` to the next real short phase.
- Keep `--force-final-channel`, `--chat-template-reasoning-effort none`, and
  `CHATTLA_ACTION_PROMPT_MODE=direct` mandatory for action-GRPO jobs.
- Do not publish yet. This only proves the action-level RL loop is finally
  producing scoreable samples; it still needs a longer phase, holdout eval, and
  fresh full benchmark.

Next promoted phase:

- Start from
  `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240`
  with a fresh scheduler.
- Cap: `128`
- Generations: `4`
- Steps: `120`
- LR: `2e-6`
- Save every `20`
- Sample logging every `5` reward calls.

Submitted promoted phase:

- Job: `160247.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `single-node`
- Requested resources: `1:ngpus=4:ncpus=128:mem=480gb`
- Walltime: `02:00:00`
- Status at launch check: running on `a Sophia GPU node/0*128` as of
  `2026-06-24 19:17:21 UTC`
- Script: `scripts/qsub_grpo_sophia_final_channel_cap128_phase.pbs`
- Output:
  `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1`
- Main log:
  `outputs/logs/grpo_final_channel_cap128_phase_160247.log`
- Sample log:
  `outputs/logs/grpo_final_channel_cap128_phase_160247_samples.jsonl`

Early launch check:

- At `2026-06-24 19:20 UTC`, `160247` was running at step `11/120`.
- The log confirms final-channel prompt preformatting with
  `reasoning_effort='none'`.
- First sample batch: `8/8` start with `Next ==`, `0/8` start with
  `analysis`, and `0/8` have empty extracted `Next`.
- Early metric rows still show some reward-variance instability, including
  several `reward_std = 0` batches, so keep watching rather than declaring the
  phase good. The key structural failure from earlier runs has not reappeared.

Post-phase eval gate:

- Added PEFT-adapter and final-channel support to `scripts/eval_canary_tla.py`.
- Added `spec`/`topic_desc` fallback to `src.validators.per_action_tlc` so
  `data/processed/diamond_eval_holdout.jsonl` carves into action harnesses.
- Updated `scripts/eval_canary_tla.py` to print a generic delta whenever two or
  more result sets are present, so the dependent adapter-vs-adapter eval will
  report `new - baseline` directly in the log instead of requiring manual JSON
  parsing.
- Remote validation: the diamond holdout yields `30` action harnesses, starting
  with `AlternatingBit`.
- Submitted dependent holdout eval:
  `160250.sophia-pbs-01.lab.alcf.anl.gov`
- Dependency: `afterok:160247`
- Script: `scripts/qsub_eval_sophia_action_holdout_fc128.pbs`
- Compares:
  - baseline adapter:
    `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240`
  - new adapter:
    `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1`
- Corpus: `data/processed/diamond_eval_holdout.jsonl`
- Output:
  `outputs/eval/action_holdout_fc128_phase1_${PBS_JOBNUM}.json`
- Log:
  `outputs/logs/eval_action_holdout_fc128_${PBS_JOBNUM}.log`

Live step-40/42 check:

- At `2026-06-24 19:25 UTC`, `160247` was still running.
- It had passed the first save point and written at least `checkpoint-20`.
- Parsed metric rows: `42`
- Mean clipped ratio: `0.488095`
- Reward mean: `0.254762`
- Reward max: `0.7875`
- Reward nonzero: `42/42`
- Reward std nonzero: `16/42`
- Mean KL: `0.002852`; max KL: `0.01012`
- Mean terminated length: `59.42`; nonzero terminated length on `33/42` rows
- Sample rows: `32`
- Sample shape:
  - `0/32` start with `analysis`;
  - `31/32` start with `Next ==`;
  - `0/32` have empty extracted `Next`;
  - sample reward mean `0.251563`.

Decision: keep `160247` running. The phase has not regressed to the
analysis-channel failure mode, clipped ratio is comfortably under the old
`0.8` gate, and reward is nonzero on every logged step. Reward variance is
mixed rather than excellent, so the dependent holdout eval remains mandatory.

Live step-54 check:

- At `2026-06-24 19:28 UTC`, `160247` was still running on
  `a Sophia GPU node/0*128` with walltime about `00:11`.
- Written checkpoints: `checkpoint-20`, `checkpoint-40`.
- Parsed metric rows: `54`.
- Mean clipped ratio: `0.449074`; max `1.0`; nonzero on `40/54` rows.
- Reward mean: `0.272685`; max `1.0`; nonzero on `54/54` rows.
- Reward std mean: `0.137257`; reward std nonzero on `23/54` rows.
- Mean KL: `0.002939`; max `0.01012`.
- Mean terminated length: `59.99`; nonzero terminated length on `44/54` rows.
- Latest row: reward `0.575`, reward std `0.4907`, clipped ratio `0.25`,
  LR `1.117e-06`.
- Sample rows: `40`.
- Sample shape:
  - `0/40` start with `analysis`;
  - `39/40` start with `Next ==`;
  - `0/40` have empty extracted `Next`;
  - sample reward mean `0.27375`.

Decision: still in flight and still worth running. The structural channel fix
is holding, the reward signal is alive, and the dependent holdout eval
`160250` is correctly held on `afterok:160247`.

Live step-66 check:

- At `2026-06-24 19:31 UTC`, `160247` was still running with walltime about
  `00:13`.
- Written checkpoints: `checkpoint-20`, `checkpoint-40`, `checkpoint-60`.
- Parsed metric rows: `66`.
- Mean clipped ratio: `0.454545`; max `1.0`; nonzero on `49/66` rows.
- Reward mean: `0.277652`; max `1.0`; nonzero on `66/66` rows.
- Reward std mean: `0.152961`; reward std nonzero on `32/66` rows.
- Mean KL: `0.00289`; max `0.01012`.
- Mean terminated length: `59.43`; nonzero terminated length on `54/66` rows.
- Latest row: reward `0.575`, reward std `0.4907`, clipped ratio `1.0`,
  LR `9.167e-07`.
- Sample rows: `52`.
- Sample shape:
  - `0/52` start with `analysis`;
  - `51/52` start with `Next ==`;
  - `0/52` have empty extracted `Next`;
  - sample reward mean `0.258654`.

Decision: continue unchanged. The run has crossed `checkpoint-60` with a live
reward signal and no channel relapse. Reward-std nonzero is `32/66`, just below
the half-of-steps promotion preference, so the fixed holdout remains the
deciding gate rather than this live metric alone.

Dependent artifact preflight:

- Added `scripts/qsub_sophia_fc128_artifact_preflight.pbs`.
- Submitted job: `160252.sophia-pbs-01.lab.alcf.anl.gov`.
- Dependency: `afterok:160250`, so it only wakes after the holdout eval job
  exits cleanly.
- Purpose: read
  `outputs/eval/action_holdout_fc128_phase1_160250.json`, abort on holdout
  regression, and only then run merge + GGUF conversion + Hugging Face
  publisher dry-run.
- Internal gate:
  - same `n` for baseline and candidate;
  - candidate TLC pass count no worse than baseline;
  - candidate SANY pass count no worse than baseline;
  - candidate mean reward no worse than baseline;
  - candidate `analysis_start == 0`;
  - candidate `empty_extracted_next == 0`.
- If the gate passes, it merges:
  `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1`
  onto the cached `EricSpencer00/chattla-20b` snapshot into
  `outputs/merged_model_fc128_phase1`, converts
  `outputs/gguf/chattla-20b-Q8_0.gguf`, and runs
  `python -m src.training.publish_hf --dry-run --require-fresh-full-benchmark-hours 24`.
- This still does **not** publish. It is a deployability preflight. A real
  upload remains blocked until a fresh full benchmark exists and is inspected.

Live step-81 check:

- At `2026-06-24 19:34 UTC`, `160247` was still running with walltime about
  `00:16`.
- Written checkpoints: `checkpoint-20`, `checkpoint-40`, `checkpoint-60`,
  `checkpoint-80`.
- Parsed metric rows: `81`.
- Mean clipped ratio: `0.425926`; max `1.0`; nonzero on `58/81` rows.
- Reward mean: `0.308333`; max `1.0`; nonzero on `81/81` rows.
- Reward std mean: `0.171032`; reward std nonzero on `43/81` rows.
- Mean KL: `0.002936`; max `0.01012`.
- Mean terminated length: `59.06`; nonzero terminated length on `68/81` rows.
- Latest row: reward `0.575`, reward std `0.4907`, clipped ratio `0`,
  LR `6.667e-07`.
- Sample rows: `64`.
- Sample shape:
  - `0/64` start with `analysis`;
  - `63/64` start with `Next ==`;
  - `0/64` have empty extracted `Next`;
  - sample reward mean `0.267969`.

Decision: keep running. The live training metrics now satisfy the clipped-ratio
and reward-variance preferences, and the output contract remains fixed. The
artifact chain should still wait for the fixed holdout, because these are
training-corpus rewards rather than an independent eval.

Live step-93 check:

- At `2026-06-24 19:36 UTC`, `160247` was still running with walltime about
  `00:18`.
- Latest written checkpoint remained `checkpoint-80`; `checkpoint-100` was not
  written yet.
- Parsed metric rows: `93`.
- Mean clipped ratio: `0.413978`; max `1.0`; nonzero on `65/93` rows.
- Reward mean: `0.314919`; max `1.0`; nonzero on `93/93` rows.
- Reward std mean: `0.189815`; reward std nonzero on `52/93` rows.
- Mean KL: `0.002853`; max `0.01012`.
- Mean terminated length: `61.11`; nonzero terminated length on `79/93` rows.
- Latest row: reward `0.3625`, reward std `0.425`, clipped ratio `0.25`,
  LR `4.667e-07`.
- Sample rows: `72`.
- Sample shape:
  - `0/72` start with `analysis`;
  - `71/72` start with `Next ==`;
  - `0/72` have empty extracted `Next`;
  - sample reward mean `0.302083`.

Decision: still healthy. The live metrics now clear the original promote
preferences, but final acceptance remains holdout-gated.

Live step-111 check:

- At `2026-06-24 19:40 UTC`, `160247` was still running with walltime about
  `00:22`.
- Written checkpoints: `checkpoint-20`, `checkpoint-40`, `checkpoint-60`,
  `checkpoint-80`, `checkpoint-100`.
- Parsed metric rows: `111`.
- Mean clipped ratio: `0.421171`; max `1.0`; nonzero on `79/111` rows.
- Reward mean: `0.314302`; max `1.0`; nonzero on `111/111` rows.
- Reward std mean: `0.184928`; reward std nonzero on `60/111` rows.
- Mean KL: `0.002831`; max `0.01016`.
- Mean terminated length: `60.85`; nonzero terminated length on `94/111` rows.
- Latest row: reward `0.15`, reward std `0`, clipped ratio `0.5`,
  LR `1.667e-07`.
- Sample rows: `88`.
- Sample shape:
  - `0/88` start with `analysis`;
  - `87/88` start with `Next ==`;
  - `0/88` have empty extracted `Next`;
  - sample reward mean `0.278409`.

Decision: continue to final. The phase is close to the 120-step target and
still satisfies the structural and reward-signal checks.

Final training result for `160247`:

- Job state: finished with `Exit_status = 0`.
- Runtime: `00:24:47` walltime; trainer-reported `1432s`.
- Final output:
  `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1`.
- Final checkpoint: `checkpoint-120`.
- Parsed metric rows: `120`.
- Mean clipped ratio: `0.416667`; max `1.0`; nonzero on `83/120` rows.
- Reward mean: `0.315833`; max `1.0`; nonzero on `120/120` rows.
- Reward std mean: `0.185695`; reward std nonzero on `65/120` rows.
- Mean KL: `0.002917`; max `0.01036`.
- Mean terminated length: `60.94`; nonzero terminated length on `102/120`
  rows.
- Final row: reward `0.2375`, reward std `0.175`, clipped ratio `0`,
  LR `1.667e-08`.
- Sample rows: `96`.
- Sample shape:
  - `0/96` start with `analysis`;
  - `95/96` start with `Next ==`;
  - `0/96` have empty extracted `Next`;
  - sample reward mean `0.271354`.

Decision: the training phase itself passed the live structural/reward gates and
correctly released dependent eval job `160250`. Do not publish or merge based
on training metrics alone; wait for `160250`.

Holdout eval result for `160250`:

- Job state: finished with `Exit_status = 0`.
- Output JSON: `outputs/eval/action_holdout_fc128_phase1_160250.json`.
- Baseline adapter:
  `outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240`.
- Candidate adapter:
  `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1`.
- Baseline result:
  - `n=30`;
  - TLC `6/30`;
  - SANY `7/30`;
  - mean reward `0.216667`;
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Candidate result:
  - `n=30`;
  - TLC `6/30`;
  - SANY `6/30`;
  - mean reward `0.2`;
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Delta:
  - TLC `+0`;
  - SANY `-1`;
  - mean reward `-0.016667`.
- Changed examples:
  - `AlternatingBit`: baseline TLC pass (`1.0`) -> candidate bronze (`0.0`);
  - `EmailVerification`: baseline SANY-only (`0.5`) -> candidate TLC pass
    (`1.0`).

Decision: do **not** promote, merge, or publish this candidate. It fixed the
output channel/format problem and held TLC count, but it failed the no-regress
holdout gate by losing one SANY pass and mean reward. The dependent artifact
preflight job `160252` was canceled after eval to avoid spending a node on a
known-failing gate.

Next experiment after failed final-checkpoint promotion:

- Added `scripts/qsub_eval_sophia_action_holdout_fc128_ckpts.pbs`.
- Submitted checkpoint sweep job:
  `160260.sophia-pbs-01.lab.alcf.anl.gov`.
- Status at submit check: running immediately on `a Sophia GPU node/0*128` as of
  `2026-06-24 19:52 UTC`.
- Purpose: compare `checkpoint-20`, `checkpoint-40`, `checkpoint-60`,
  `checkpoint-80`, `checkpoint-100`, and `checkpoint-120` from
  `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1`
  against baseline `checkpoint-240` on the same 30-example action holdout.
- Output pattern:
  `outputs/eval/action_holdout_fc128_phase1_ckpt${step}_160260.json`.
- Log:
  `outputs/logs/eval_action_holdout_fc128_ckpts_160260.log`.
- Decision rule:
  - promote only an intermediate checkpoint that has no TLC/SANY/mean-reward
    regression versus `checkpoint-240`;
  - if no checkpoint passes, do not continue this exact RL phase shape;
  - use the result to decide between shorter early-stop promotion, stronger
    reward shaping against regressions, or adding a replay/anchor term for
    already-good actions.

Checkpoint sweep partial result:

- `checkpoint-20` completed on job `160260`.
- Result:
  - TLC `6/30` versus baseline `6/30` (`+0`);
  - SANY `7/30` versus baseline `7/30` (`+0`);
  - mean reward `0.216667` versus baseline `0.216667` (`+0.000000`);
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Decision: `checkpoint-20` is a no-regression checkpoint, but it is not an
  improvement on the fixed holdout. Keep the sweep running through later
  checkpoints before deciding whether to promote an early stop, because the
  goal is a stronger prover, not merely a format-fixed tie.
- Changed examples at `checkpoint-20`:
  - `BackpressureChannel`: baseline bronze (`0.0`) -> candidate SANY-only
    (`0.5`);
  - `EmailVerification`: baseline SANY-only (`0.5`) -> candidate bronze
    (`0.0`).
- Interpretation: the aggregate tie is a trade, not a monotonic improvement.
  The next recipe likely needs an anti-forgetting anchor/replay mechanism if no
  later checkpoint improves the fixed holdout cleanly.
- `checkpoint-40` completed on job `160260`.
- Result:
  - TLC `6/30` versus baseline `6/30` (`+0`);
  - SANY `8/30` versus baseline `7/30` (`+1`);
  - mean reward `0.233333` versus baseline `0.216667` (`+0.016667`);
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Decision: `checkpoint-40` is currently the first promotable checkpoint from
  this phase: it preserves TLC, improves SANY, improves mean reward, and keeps
  the final-channel output contract clean. Keep the sweep running before
  choosing it, because a later checkpoint may improve TLC or reward further.
- Added `scripts/qsub_sophia_fc128_best_artifact_preflight.pbs`.
- Submitted dependent artifact-preflight job:
  `160268.sophia-pbs-01.lab.alcf.anl.gov`.
- Dependency: `afterok:160260`.
- Purpose: after the sweep finishes, read all
  `outputs/eval/action_holdout_fc128_phase1_ckpt*_160260.json` files, select
  the best checkpoint that improves at least one held-out metric while
  regressing none, and only then attempt merge + GGUF conversion + Hugging Face
  publisher dry-run.
- Selection key among eligible checkpoints: highest TLC, then highest SANY,
  then highest mean reward, then earliest step. If no checkpoint improves
  without regression, the job aborts before merge.
- This still does **not** publish. A real upload remains blocked by the fresh
  full benchmark gate and manual inspection of the deployable artifact.
- Prepared Sophia artifact prerequisites before `160268` wakes:
  - cloned `llama.cpp` into `outputs/llama.cpp`;
  - installed `gguf` and `sentencepiece` into the `frs` conda env;
  - added `CHATTLA_LLAMA_CPP_OFFLINE=1` support to
    `src/inference/convert_to_gguf.py`;
  - set `CHATTLA_LLAMA_CPP_OFFLINE=1` in
    `scripts/qsub_sophia_fc128_best_artifact_preflight.pbs`.
- Rationale: compute jobs should not have to rely on outbound git/pip access
  for conversion after spending GPU time merging weights.
- `checkpoint-60` completed on job `160260`.
- Result:
  - TLC `5/30` versus baseline `6/30` (`-1`);
  - SANY `6/30` versus baseline `7/30` (`-1`);
  - mean reward `0.183333` versus baseline `0.216667` (`-0.033333`);
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Decision: reject `checkpoint-60`. It keeps the output format clean but shows
  real holdout regression. Current best remains `checkpoint-40`.
- `checkpoint-80` completed on job `160260`.
- Result:
  - TLC `5/30` versus baseline `6/30` (`-1`);
  - SANY `6/30` versus baseline `7/30` (`-1`);
  - mean reward `0.183333` versus baseline `0.216667` (`-0.033333`);
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Decision: reject `checkpoint-80`. The regression matches `checkpoint-60`,
  which makes `checkpoint-40` look like the useful early-stop point rather than
  the start of a monotonic improvement phase.
- `checkpoint-100` completed on job `160260`.
- Result:
  - TLC `7/30` versus baseline `6/30` (`+1`);
  - SANY `8/30` versus baseline `7/30` (`+1`);
  - mean reward `0.250000` versus baseline `0.216667` (`+0.033333`);
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Changed examples:
  - `CountDownLatch`: baseline TLC pass (`1.0`) -> candidate bronze (`0.0`);
  - `BullyElection`: baseline bronze (`0.0`) -> candidate TLC pass (`1.0`);
  - `DocumentApproval`: baseline bronze (`0.0`) -> candidate TLC pass (`1.0`).
- Decision: `checkpoint-100` supersedes `checkpoint-40` as the current best
  candidate. It is still not monotonic on individual examples, so the next
  training recipe should add anti-forgetting pressure, but it passes the
  current aggregate no-regression gate and improves TLC, SANY, and reward.
- `checkpoint-120` completed on job `160260`.
- Result:
  - TLC `6/30` versus baseline `6/30` (`+0`);
  - SANY `6/30` versus baseline `7/30` (`-1`);
  - mean reward `0.200000` versus baseline `0.216667` (`-0.016667`);
  - `next_start=30/30`, `analysis_start=0/30`, `empty_next=0/30`.
- Decision: reject `checkpoint-120`. Like the final adapter eval, it preserves
  the output channel but regresses SANY and reward.
- Final sweep decision:
  - job `160260` completed with `Exit_status = 0`;
  - eligible no-regression/improving checkpoints: `checkpoint-40` and
    `checkpoint-100`;
  - selected best checkpoint: `checkpoint-100`, because it has the highest TLC,
    highest SANY, and highest mean reward among eligible checkpoints;
  - selection artifact:
    `outputs/eval/fc128_best_checkpoint_160268.json`;
  - selected adapter:
    `outputs/checkpoints_grpo_action_tok1200_g4_final_channel_cap128_phase1/checkpoint-100`.
- Dependent artifact preflight job `160268` released after `160260` and started
  on `a Sophia GPU node`. It is merging the selected LoRA, then should attempt GGUF
  conversion and Hugging Face publisher dry-run.
- Artifact preflight `160268` failed before conversion:
  - PBS state: finished with `Exit_status = 1`;
  - failure location: `src.training.merge_lora`, inside PEFT
    `merge_and_unload()`;
  - error: `RuntimeError: CUDA error: CUBLAS_STATUS_ALLOC_FAILED when calling
    cublasCreate(handle)`;
  - node had 4x A100 40GB free at job start, and host memory use stayed around
    40GB, so the failure is the GPU merge path, not a bad selected checkpoint
    or missing artifact input.
- Corrective action:
  - added `--no-dpo-auto` to `src/training/merge_lora.py` so artifact jobs can
    avoid accidentally merging the older `outputs/checkpoints_dpo` adapter;
  - changed `scripts/qsub_sophia_fc128_best_artifact_preflight.pbs` to run
    `merge_lora` with `CUDA_VISIBLE_DEVICES="" --device cpu --no-dpo-auto`;
  - remote-compiled the patched `merge_lora.py` and `bash -n` checked the PBS
    script on Sophia;
  - submitted retry job `160286.sophia-pbs-01.lab.alcf.anl.gov`.
- Rationale: CPU merge is slower but avoids the CUBLAS/VRAM failure mode and
  should fit inside the requested 480GB host memory. Disabling DPO autodetect
  keeps the artifact faithful to the selected GRPO adapter.
- Retry `160286` proved the CPU merge path gets through `merge_and_unload()`,
  but failed while saving:
  - `save_pretrained()` entered the Transformers PEFT adapter-save branch
    because `_hf_peft_config_loaded` remained set after merge;
  - the fallback `torch.save(state_dict, pytorch_model.bin)` then attempted a
    monolithic binary and failed after writing about `23GB`;
  - output directory after failure contained only partial `pytorch_model.bin`
    and generation config, not a valid merged model.
- Second corrective action:
  - patched `merge_lora.py` to clear stale PEFT save markers after every
    `merge_and_unload()`;
  - changed the save path to use full-model sharded safetensors with
    `save_peft_format=False` and `max_shard_size=5GB`;
  - removed the monolithic `torch.save` fallback for this 20B artifact path;
  - remote-compiled the patched file and submitted retry job
    `160287.sophia-pbs-01.lab.alcf.anl.gov`.
- Retry `160287` then failed immediately with `OSError: [Errno 122] Disk quota
  exceeded` while writing `outputs/merged_model_fc128_best/config.json`.
  This proves the next blocker is `/home` quota, not the merge logic.
- Third corrective action:
  - added `--gguf-dir` support to `src/inference/convert_to_gguf.py`;
  - added `--gguf-dir` and `--merged-model-dir` support to
    `src/training/publish_hf.py`;
  - changed the artifact preflight to write heavy artifacts under
    `/grand/<ACCOUNT>/<user>/chattla_artifacts/fc128_best`;
  - verified that `/grand/<ACCOUNT>/<user>/chattla_artifacts` is writable;
  - remote-compiled the patched files and submitted retry job
    `160291.sophia-pbs-01.lab.alcf.anl.gov`.
- Retry `160291` successfully merged and saved the selected adapter as sharded
  safetensors under `/grand/<ACCOUNT>/<user>/chattla_artifacts/fc128_best`,
  but GGUF conversion failed because the saved tensors retained PEFT wrapper
  names such as `base_model.model.model.embed_tokens.weight`.
- Fourth corrective action:
  - patched `merge_lora.py` to pass a converter-friendly state dict to
    `save_pretrained()`;
  - if tensor names start with `base_model.model.`, the save path strips that
    prefix before writing the sharded safetensors;
  - remote-compiled the patched file and submitted retry job
    `160296.sophia-pbs-01.lab.alcf.anl.gov`.
- Retry `160296` still produced prefixed tensor names because Transformers
  `save_pretrained()` defaulted `save_original_format=True`, which reintroduced
  names like `base_model.model.model.embed_tokens.weight` after the state-dict
  cleanup. GGUF conversion failed on that tensor name.
- Fifth corrective action:
  - patched `merge_lora.py` to call `save_pretrained(...,
    save_original_format=False)` for merged artifacts;
  - remote-compiled the patch and submitted retry job
    `160299.sophia-pbs-01.lab.alcf.anl.gov`.
- Retry `160299` completed successfully:
  - PBS `Exit_status = 0`;
  - merged BF16 artifacts:
    `/grand/<ACCOUNT>/<user>/chattla_artifacts/fc128_best/merged_model`;
  - saved index has normal converter names (`prefixed=0`, `model.*=410`);
  - GGUF:
    `/grand/<ACCOUNT>/<user>/chattla_artifacts/fc128_best/gguf/chattla-20b-Q8_0.gguf`;
  - GGUF size: about `22.3GB`;
  - publisher dry-run selected version `v20` but correctly warned that real
    publish would abort because the newest full benchmark was
    `benchmark_results_v14_full_20260404.csv`, about `1488.9h` old.
- Current state: deployable artifact exists, but real Hugging Face publish is
  still blocked by a fresh full benchmark and final manual publish approval.

## Local GGUF benchmark result, 2026-06-24

The Sophia artifact from job `160299` was copied to the local Mac, registered
with Ollama as `chattla:20b-fc128best`, and smoke-tested. Registration and
generation worked, but quality did not pass the publish bar.

Evidence:

- local GGUF:
  `outputs/gguf_fc128_best/chattla-20b-Q8_0.gguf`;
- SHA256 prefix:
  `5b3d2729998b5b7ccc53a230dec010b1518d9c2fb3e34040931ae521a1f7e85f`;
- local Ollama tag:
  `chattla:20b-fc128best`;
- smoke CSV:
  `outputs/benchmark_results/benchmark_results_fc128best_smoke_20260624_163412.csv`;
- combined full CSV:
  `outputs/benchmark_results/benchmark_results_fc128best_full_20260624_1640.csv`;
- sliced full benchmark parts:
  `outputs/benchmark_results/fc128best_parts_20260624_1640/`.

Full benchmark result:

- SANY: `0/20`;
- TLC: `0/20`;
- depth-1: `0/20`;
- partial-credit mean: `0.0`.

Qualitative failure mode:

- generated modules have the right surface shape but invalid TLA+ syntax and
  semantics, for example `#=`, primed assignments in `Init`, undeclared
  variables, mismatched `TypeOK`/`TypeInvariant`, and pseudo-code operators;
- action-holdout success did not transfer to full-module generation;
- Modelfile/template mode did not rescue the behavior, so this is not just an
  Ollama wrapper issue.

Operational note:

- the original full local benchmark process was killed with exit `137` around
  BM005, likely local memory pressure;
- `src/inference/benchmark.py` now flushes each CSV row immediately so future
  benchmark interruptions leave usable partial evidence;
- the completed full scorecard was produced by running one benchmark problem
  per subprocess and combining the per-problem CSVs.

Decision:

- do not publish `chattla:20b-fc128best`;
- do not repeat another action-only FC128 phase as the default next step;
- launch a short full-spec GRPO diagnostic that optimizes the deployment task
  directly: natural language to complete TLA+ module, scored by the component
  validator.

Next submitted recipe:

```bash
qsub scripts/qsub_grpo_sophia_fullspec_diag.pbs
```

Initial attempts:

- job `160325` ran two steps with the original full-spec component reward and
  showed `reward=0`, `reward_std=0`, `grad_norm=0`;
- job `160328` added sample logging and showed the root cause: completions were
  full module-shaped TLA+ outputs, but all were SANY-invalid, so the reward
  was flat zero;
- `src/rlvr_canary/fullspec_reward.py` now adds a pre-SANY structural and
  syntax-hygiene floor for near-miss modules, while keeping verifier/TLC
  rewards above that band;
- job `160339` completed a 6-step sampled diagnostic with the shaped reward.

`160339` evidence:

- output:
  `outputs/checkpoints_grpo_fullspec_diag_160339`;
- samples:
  `outputs/logs/grpo_fullspec_diag_160339_samples.jsonl`;
- checkpoints:
  `checkpoint-3` and `checkpoint-6`;
- step 1: reward mean/std `0.2537/0.0075`, grad norm `4.253`;
- step 2: reward mean/std `0.2575/0.015`, grad norm `20.19`;
- step 3: reward mean/std `0.2113/0.05921`, grad norm `27.3`;
- step 5: reward mean/std `0.2875/0.075`, grad norm `2.92`;
- step 6: reward mean/std `0.21/0.0495`, grad norm `6.917`;
- only step 4 was flat (`reward_std=0`).

Decision:

- full-spec GRPO is now viable enough to run longer because it has nonzero
  reward variance and nonzero gradients;
- the reward is still mostly a syntax/shape ladder, not yet SANY/TLC success,
  so the next phase should remain a bounded phase, not a publish candidate;
- inspect samples for reductions in invalid declarations (`CONSTANTS N \in`,
  typed `VARIABLES`, `EXISTS`) before promoting to a long run.

Promote this path only if:

- reward is nonzero and has variance in early steps;
- completions start as full modules without analysis/prose drift;
- checkpoint-10 or checkpoint-20 improves SANY/full-module score on a fixed
  benchmark or holdout sample;
- local/Ollama GGUF benchmark recovers above the previous `0/20` full-score
  floor after merge/conversion.

## 2026-06-24 full-spec phase-1 live result

Submitted the bounded full-spec phase after the shaped-reward diagnostic:

- Job: `160343.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `single-node`
- Node: `a Sophia GPU node`
- Requested resources: `1:ngpus=4:ncpus=128:mem=480gb`
- Walltime: `04:00:00`
- Script: `scripts/qsub_grpo_sophia_fullspec_phase1.pbs`
- Output: `outputs/checkpoints_grpo_fullspec_phase1_160343`
- Main log: `outputs/logs/grpo_fullspec_phase1_160343.log`
- Sample log: `outputs/logs/grpo_fullspec_phase1_160343_samples.jsonl`
- Training shape: `60` steps, `4` generations, `max_completion=1024`,
  LoRA `r=8`, LR `2e-6`, save every `20`, sample every `5` reward calls.

Live check at step `29/60`:

- Job state: running.
- Saved checkpoints: `checkpoint-20`.
- Parsed metric rows: `29`.
- Reward mean: `0.263793`; min `0.235`; max `0.35`.
- Reward std mean: `0.030445`; reward std nonzero on `22/29` rows.
- Clipped mean: `0.241379`; max `0.5`.
- Mean KL: `0.010916`; max `0.02963`.
- Mean completion length: `659.63`.
- Latest row: reward `0.28`, reward std `0`, clipped ratio `0.25`,
  LR `1.067e-6`.
- Sample rows: `20`.
- Sample shape:
  - `20/20` start with `---- MODULE`;
  - `19/20` contain `====`;
  - sample reward mean `0.25675`, max `0.28`.

Live check at step `40/60`:

- Job state: running.
- Saved checkpoints: `checkpoint-20`, `checkpoint-40`.
- Latest row: reward `0.265`, reward std `0.01732`, clipped ratio `0.25`,
  mean completion length `256`, LR `7e-7`, grad norm `6.875`.
- The phase has now produced the first mid-run checkpoint required by the
  dependent eval job `160345`.

Live check at step `42/60`:

- Job state: still running.
- Steps `1-20`: reward mean `0.263690`, reward std nonzero `17/20`,
  clipped mean `0.2375`, max reward `0.35`.
- Steps `21-40`: reward mean `0.261310`, reward std nonzero `15/20`,
  clipped mean `0.25`, max reward `0.35`.
- Steps `41-42`: reward mean `0.34375`, max reward `0.4375`.
- Step `41` showed a high-variance/high-reward spike:
  reward mean/std `0.4375/0.375`.
- The spike was not captured in raw samples because phase-1 only logs every
  `5` reward calls; the latest sampled call (`40`) still looked mostly like
  invalid floor-band modules with typed declarations, bad `UNCHANGED <<>>`, and
  free variables.
- Updated queued phase-2 script so `160347`, if it trains, uses
  `--sample-log-every 1`. This should preserve every high-signal completion
  in the stricter reward phase.

Interpretation:

- This phase is useful and should keep running. It is clearly no longer the
  flat-zero full-spec run from `160325`/`160328`.
- It is not yet a promotion candidate. Samples are module-shaped, but rewards
  are still mostly in the structural floor band rather than verifier/TLC
  success.
- Recent steps are plateauing at the shaped floor: steps `26` through `29`
  logged `reward_std=0` and tiny gradients. That does not invalidate the
  earlier signal, but it means the next recipe should make syntax-validity
  separable, not just module shape.

Likely next improvement:

- Keep this phase to at least `checkpoint-40` or completion, unless it fails.
- Add a remote full-spec checkpoint eval before any artifact work. The eval
  should score `checkpoint-20`, `checkpoint-40`, and `checkpoint-60` on a fixed
  small full-spec holdout with `reward_from_spec`, plus explicit counts for
  SANY/depth-1/full-TLC success.
- Tighten the next reward ladder around concrete syntax failures seen in
  samples: typed `CONSTANTS`/`VARIABLES`, undeclared action parameters, nested
  operator definitions inside `Next`, invalid record/function updates, and
  pseudo-code assignment syntax.
- Do not merge, GGUF-convert, or publish any full-spec checkpoint until it
  beats the current `0/20` full benchmark floor on an independent full-module
  eval.

Follow-up queued:

- Added `scripts/eval_fullspec_checkpoints.py`.
- Added `scripts/qsub_eval_sophia_fullspec_phase1_ckpts.pbs`.
- Submitted dependent eval job:
  `160345.sophia-pbs-01.lab.alcf.anl.gov`.
- Dependency: `afterok:160343`.
- Status at submit check: held on dependency, as expected.
- Eval target: base model plus `checkpoint-20`, `checkpoint-40`, and
  `checkpoint-60` from `outputs/checkpoints_grpo_fullspec_phase1_160343`.
- Eval corpus: first `10` rows of `data/processed/diamond_eval_holdout.jsonl`.
- Eval outputs:
  - `outputs/logs/eval_fullspec_phase1_ckpts_160345.log`;
  - `outputs/eval/fullspec_phase1_base_160345.json`;
  - `outputs/eval/fullspec_phase1_ckpt{20,40,60}_160345.json`.
- Metrics: SANY pass count, TLC pass count, depth-1 pass count,
  component partial-credit mean, structural-floor mean, module-start,
  terminator, and target module match.

Decision rule for `160345`:

- promote a checkpoint only if it improves over base on at least one verifier
  metric without regressing SANY/depth-1/TLC count;
- if all checkpoints remain at structural-floor-only reward, patch the reward
  ladder before launching another long full-spec phase;
- never run local Ollama for this path on the MacBook; keep generation/eval on
  Sophia.

Next-run reward patch:

- Patched `src/rlvr_canary/fullspec_reward.py` after inspecting additional
  `160343` samples.
- Important distinction: running training job `160343` already imported the
  older reward function, so its training metrics are still from the first
  shaped floor. Future jobs and the dependent eval source tree now include the
  stricter diagnostics.
- Added `_syntax_hygiene_issues()` to log and penalize common SANY/TLC-invalid
  near misses:
  - typed `CONSTANTS` / `VARIABLES` declarations using `\in` or `->`;
  - assignments inside `CONSTANTS` declarations;
  - primed variables inside `Init`;
  - nested operator definitions inside `Next`;
  - `UNCHANGED <<>>`;
  - pseudo/Python-ish helpers such as `len(...)`, `SeqHead`, `SeqTail`,
    `\implies`, predicate names with `?`, and `STRING`.
- Added `syntax_issues` to sample JSONL rows.
- Changed `_structural_floor()` so invalid-but-module-shaped completions are
  capped lower instead of clustering around `0.25` to `0.28`.
- Local sanity check:
  - bad snippet with typed declarations and `UNCHANGED <<>>`: floor `0.205`,
    issues `typed_constants`, `typed_variables`, `empty_unchanged`;
  - clean skeleton: floor `0.28`, no issues.
- Synced and `py_compile` checked the patch on Sophia.

Next-run prompt patch:

- Patched `src/rlvr_canary/fullspec_dataset.py` so future full-spec generation
  prompts explicitly forbid the failure modes observed in `160343` samples:
  typed `CONSTANTS`/`VARIABLES` declarations, `UNCHANGED <<>>`, free action
  parameters in `Next`, nested operator definitions inside `Next`, and
  pseudo-TLA helpers such as `len(...)`, `SeqHead`, `SeqTail`, `\implies`, and
  question-mark predicate names.
- Important distinction: `160343` already built its dataset before this patch,
  so its training metrics reflect the old prompt. `160345` eval and `160347`
  phase-2 generation will use the stricter prompt text.
- Local and Sophia `py_compile` checks passed, and Sophia verified the prompt
  contains the new strict clauses.

Next-run trainer/queue patch:

- Added `--adapter-checkpoint` and `--resume-from-checkpoint` support to
  `scripts/train_rl_fullspec.py`.
- Semantics match the action trainer:
  - use `--resume-from-checkpoint` only to continue an interrupted phase with
    the same optimizer/LR state;
  - use `--adapter-checkpoint` for a new phase that warm-starts learned LoRA
    weights while resetting optimizer and LR schedule.
- Local and Sophia checks:
  - `python -m py_compile scripts/train_rl_fullspec.py`;
  - `python -m scripts.train_rl_fullspec --help` shows both new flags.
- Added gated phase-2 wrapper:
  `scripts/qsub_grpo_sophia_fullspec_phase2_strict_select.pbs`.
- Submitted gated phase-2 job:
  `160347.sophia-pbs-01.lab.alcf.anl.gov`.
- Dependency: `afterok:160345`.
- Behavior:
  - read `outputs/eval/fullspec_phase1_base_160345.json` and
    `outputs/eval/fullspec_phase1_ckpt*_160345.json`;
  - select a phase-1 checkpoint only if it improves at least one verifier or
    reward metric while regressing none of SANY/depth-1/TLC/mean reward versus
    base;
  - if no checkpoint is eligible, write
    `outputs/eval/fullspec_phase2_selection_${PBS_JOBNUM}.json` and exit before
    training;
  - if a checkpoint is eligible, run 40 more full-spec GRPO steps with the
    stricter reward floor, `--adapter-checkpoint`, LR `1.5e-6`, save every
    `10`, sample every `5` reward calls.
- Phase-2 outputs if it trains:
  - `outputs/checkpoints_grpo_fullspec_phase2_strict_160347`;
  - `outputs/logs/grpo_fullspec_phase2_strict_160347.log`;
  - `outputs/logs/grpo_fullspec_phase2_strict_160347_samples.jsonl`;
  - `outputs/eval/fullspec_phase2_selection_160347.json`.
- Updated `160347` before release so it samples every reward call
  (`--sample-log-every 1`) rather than every fifth reward call. This avoids
  missing rare high-reward completions like phase-1 step `41`.

Queued phase-2 eval:

- Added `scripts/qsub_eval_sophia_fullspec_phase2_ckpts.pbs`.
- Submitted dependent eval job:
  `160348.sophia-pbs-01.lab.alcf.anl.gov`.
- Dependency: `afterok:160347`.
- Behavior:
  - if `160347` exits without training because no phase-1 checkpoint is
    eligible, `160348` exits cleanly after noting the missing phase-2 output
    directory;
  - if `160347` trains, evaluate base plus phase-2 `checkpoint-10`,
    `checkpoint-20`, `checkpoint-30`, and `checkpoint-40` on the same first
    `10` diamond-holdout full-spec prompts.
- Eval outputs:
  - `outputs/logs/eval_fullspec_phase2_ckpts_160348.log`;
  - `outputs/eval/fullspec_phase2_base_160348.json`;
  - `outputs/eval/fullspec_phase2_ckpt{10,20,30,40}_160348.json`.

Eval instrumentation update:

- Patched `scripts/eval_fullspec_checkpoints.py` to record
  `syntax_issues`, `syntax_issue_rows`, and `syntax_issue_count` using the
  stricter full-spec reward hygiene helper.
- Patched both full-spec eval PBS summaries to print those counts.
- Rationale: verifier pass counts may stay at zero early; syntax issue counts
  tell us whether the model is actually moving away from typed declarations,
  `UNCHANGED <<>>`, free variables, and pseudo-TLA before SANY/TLC starts
  passing.
- Local checks:
  - `python3 -m py_compile scripts/eval_fullspec_checkpoints.py`;
  - `bash -n` for both eval PBS wrappers;
  - a bad snippet reports syntax issues
    `empty_unchanged`, `typed_constants`, `typed_variables`.
- Synced to Sophia and verified `py_compile`, `bash -n`, and presence of
  `syntax_issue_rows` in all three remote files before `160345` released.

Promote beyond this phase only if:

- clipped mean stays below `0.8`;
- sample logs remain `0` analysis-start and near-`0` empty extracted `Next`;
- reward variance appears on at least half of logged steps;
- a fixed holdout does not regress against `checkpoint-240`.

## 2026-06-24 full-spec phase 1 completion

Sophia job `160343` completed the 60-step full-spec phase-1 diagnostic.

- Machine: Sophia `single-node`, 4x A100 on `a Sophia GPU node`
- Output: `outputs/checkpoints_grpo_fullspec_phase1_160343`
- Sample log: `outputs/logs/grpo_fullspec_phase1_160343_samples.jsonl`
- Saved checkpoints: `checkpoint-20`, `checkpoint-40`, `checkpoint-60`
- Runtime: about `3032s` training, about `50.5s/step`
- Mean reward: `0.266625`
- Max reward: `0.4375`
- Reward std was nonzero on `49/60` logged steps
- Mean clipped ratio: `0.245833`
- Final row: reward `0.2287`, reward std `0.05105`, grad norm `20.09`,
  clipped ratio `0.25`, mean completion length `1024`

Grade: **B+ infrastructure, C+/B- learning signal pending verifier eval**.

Interpretation: this was a real learning run, not a dead zero-reward loop.
The shaped full-spec reward gave frequent variance and the job saved all
planned checkpoints. It is still not a publishable or even promotable result
until the fixed holdout eval proves that the reward translated into fewer SANY
syntax errors, better module completion, and ideally a nonzero verifier pass.
The final rows still include 1024-token completions, so output discipline
remains the main risk.

Current chain after phase 1:

- `160345` phase-1 eval is queued after `160343`, waiting on Sophia resources.
- `160347` strict phase-2 train remains held after `160345`.
- `160348` phase-2 eval remains held after `160347`.
- No user input or new key is needed while SSH remains live and the scheduler
  holds the dependency chain.

Next decision: wait for `160345` JSONs and compare base, `checkpoint-20`,
`checkpoint-40`, and `checkpoint-60`. Only let `160347` train if the gated
selection finds a checkpoint that does not regress against base and improves at
least one verifier/reward metric.

## 2026-06-24 alternate eval queue lane

The original phase-1 eval `160345` remained queued on `single-node` with
`Not Running: Insufficient amount of resource: queue_tags`, so an alternate
`by-gpu` lane was submitted to race the same fixed eval without changing the
original evidence path.

- Original eval: `160345`, queue `single-node`, still queued on `queue_tags`
- Alternate eval: `160353`, queue `by-gpu`, same phase-1 checkpoints and
  output naming by its own PBS job id
- Alternate gated phase 2: `160354`, held after `160353`, with
  `EVAL_JOB=160353`
- Alternate phase-2 eval: `160355`, held after `160354`, with
  `PHASE2_JOB=160354`
- The original downstream jobs `160347` and `160348` were placed under user
  hold (`Hold_Types=su`) so they cannot accidentally launch a duplicate
  phase-2 train if `160345` finishes after the alternate lane.

Implementation notes:

- `scripts/qsub_grpo_sophia_fullspec_phase2_strict_select.pbs` now uses
  `EVAL_JOB="${EVAL_JOB:-160345}"`, preserving the original default while
  allowing alternate eval JSONs.
- `scripts/qsub_eval_sophia_fullspec_phase2_ckpts.pbs` now uses
  `PHASE2_JOB="${PHASE2_JOB:-160347}"`, preserving the original default while
  allowing alternate phase-2 output dirs.
- Both modified wrappers passed `bash -n` locally and on Sophia before the
  alternate chain was submitted.

Next polling rule: first eval JSONs win. If `160353` finishes first, use its
base/checkpoint comparison and let `160354` decide whether phase 2 should train.
Keep `160347`/`160348` held unless the alternate lane fails and the original
lane produces the only usable eval evidence.

## 2026-06-24 one-GPU eval hedge result

Because both 4-GPU eval lanes were still queued on `queue_tags`, a third
phase-1 eval hedge was submitted through Sophia `single-gpu` to test whether
`device_map="auto"` could make eval-only inference work on that queue.

- One-GPU phase-1 eval: `160356`, queue `single-gpu`, ran on
  `a Sophia GPU node`
- Hardware reality: `single-gpu` provided an `NVIDIA A100-SXM4-40GB`, not an
  80GB card.
- Result: failed during base model load with CUDA OOM after `device_map=auto`
  offloaded some parameters to CPU; PyTorch attempted an additional `33.27 GiB`
  allocation with only `5.77 GiB` free.
- No eval JSONs were produced for `160356`.
- Dead downstream jobs `160357` and `160358` were cleaned up.
- The by-gpu downstream path was released back to scheduler dependency hold:
  `160353` -> `160354` -> `160355`.

Current active automatic path: `160353` -> `160354` -> `160355`.

Do not retry this full BF16 eval on one 40GB A100. A one-GPU eval would need a
quantized or explicitly sharded/offloaded path; otherwise wait for the 4-GPU
eval lanes.

## 2026-06-24 int8 one-GPU triage eval result

After the BF16 one-GPU eval OOM, a triage-only int8 eval path was added and
submitted to get relative checkpoint signal while the BF16 4-GPU eval lanes
wait on `queue_tags`.

- Code change: `scripts/eval_fullspec_checkpoints.py` now supports
  `--load-in-8bit`, using `BitsAndBytesConfig(load_in_8bit=True)`.
- New wrapper: `scripts/qsub_eval_sophia_fullspec_phase1_ckpts_int8.pbs`
- Job: `160359.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `single-gpu`
- Node/GPU: `a Sophia GPU node`, one 40GB A100
- Result: failed during base model load before producing JSONs.
- Failure mode: Transformers/bitsandbytes refused the automatic device map
  because some modules would be dispatched to CPU/disk. The error recommends
  `llm_int8_enable_fp32_cpu_offload=True` plus a custom device map.
- Outputs:
  - log `outputs/logs/eval_fullspec_phase1_int8_160359.log`
  - JSONs `outputs/eval/fullspec_phase1_int8_base_160359.json`
  - JSONs `outputs/eval/fullspec_phase1_int8_ckpt{20,40,60}_160359.json`

No int8 eval evidence exists yet. A future int8 hedge would need explicit
CPU-offload configuration and should still be treated only as triage. The BF16
4-GPU eval path remains the authoritative gate.

## 2026-06-24 BF16 eval active

The alternate BF16 phase-1 eval `160353` moved from queued to running while
the int8 hedge was being checked.

- Active job: `160353.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `by-gpu`
- Node: `a Sophia GPU node`
- GPUs: 4x `NVIDIA A100-SXM4-40GB`
- Downstream: `160354` gated strict phase-2 train remains held by scheduler
  dependency after `160353`; `160355` phase-2 eval remains held after `160354`.

This is the current authoritative path. Parse
`outputs/eval/fullspec_phase1_*_160353.json` as soon as they appear. If
`160353` exits successfully, let `160354` select a non-regressing checkpoint
and either train strict phase 2 or exit cleanly with no selection.

Partial result from `160353`:

- Base JSON written: `outputs/eval/fullspec_phase1_base_160353.json`
- Base on first 10 diamond holdout rows:
  - SANY: `6/10`
  - depth-1 TLC: `5/10`
  - TLC: `2/10`
  - mean reward: `0.425`
  - syntax issue rows/count: `0/0`
  - terminators: `10/10`
  - module-name matches: `2/10`
  - raw generations starting exactly with `---- MODULE`: `0/10`

Interpretation: the baseline is not weak on this slice. Phase-1 adapters must
avoid regressing against a real verifier baseline, not merely improve a shaped
reward floor.

Additional partial result:

- `checkpoint-20` JSON written:
  `outputs/eval/fullspec_phase1_ckpt20_160353.json`
- `checkpoint-20` on the same 10 rows:
  - SANY: `3/10`
  - depth-1 TLC: `3/10`
  - TLC: `1/10`
  - mean reward: `0.23`
  - syntax issue rows/count: `5/6`
  - terminators: `10/10`
  - module-name matches: `1/10`
  - raw generations starting exactly with `---- MODULE`: `10/10`

Interpretation: `checkpoint-20` regresses against base and should be
ineligible for phase 2. Starting the module directly improved, but verifier
quality and syntax hygiene got worse.

Additional partial result:

- `checkpoint-40` JSON written:
  `outputs/eval/fullspec_phase1_ckpt40_160353.json`
- `checkpoint-40` on the same 10 rows:
  - SANY: `4/10`
  - depth-1 TLC: `4/10`
  - TLC: `1/10`
  - mean reward: `0.305`
  - syntax issue rows/count: `3/4`
  - terminators: `10/10`
  - module-name matches: `1/10`
  - raw generations starting exactly with `---- MODULE`: `10/10`

Interpretation: `checkpoint-40` is also an ineligible regression against base.
It is less bad than `checkpoint-20`, but still loses verifier passes, TLC pass,
mean reward, syntax hygiene, and module-name matching.

Final phase-1 eval result:

| Candidate | SANY | depth-1 | TLC | Mean reward | Syntax rows/count | Starts module | Module match |
|-----------|------|---------|-----|-------------|-------------------|---------------|--------------|
| base | `6/10` | `5/10` | `2/10` | `0.425` | `0/0` | `0/10` | `2/10` |
| checkpoint-20 | `3/10` | `3/10` | `1/10` | `0.23` | `5/6` | `10/10` | `1/10` |
| checkpoint-40 | `4/10` | `4/10` | `1/10` | `0.305` | `3/4` | `10/10` | `1/10` |
| checkpoint-60 | `3/10` | `3/10` | `1/10` | `0.23` | `1/2` | `10/10` | `1/10` |

Selection result:

- `160354` woke after `160353`, read the BF16 eval JSONs, wrote
  `outputs/eval/fullspec_phase2_selection_160354.json`, and selected `null`.
- No strict phase-2 training ran.
- `160355` woke after `160354`, found no phase-2 directory, and exited without
  eval.

Verdict: **do not publish and do not continue from any `160343` checkpoint**.
The run improved one superficial output-contract metric (`starts_module`) while
damaging the verifier metrics, syntax hygiene, and requested module-name match.

Next-run change:

- Add exact target module names to full-spec training prompts and eval prompts.
- Cap reward for completions whose `---- MODULE ... ----` name does not match
  the requested module.
- Include `target_module`, `produced_module`, and `module_match` in sample logs.
- Tighten phase-2 selection so syntax issue rows/count and module-name matching
  cannot regress against base.
- Run a smaller fresh-from-base diagnostic: 30 steps, LR `7.5e-7`, beta `0.08`,
  temperature `0.35`, save every `10`, sample every reward call.

New files/patches:

- `src/rlvr_canary/fullspec_dataset.py`: exact module name in user prompt.
- `src/rlvr_canary/fullspec_reward.py`: target-module extraction, mismatch cap,
  and module-match sample logging.
- `scripts/eval_fullspec_checkpoints.py`: exact module name in eval prompt.
- `scripts/qsub_grpo_sophia_fullspec_exact_module_diag.pbs`: bounded retry.
- `scripts/qsub_eval_sophia_fullspec_phase1_ckpts.pbs`: `PHASE_JOB` override.
- `scripts/qsub_grpo_sophia_fullspec_phase2_strict_select.pbs`: `PHASE1_JOB`
  override plus syntax/module no-regression gate.

Submitted exact-module retry chain:

- Train: `160362.sophia-pbs-01.lab.alcf.anl.gov`
  - queue `by-gpu`
  - running on `a Sophia GPU node`
  - log `outputs/logs/grpo_fullspec_exact_160362.log`
  - output `outputs/checkpoints_grpo_fullspec_phase1_160362`
  - samples `outputs/logs/grpo_fullspec_exact_160362_samples.jsonl`
- Phase-1 BF16 eval: `160363`, afterok `160362`, with `PHASE_JOB=160362`
- Gated strict phase 2: `160364`, afterok `160363`, with
  `EVAL_JOB=160363,PHASE1_JOB=160362`
- Phase-2 eval: `160365`, afterok `160364`, with `PHASE2_JOB=160364`

Early checks for `160362`:

- verify the prompt log shows exact module-name prompts;
- verify sample rows include `target_module`, `produced_module`, and
  `module_match`;
- after 10 steps, require reward variance and no systematic module mismatch;
- promote only if the BF16 eval `160363` beats or matches the exact-prompt base
  without syntax/module regressions.

Initial health check:

- `160362` started immediately on `a Sophia GPU node`.
- Step 1 completed with reward mean `0.3875`, reward std `0.1903`, clipped
  ratio `0.25`, grad norm `28.82`, and mean completion length `764`.
- Sample log exists at
  `outputs/logs/grpo_fullspec_exact_160362_samples.jsonl`.
- First sample rows include `target_module`, `produced_module`, and
  `module_match`.
- First sampled prompt target was `OrderLifecycle`; all four sampled
  completions used `OrderLifecycle` exactly.
- One sampled completion still had `empty_unchanged` and `typed_variables`, so
  syntax hygiene remains the thing to watch after `checkpoint-10`.

Checkpoint-10 health:

- At 16 logged metric rows, `checkpoint-10` exists.
- Mean reward so far: `0.329769`; max reward `0.675`.
- Reward std is nonzero on `13/16` rows.
- Mean clipped ratio remains `0.25`.
- Latest row: reward `0.27`, reward std `0`, grad norm `1.157`, LR
  `3.75e-7`, mean completion length `550`.
- Sample log has 64 rows.
- Module match is `64/64` among samples with target-module metadata.
- Syntax issue rows are `21/64`; recent issues are mostly `empty_unchanged`.

Interpretation: the exact-module patch fixed the module-name regression in
training samples, but syntax hygiene is still not fully controlled. Let the
30-step diagnostic finish and use BF16 eval `160363` as the real gate.

Final train health for `160362`:

- Training completed all `30/30` steps and released `160363`.
- Saved checkpoints: `checkpoint-10`, `checkpoint-20`, `checkpoint-30`.
- Mean reward across logged rows: `0.35846`; max reward `0.675`.
- Reward std was nonzero on `23/30` rows.
- Mean clipped ratio: `0.241667`.
- Final row: reward `0.28`, reward std `0`, grad norm `0.08678`, LR
  `2.5e-8`, clipped ratio `0.25`, mean completion length `588.8`.
- Sample log rows: `120`.
- Module match: `120/120` among samples with target-module metadata.
- Syntax issue rows: `32/120`.

Interpretation: exact-module control held for the full diagnostic. This still
needs BF16 eval because sample-level syntax issues remain common enough to
threaten verifier quality.

BF16 eval `160363` is running on `a Sophia GPU node`.

Eval-wrapper correction:

- `160363` was killed because the phase-1 eval wrapper still hard-coded
  checkpoints `20`, `40`, and `60`; the exact-module diagnostic saved
  `10`, `20`, and `30`.
- `scripts/qsub_eval_sophia_fullspec_phase1_ckpts.pbs` now discovers
  `checkpoint-*` directories from `PHASE_DIR` unless `EVAL_STEPS` is supplied.
- Corrected eval chain:
  - BF16 phase-1 eval `160377`, with `PHASE_JOB=160362`
  - gated phase-2 selector/train `160378`, with
    `EVAL_JOB=160377,PHASE1_JOB=160362`
  - phase-2 eval `160379`, with `PHASE2_JOB=160378`
- `160377` started immediately on `a Sophia GPU node`.

Live `160377` snapshot:

- Base exact-prompt eval is stronger than the first adapted checkpoint so far:
  - base: `sany_pass=6`, `depth1_pass=6`, `tlc_pass=4`, `mean_reward=0.52`
  - `checkpoint-10`: `sany_pass=3`, `depth1_pass=3`, `tlc_pass=1`,
    `mean_reward=0.23`
  - both runs have `module_match=10/10`
  - `checkpoint-10` already shows `syntax_issue_rows=3`, while the base has
    `syntax_issue_rows=0`
- `160377` is still running as of the latest check, so do not promote or relax
  the phase-2 gate from early evidence.
- If later checkpoints recover, the selector should still require a win over
  the exact-prompt base, not just over the old broken eval chain.
- Latest poll still shows only `fullspec_phase1_base_160377.json` and
  `fullspec_phase1_ckpt10_160377.json`; `checkpoint-20` and `checkpoint-30`
  have not written JSON outputs yet.
- The first adapted checkpoint is also emitting a concrete syntax/order bug:
  the raw spec defines `Next == ... \/ Terminating` before `Terminating ==`,
  and SANY reports `Unknown operator: Terminating`. The next data or reward
  pass should explicitly teach helper operators to appear before `Next`, or
  penalize this forward-reference pattern directly.
- The `checkpoint-20` eval has now landed and is even weaker than
  `checkpoint-10` on the fixed holdout:
  - `sany_pass=1`, `depth1_pass=1`, `tlc_pass=1`, `mean_reward=0.1`
  - `syntax_issue_rows=5`
  - errors now include malformed `Init`, bad `Next` fragments, and operator
    ordering problems rather than a single isolated bug
- That means the current exact-prompt GRPO phase is not yet moving toward a
  promotable checkpoint; the next loop needs either a stricter data filter for
  helper/operator ordering or a reward term that directly penalizes
  forward-reference / malformed-action patterns.
- `160377` is still running with `checkpoint-20` written and `checkpoint-30`
  still absent; keep the chain gated until the final artifact lands and the
  full trajectory can be judged instead of the partial middle.
- Latest live poll still shows only three JSON artifacts on disk for this
  gate: base, checkpoint-10, and checkpoint-20. `checkpoint-30` is visible in
  the log but has not written its JSON yet, so the phase remains unfinished.

## 2026-06-25 final phase-1 / phase-2 closure

The full `160377` sweep has now finished and the dependent phase-2 chain
closed cleanly.

- Final phase-1 checkpoint result:
  - `checkpoint-30`: `sany_pass=1`, `depth1_pass=1`, `tlc_pass=1`,
    `mean_reward=0.1`, `syntax_issue_rows=2`, `syntax_issue_count=2`
  - this remained far behind the exact-prompt base (`sany_pass=6`,
    `depth1_pass=6`, `tlc_pass=4`, `mean_reward=0.52`)
- Phase-2 selector result:
  - `outputs/eval/fullspec_phase2_selection_160378.json`
  - `selected: null`
  - all candidates were ineligible
- Phase-2 eval result:
  - `160379` wrote only the no-op header
  - `Phase-2 directory not present; gated phase-2 likely selected no eligible phase-1 checkpoint. Nothing to evaluate.`
- Scheduler closure:
  - `160377`, `160378`, and `160379` are all finished
  - no promotable full-spec checkpoint emerged from this chain

Implication:

The exact-prompt full-spec recipe is not yet solid enough for publication.
The next loop should not be another blind continuation. It should revise the
data or reward contract around malformed `Next`/helper ordering and bad action
fragments before another long run.

Current hardening:

- The full-spec developer prompt now explicitly says that helper operators used
  by `Next` must be defined before `Next`.
- The full-spec reward now detects forward references from `Next` to later
  helper definitions and caps those samples (`forward_reference_*` issues).
- This matches the failure mode seen in the `160377` sweep, where
  `checkpoint-30` still collapsed to `sany_pass=1` and the logs showed malformed
  `Next` / helper ordering patterns.

## 2026-06-25 next diagnostic

Queued a fresh full-spec diagnostic to validate the new contract:

- Job: `160386.sophia-pbs-01.lab.alcf.anl.gov`
- Queue: `single-node`
- Script: `scripts/qsub_grpo_sophia_fullspec_diag.pbs`
- Resources: `1:ngpus=4:ncpus=128:mem=480gb`
- Walltime: `02:00:00`
- Status at submit check: queued

This run is the first live test of the forward-reference penalty and updated
prompt wording. It should be watched for whether the sample logs stop showing
later-defined helpers inside `Next` and whether the reward variance stays
nonzero under the stricter contract.

## Publish readiness

The Hugging Face publisher already exists: `src.training.publish_hf`.
Publishing is **not** ready until a checkpoint passes the quality gate and has
been turned into deployable artifacts.

Current publish blockers:

- `checkpoint-100` passed the fixed 30-example action-holdout gate and was
  selected by `160268`.
- The current best RL artifact is still a LoRA adapter, not a
  merged/deployable model.
- Remote dry-run on Sophia reaches the real artifact blocker:
  `GGUF not found: /home/<user>/ChatTLA/outputs/gguf/chattla-20b-Q8_0.gguf`
- A fresh full benchmark is still required before publishing a new public model.

Publish path once a checkpoint is selected:

```bash
python -m src.training.merge_lora \
  --checkpoint outputs/checkpoints_grpo_action_tok1200_g4_phase2_sophia/checkpoint-240 \
  --base-model /grand/<ACCOUNT>/<user>/hf-cache/hub/models--EricSpencer00--chattla-20b/snapshots/c1a3e8b5c6916ce4a0ed830e996662ca28e0a262 \
  --output outputs/merged_model

python -m src.inference.convert_to_gguf \
  --quant Q8_0 \
  --no-ollama-register

python -m src.training.publish_hf \
  --dry-run \
  --require-fresh-full-benchmark-hours 24
```

Only remove `--dry-run` after:

- diagnostic cap samples show compact action-level completions;
- fixed holdout score is at least as good as the pre-GRPO baseline;
- a fresh full benchmark CSV exists and does not show a TLC regression;
- `outputs/gguf/chattla-20b-Q8_0.gguf` and `outputs/hf_readme/README.md` are
  present.

## Health gates

After the first 10 to 20 steps, grade the run before letting this recipe become
the next default.

Stop or revise if any of these hold:

- `completions/clipped_ratio > 0.8` for the first 10 logged steps;
- `reward_std == 0` for essentially all first 10 logged steps;
- reward never exceeds `0.075`;
- there are no naturally terminated completions;
- the job OOMs before the first checkpoint.

Promote or extend if:

- the job reaches at least `checkpoint-20`;
- clipped ratio is meaningfully below the previous `1.0`;
- reward variance appears in most batches;
- KL remains stable and non-explosive;
- sampled completions are closer to compact action-level answers.

## What to do better next run

1. Add completion sample logging every checkpoint. Metrics alone hid the most
   important question: what is the model actually writing for 192 to 256 tokens?
2. Evaluate `checkpoint-80`, Sophia `checkpoint-160`, and Sophia
   `checkpoint-240` against a fixed action holdout before comparing future
   adapters.
3. Add an abort script that tails the PBS log and kills the job when the health
   gates fail.
4. Tighten the prompt/output contract so the model is asked for the smallest
   action artifact that can be scored, not an open-ended explanation.
5. Track corpus statistics in the output directory: source corpus, row count,
   action harness count, prompt-token p50/p90/p99, and max gold action length.
6. Only scale walltime or step count after clipped ratio and holdout score
   improve.

## Overnight operating plan

1. Build `data/processed/diamond_sft_v3_action_tok1200.jsonl` on Polaris from
   the full diamond SFT v3 corpus using the model tokenizer and action prompt
   loader.
2. Submit the `tok1200_g4` PBS job to the `preemptable` queue with rerun
   enabled.
3. Confirm the job ID, log path, queue state, first checkpoint plan, and where
   the resume script will pick up.
4. In the morning, inspect:
   - PBS exit status;
   - first and final metric rows;
   - clipped ratio;
   - reward distribution;
   - checkpoint directories;
   - at least a few raw completions if logging is available.
5. Decide whether to continue with `g4`, fall back to `g2` plus better reward
   shaping, or switch to shorter rerunnable chunks before another overnight run.

## 2026-06-25 strategy check against the paper

The new TLA-Prover paper is a strong external check on the loop we are running
here. It mostly confirms the failure modes we already observed, and it shifts
the next strategic decision toward data and evaluation quality rather than raw
compute.

Paper-aligned takeaways:

- repair-based GRPO remains the right training shape; the paper's DPO ablation
  trails repair-GRPO by 10 points at Diamond, so static preference pairs are
  not the better next bet;
- truncation is a real learning problem, not just a logging annoyance;
  reward variance collapses when generations all hit the cap;
- stacked SFT regresses, so major corpus revisions should restart from a frozen
  base or fresh adapter path rather than compounding LoRA drift;
- content-level auditing matters more than file-path labels;
- smaller, higher-quality corpora beat larger noisy corpora;
- comment leakage is not cosmetic, because it burns completion budget before
  the model reaches the module body;
- a 30-problem holdout is enough for smoke decisions, but not enough for
  high-confidence strategy changes.

What we should do next:

1. Keep the repair-style GRPO path and keep the comment-stripping hygiene.
2. Bias the corpus toward harder protocol / case-analysis examples instead of
   reinforcing the easy invariant template.
3. Treat helper ordering, `Next` structure, and mutation-sensitive invariants as
   content-level gating checks, not just prompt suggestions.
4. Keep the 30-problem suite as a quick gate, but add a larger follow-on
   benchmark before any publish decision.
5. Treat disk pressure as a stop condition. If a run is likely to fill the
   filesystem or accumulate too many checkpoints/logs, shorten it or reroute it
   before the scheduler kills it.

Verdict: we are progressing, but the next meaningful gain comes from data and
eval refinement, not another blind increase in step count.

### Space-pressure postmortem

The latest full-spec diagnostic died because the heavy training artifacts were
still being written under `outputs/...` in the repo worktree, which lands on the
quota-limited home filesystem on Sophia. The model cache was already pointed at
`/grand`, but the checkpoints, stdout log, and sample log were not. That made
the run vulnerable to a root kill even though the training loop itself was
still healthy.

The wrappers now move full-spec logs and checkpoints to
`/grand/<ACCOUNT>/<user>/chattla_artifacts/fullspec/${PBS_JOBNUM}` instead of
the repo tree. Keep the eval JSONs in `outputs/eval` for now; they are small,
and the killer was the checkpoint/log path.

### 2026-06-25 diagnostic readout

The current BF16 full-spec eval chain closed without promotion:

- `160377` finished cleanly, but the exact-prompt phase-1 checkpoints did not
  beat the exact-prompt base;
- `160378` selected `null` and never launched phase 2;
- `160379` exited as the intended no-op because phase 2 was not eligible.

The active diagnostic `160386` is still useful, though. It shows the reward
contract is producing variance and the completions are much healthier than the
earlier flat-cap runs:

- 24 / 24 completions started the target module;
- 22 / 24 reached a terminator;
- reward mean `0.314` with std `0.134`;
- only 7 / 24 completions carried syntax-hygiene issues.

The remaining recurring issues are now narrower and more actionable:

- `typed_constants`
- `typed_variables`
- `empty_unchanged`

That is the next thing to attack. The reward floor now treats those patterns as
critical so they cannot sit near the top of the bronze band. If the next
diagnostic still favors them, the next move should be a prompt/data revision
rather than another long phase.

### 2026-06-25 direct-start warm-start readout

The direct-start contract and `reasoning_effort=none` path did what we hoped:
`160408` stayed on-contract across the whole 30-step warm start, and the sample
log showed perfect module starts and terminators. The follow-up holdout eval
`160417` was the important part, though, and it did not clear the promotion
bar.

Holdout summary for `160417` on the exact-prompt base and the three phase-1
checkpoints:

- base: `mean_reward = 0.415`, `sany = 6/10`, `depth1 = 6/10`, `tlc = 1/10`
- `checkpoint-10`: `mean_reward = 0.23`, `sany = 3/10`, `depth1 = 3/10`,
  `tlc = 1/10`
- `checkpoint-20`: `mean_reward = 0.36`, `sany = 5/10`, `depth1 = 5/10`,
  `tlc = 1/10`
- `checkpoint-30`: `mean_reward = 0.23`, `sany = 3/10`, `depth1 = 3/10`,
  `tlc = 1/10`

No checkpoint beat or matched the base on the holdout, so this branch should
not be promoted. The useful strategy change is to stop treating a clean
contract as sufficient on its own.

Next run guidance:

- keep the direct-start contract;
- do not launch another broad 30-step phase unless the reward shape changes;
- if we run again, make it a smaller bounded diagnostic that targets the
  remaining syntax and helper-order failures directly;
- prefer early checkpoint selection over “train through 30 and hope the tail
  recovers”;
- promote only when holdout clears the base and the sample log stays clean.

The current evidence says the contract fix is necessary but not sufficient.
