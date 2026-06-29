#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CHATTLA_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CODEX="${CODEX_BIN:-$HOME/.local/bin/codex}"
LOG_DIR="$REPO/outputs/logs"
PROMPT="$LOG_DIR/macmini_codex_goal_prompt.txt"
LOG="$LOG_DIR/macmini_codex_goal.exec.log"
LAST="$LOG_DIR/macmini_codex_goal.last.txt"
WRAPPER="$LOG_DIR/macmini_codex_goal.wrapper.log"
PIDFILE="$LOG_DIR/macmini_codex_goal.worker.pid"
STATUS="$LOG_DIR/macmini_codex_goal.status.json"
MAX_LOG_BYTES="${CHATTLA_CODEX_LOG_MAX_BYTES:-10485760}"

export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export TERM="${TERM:-xterm-256color}"

ts() { date -u +%FT%TZ; }

die() {
  echo "[$(ts)] supervisor fatal: $*" >&2
  exit 1
}

sha256() {
  shasum -a 256 "$1" | awk '{print $1}'
}

rotate_log() {
  local file="$1"
  [ -f "$file" ] || return 0
  local bytes
  bytes="$(wc -c < "$file" | tr -d ' ')"
  if [ "${bytes:-0}" -gt "$MAX_LOG_BYTES" ]; then
    mv "$file" "$file.1"
    : > "$file"
  fi
}

write_status() {
  local state="$1"
  local worker_pid="${2:-}"
  local prompt_hash=""
  if [ -f "$PROMPT" ]; then
    prompt_hash="$(sha256 "$PROMPT")"
  fi
  cat > "$STATUS" <<JSON
{
  "updated_at": "$(ts)",
  "state": "$state",
  "supervisor_pid": $$,
  "worker_pid": "${worker_pid}",
  "repo": "$REPO",
  "codex": "$CODEX",
  "prompt_sha256": "$prompt_hash"
}
JSON
}

preflight() {
  [ -d "$REPO" ] || die "repo missing: $REPO"
  [ -x "$CODEX" ] || die "codex binary missing or not executable: $CODEX"
  mkdir -p "$LOG_DIR"
  [ -f "$PROMPT" ] || die "prompt missing: $PROMPT"
  [ -w "$LOG_DIR" ] || die "log dir not writable: $LOG_DIR"
}

worker_running() {
  [ -f "$PIDFILE" ] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" >/dev/null 2>&1 || return 1
  ps -p "$pid" -o command= | grep -F "$CODEX exec" >/dev/null 2>&1
}

preflight

while true; do
  rotate_log "$LOG"
  rotate_log "$WRAPPER"

  if worker_running; then
    pid="$(cat "$PIDFILE")"
    write_status "running" "$pid"
    echo "[$(ts)] supervisor heartbeat: codex worker running pid=$pid" >> "$WRAPPER"
    sleep "${CHATTLA_CODEX_SUPERVISOR_SLEEP:-300}"
    continue
  fi

  rm -f "$PIDFILE"
  echo "[$(ts)] supervisor launching codex goal worker" >> "$WRAPPER"
  cd "$REPO"
  /usr/bin/caffeinate -dimsu "$CODEX" exec \
    --dangerously-bypass-approvals-and-sandbox \
    -s danger-full-access \
    -C "$REPO" \
    -o "$LAST" \
    - < "$PROMPT" >> "$LOG" 2>&1 &
  pid="$!"
  echo "$pid" > "$PIDFILE"
  write_status "launched" "$pid"
  wait "$pid" || rc="$?"
  rc="${rc:-0}"
  rm -f "$PIDFILE"
  write_status "exited" ""
  echo "[$(ts)] supervisor observed codex worker exit rc=$rc; relaunching after backoff" >> "$WRAPPER"
  unset rc
  sleep "${CHATTLA_CODEX_RESTART_BACKOFF:-60}"
done
