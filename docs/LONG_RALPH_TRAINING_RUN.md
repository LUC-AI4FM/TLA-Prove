# Long Ralph Training Run

Goal: train the canonical ChatTLA student from long verifier-guided repair
trajectories, using Ollama Cloud as the strong repair teacher and `REDACTED-HOST`
as the durable artifact store and cloud-only launch host.

## Host roles

- `REDACTED-HOST.cs.luc.edu`: default cloud-only long-Ralph host plus artifact store for trajectories, repair pairs, summaries, checkpoints, and logs.
- `REDACTED-HOST`: optional GPU host for the retrain phase if you explicitly want a local GRPO pass.
- `polaris`: fastest training host; use once collection/training smoke passes and queue time is acceptable.

## Key setup

Paste the Ollama key into each host that may call the teacher:

```bash
ssh HOST 'mkdir -p ~/.config/chattla && chmod 700 ~/.config/chattla && bash -lc '"'"'read -rsp "OLLAMA_API_KEY: " key; echo; umask 077; printf "export OLLAMA_API_KEY=%q\n" "$key" > ~/.config/chattla/ollama.env; echo saved ~/.config/chattla/ollama.env'"'"''
```

Replace `HOST` with `REDACTED-HOST.cs.luc.edu`, `REDACTED-HOST`, or `polaris`.

## Run

From `REDACTED-HOST` for cloud-only collection, or a GPU host if you want the local retrain phase:

```bash
cd /path/to/ChatTLA
scripts/launch_long_ralph_training.sh start
tmux attach -t chattla-long-ralph
```

Useful overrides:

```bash
export CHATTLA_MAX_PROMPTS=120
export CHATTLA_MAX_ITERS=64
export OLLAMA_CLOUD_MODEL=qwen3-coder:480b
export CHATTLA_BASE_MODEL=EricSpencer00/chattla-20b
export CHATTLA_AISEC_STORE=REDACTED-HOST.cs.luc.edu:~/chattla-long-runs
export CHATTLA_CLOUD_ONLY=1
export CHATTLA_SKIP_GRPO=1
export CHATTLA_INITIAL_PROVIDER=teacher
export CHATTLA_REPAIR_PROVIDER=teacher
export CHATTLA_LOCAL_MODEL_AUDIT=0
```

## Acceptance workflow

Use two stages:

1. Proof collection: `CHATTLA_ACCEPTANCE_MODE=proof` and `CHATTLA_SUCCESS_GATE=gold`.
   This stops once a candidate passes SANY and TLC. It is the default launcher mode
   on `REDACTED-HOST` when `CHATTLA_CLOUD_ONLY=1`, because it banks proof-passing
   candidates without spending local GPU cycles on the retrain phase.
2. Modeling audit: rerun with `CHATTLA_ACCEPTANCE_MODE=audit` and
   `CHATTLA_SUCCESS_GATE=diamond`. This adds the deterministic local modeling audit
   plus the optional final adequacy judge, checking that invariants, temporal
   properties, fairness, waiting state, acquire/release actions, and domain actors
   are actually represented.

The collector records both `proof_success` and final `success` on each step, so
proof-passing specs remain visible even when a modeling audit rejects them.

## Stop policy

The collector is adaptive, not three-shot:

- stop on diamond success plus final LLM adequacy judge by default;
- stop on repeated malformed generations;
- stop on repeated verifier failure signature;
- stop on repeated byte-identical spec;
- stop after score stalls;
- keep `CHATTLA_MAX_ITERS` as a watchdog, not the target.

The final judge is enabled by default in `scripts/collect_long_ralph_trajectories.py`.
It runs after SANY/TLC/diamond pass and rejects specs that are valid TLA+ but do
not actually model the natural-language requirement.

Evaluation reports fixed `pass@1/3/8/15/20` curves for comparability.

## Latest snapshot

Latest checked run: `REDACTED-HOST:/home/REDACTED-USER/ChatTLA/data/processed/long_ralph/run_20260609_083126`

- repair mode: `diff`
- prompts completed: `3`
- accepted specs: `0`
- run-level success count: `0`

Per-prompt outcome:

- `topic_BinarySemaphore`: `185` iterations, best tier `silver`, best score `0.366`, stop reason `frontier_stall`
- `topic_CountingSemaphore`: `118` iterations, best tier `gold`, best score `0.5`, stop reason `frontier_stall`
- `topic_ReadWriteLock`: `123` iterations, best tier `gold`, best score `0.5`, stop reason `frontier_stall`

Recent failure mix in the last `120` steps was dominated by syntax and liveness
adequacy issues rather than long TLC timeout loops:

- `syntax`: `61`
- `weak_fairness`: `29`
- `tlc`: `8`
- `property_violation`: `9`

Interpretation: the diff-repair path is moving the search into more localized
spec edits and repeated adequacy/liveness corrections, but it has not yet
produced accepted specs on this run.

Follow-up fix: the loop now repairs from the strongest current frontier candidate
instead of the most recent regressed child. TLC is also run with coverage enabled,
with a static action-name fallback, so proof-passing specs are not mislabeled as
having zero action coverage when TLC did not print coverage rows.
