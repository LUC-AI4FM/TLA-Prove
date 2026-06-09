#!/usr/bin/env bash
# Long Ralph trajectory collection + repair-GRPO launcher.
#
# Usage:
#   scripts/launch_long_ralph_training.sh start
#   scripts/launch_long_ralph_training.sh status
#   scripts/launch_long_ralph_training.sh logs
#   scripts/launch_long_ralph_training.sh stop
#
# Required before start:
#   ~/.config/chattla/ollama.env containing: export OLLAMA_API_KEY=...

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

SESSION="${CHATTLA_TMUX_SESSION:-chattla-long-ralph}"
LOG_DIR="${CHATTLA_LOG_DIR:-outputs/logs}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/long_ralph_training.log"

PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PY=".venv/bin/python"
  else
    PY="python3"
  fi
fi

ts() { date '+%Y-%m-%d %H:%M:%S'; }

load_env() {
  if [[ -f "$HOME/.config/chattla/ollama.env" ]]; then
    # shellcheck disable=SC1090
    source "$HOME/.config/chattla/ollama.env"
  fi
  if [[ -f "$HOME/.config/tla-generator/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.config/tla-generator/.env"
    set +a
  fi
  if [[ -x "$HOME/.local/opt/jdk-17.0.13+11/bin/java" ]]; then
    export JAVA_HOME="$HOME/.local/opt/jdk-17.0.13+11"
    export PATH="$JAVA_HOME/bin:$PATH"
  fi
}

sync_to_aisec() {
  local path="$1"
  local remote="${CHATTLA_AISEC_STORE:-REDACTED-HOST.cs.luc.edu:~/chattla-long-runs}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -az "$path/" "$remote/$(hostname -s)-$(basename "$path")/" \
      >>"$LOG" 2>&1 || echo "[$(ts)] WARN: rsync to $remote failed" | tee -a "$LOG"
  fi
}

run_pipeline() {
  load_env
  if [[ -z "${OLLAMA_API_KEY:-}" ]]; then
    echo "[$(ts)] ERROR: OLLAMA_API_KEY missing. Create ~/.config/chattla/ollama.env" | tee -a "$LOG"
    exit 1
  fi

  export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
  export CHATTLA_BASE_MODEL="${CHATTLA_BASE_MODEL:-EricSpencer00/chattla-20b}"
  export OLLAMA_CLOUD_MODEL="${OLLAMA_CLOUD_MODEL:-qwen3-coder:480b}"

  local stamp
  stamp="$(date '+%Y%m%d_%H%M%S')"
  local run_dir="${CHATTLA_LONG_RALPH_DIR:-data/processed/long_ralph/run_$stamp}"
  mkdir -p "$run_dir"
  local run_abs
  run_abs="$(cd "$(dirname "$run_dir")" && pwd)/$(basename "$run_dir")"

  echo "[$(ts)] ===== Long Ralph Training Run =====" | tee -a "$LOG"
  echo "[$(ts)] repo=$REPO" | tee -a "$LOG"
  echo "[$(ts)] python=$PY" | tee -a "$LOG"
  echo "[$(ts)] run_dir=$run_dir" | tee -a "$LOG"
  echo "[$(ts)] base=$CHATTLA_BASE_MODEL teacher=$OLLAMA_CLOUD_MODEL" | tee -a "$LOG"

  local freeze_arg
  case "${CHATTLA_FREEZE_PROPERTIES:-0}" in
    1|true|TRUE|yes|YES) freeze_arg="--freeze-properties" ;;
    *) freeze_arg="--no-freeze-properties" ;;
  esac

  local semantic_stall_arg
  case "${CHATTLA_SEMANTIC_STALL_STOP:-1}" in
    0|false|FALSE|no|NO) semantic_stall_arg="--no-semantic-stall-stop" ;;
    *) semantic_stall_arg="--semantic-stall-stop" ;;
  esac

  echo "[$(ts)] Phase 1: collect long Ralph trajectories" | tee -a "$LOG"
  "$PY" -u -m scripts.collect_long_ralph_trajectories \
    --student-model "${CHATTLA_STUDENT_MODEL:-chattla:20b}" \
    --teacher-model "$OLLAMA_CLOUD_MODEL" \
    --initial-provider "${CHATTLA_INITIAL_PROVIDER:-student}" \
    --repair-provider "${CHATTLA_REPAIR_PROVIDER:-teacher}" \
    --repair-mode "${CHATTLA_REPAIR_MODE:-diff}" \
    --success-gate "${CHATTLA_SUCCESS_GATE:-diamond}" \
    --max-iters "${CHATTLA_MAX_ITERS:-0}" \
    --max-same-failure-family-iters "${CHATTLA_MAX_SAME_FAILURE_FAMILY_ITERS:-24}" \
    --max-frontier-stall-iters "${CHATTLA_MAX_FRONTIER_STALL_ITERS:-96}" \
    --branch-after-iters "${CHATTLA_BRANCH_AFTER_ITERS:-20}" \
    --branch-width "${CHATTLA_BRANCH_WIDTH:-5}" \
    --branch-iters "${CHATTLA_BRANCH_ITERS:-8}" \
    --max-prompts "${CHATTLA_MAX_PROMPTS:-120}" \
    "$freeze_arg" \
    "$semantic_stall_arg" \
    --num-shards "${CHATTLA_NUM_SHARDS:-1}" \
    --shard-index "${CHATTLA_SHARD_INDEX:-0}" \
    --tlc-timeout "${CHATTLA_TLC_TIMEOUT:-45}" \
    --out-trajectories "$run_dir/trajectories.jsonl" \
    --out-pairs "$run_dir/repair_pairs.jsonl" \
    --out-step-events "$run_dir/step_events.jsonl" \
    --out-live-pairs "$run_dir/repair_pairs_live.jsonl" \
    --out-accepted-dir "$run_dir/accepted_specs" \
    --run-report "$run_dir/run_report.json" \
    --summary "$run_dir/summary.json" \
    2>&1 | tee -a "$LOG"

  ln -sfn "$run_abs" data/processed/long_ralph/latest
  cp "$run_dir/repair_pairs.jsonl" data/processed/ralph_repair_pairs_long_latest.jsonl
  sync_to_aisec "$run_dir"

  local pairs
  pairs="$(wc -l < "$run_dir/repair_pairs.jsonl" | tr -d ' ')"
  echo "[$(ts)] collected repair pairs=$pairs" | tee -a "$LOG"
  if [[ "$pairs" -lt "${CHATTLA_MIN_REPAIR_PAIRS:-100}" ]]; then
    echo "[$(ts)] ERROR: too few repair pairs; skipping GRPO" | tee -a "$LOG"
    exit 1
  fi

  echo "[$(ts)] Phase 2: unload local Ollama models before training" | tee -a "$LOG"
  curl -s http://localhost:11434/api/generate \
    -d "{\"model\":\"${CHATTLA_STUDENT_MODEL:-chattla:20b}\",\"keep_alive\":0}" \
    >/dev/null 2>&1 || true
  sleep 5

  echo "[$(ts)] Phase 3: repair-GRPO from canonical ChatTLA" | tee -a "$LOG"
  export CHATTLA_REWARD_WORKERS="${CHATTLA_REWARD_WORKERS:-4}"
  export CHATTLA_REWARD_TLC_TIMEOUT="${CHATTLA_REWARD_TLC_TIMEOUT:-30}"
  "$PY" -u -m scripts.train_rl_repair \
    --model "$CHATTLA_BASE_MODEL" \
    --trajectory-file "$run_dir/repair_pairs.jsonl" \
    --output-dir "${CHATTLA_GRPO_OUT:-outputs/checkpoints_long_ralph_repair}" \
    --max-steps "${CHATTLA_GRPO_STEPS:-200}" \
    --num-generations "${CHATTLA_NUM_GENERATIONS:-4}" \
    --max-completion-length "${CHATTLA_MAX_COMPLETION:-768}" \
    --max-prompt-tokens "${CHATTLA_MAX_PROMPT_TOKENS:-2200}" \
    --min-before-score "${CHATTLA_MIN_BEFORE_SCORE:-0.02}" \
    --max-before-score "${CHATTLA_MAX_BEFORE_SCORE:-0.90}" \
    --difficulty all \
    --save-steps "${CHATTLA_SAVE_STEPS:-25}" \
    2>&1 | tee -a "$LOG"

  echo "[$(ts)] Phase 4: sync checkpoints/logs to aisec store" | tee -a "$LOG"
  sync_to_aisec "$run_dir"
  sync_to_aisec "${CHATTLA_GRPO_OUT:-outputs/checkpoints_long_ralph_repair}"
  echo "[$(ts)] ===== Long Ralph Training Run Finished =====" | tee -a "$LOG"
}

case "${1:-start}" in
  start)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      echo "tmux session already exists: $SESSION"
      echo "Attach: tmux attach -t $SESSION"
      exit 0
    fi
    tmux new-session -d -s "$SESSION" "cd '$REPO' && bash scripts/launch_long_ralph_training.sh run"
    echo "Started $SESSION"
    echo "Attach: tmux attach -t $SESSION"
    echo "Logs:   tail -f $LOG"
    ;;
  run)
    run_pipeline
    ;;
  status)
    tmux has-session -t "$SESSION" 2>/dev/null && tmux list-sessions | grep "$SESSION" || {
      echo "No tmux session: $SESSION"
      exit 1
    }
    ;;
  logs)
    tail -f "$LOG"
    ;;
  stop)
    tmux kill-session -t "$SESSION"
    ;;
  *)
    echo "Usage: $0 {start|run|status|logs|stop}" >&2
    exit 2
    ;;
esac
