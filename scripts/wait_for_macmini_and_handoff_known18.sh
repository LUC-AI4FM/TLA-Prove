#!/usr/bin/env bash
set -euo pipefail

LOCAL_REPO="${CHATTLA_LOCAL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RELAY_HOST="${CHATTLA_RELAY_HOST:-${CHATTLA_MAC_HOST:-}}"
RELAY_KEY="${CHATTLA_RELAY_KEY:-${CHATTLA_MAC_KEY:-$HOME/.ssh/id_ed25519}}"
RELAY_REPO="${CHATTLA_RELAY_REPO:-${CHATTLA_MAC_REPO:-$HOME/ChatTLA}}"
RELAY_LABEL="${CHATTLA_RELAY_LABEL:-relay}"
SOPHIA_CTL="${SOPHIA_CTL:-$HOME/.ssh/${CHATTLA_SOPHIA_CTL_NAME:-chattla-remote-ctl}}"
REMOTE_HOST="${CHATTLA_REMOTE_HOST:-${SOPHIA_HOST:-}}"
REMOTE_REPO="${CHATTLA_REMOTE_REPO:-ChatTLA}"
LOG_DIR="${CHATTLA_HANDOFF_LOG_DIR:-$LOCAL_REPO/outputs/logs}"
SLEEP_SECONDS="${CHATTLA_MACMINI_WAIT_SLEEP:-60}"
MAX_ATTEMPTS="${CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS:-0}"
MIRROR_ONLY=0
HANDOFF_ARGS=()

if [ -z "$RELAY_HOST" ]; then
  echo "Set CHATTLA_RELAY_HOST or CHATTLA_MAC_HOST to the relay SSH target." >&2
  exit 2
fi
if [ -z "$REMOTE_HOST" ]; then
  echo "Set CHATTLA_REMOTE_HOST or SOPHIA_HOST to the remote SSH target." >&2
  exit 2
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mirror-report-only)
      MIRROR_ONLY=1
      ;;
    *)
      HANDOFF_ARGS+=("$1")
      ;;
  esac
  shift
done

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/wait_for_macmini_handoff.log"
MIRROR_FAILURE_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission_mirror_failed.json"

ts() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

ssh_probe() {
  ssh \
    -o ConnectTimeout=10 \
    -o BatchMode=yes \
    -o PubkeyAuthentication=yes \
    -o PasswordAuthentication=no \
    -o IdentitiesOnly=yes \
    -i "$RELAY_KEY" \
    "$RELAY_HOST" \
    "true" >/dev/null 2>&1
}

mirror_remote_report() {
  local report="outputs/manifests/tla_prover_remote_submission.json"
  mkdir -p "$LOCAL_REPO/outputs/manifests"
  ssh \
    -o ConnectTimeout=10 \
    -o BatchMode=yes \
    -o PubkeyAuthentication=yes \
    -o PasswordAuthentication=no \
    -o IdentitiesOnly=yes \
    -i "$RELAY_KEY" \
    "$RELAY_HOST" \
    "cd '$RELAY_REPO' && rsync -az -e \"ssh -o BatchMode=yes -S '$SOPHIA_CTL'\" '$REMOTE_HOST:$REMOTE_REPO/$report' '$RELAY_REPO/$report'" \
    >> "$LOG" 2>&1 || return 1
  rsync -az \
    -e "ssh -o ConnectTimeout=10 -o BatchMode=yes -o PubkeyAuthentication=yes -o PasswordAuthentication=no -o IdentitiesOnly=yes -i $RELAY_KEY" \
    "$RELAY_HOST:$RELAY_REPO/$report" "$LOCAL_REPO/$report" >> "$LOG" 2>&1
}

write_mirror_failure_report() {
  mkdir -p "$(dirname "$MIRROR_FAILURE_REPORT")"
  python3 - "$MIRROR_FAILURE_REPORT" "$RELAY_HOST" "$RELAY_LABEL" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "stage": "mirror_remote_report",
    "exit_code": 76,
    "relay_host": sys.argv[2],
    "relay_label": sys.argv[3],
    "next_action": "Retry mirror only; do not resubmit known-18 until this report is cleared.",
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

start_watcher() {
  echo "[$(ts)] starting remote result watcher" >> "$LOG"
  scripts/watch_tla_prover_remote_results.sh \
    --max-attempts "${CHATTLA_RESULTS_WATCH_MAX_ATTEMPTS:-120}" \
    --sleep-seconds "${CHATTLA_RESULTS_WATCH_SLEEP:-120}" >> "$LOG" 2>&1 || true
}

mirror_or_record_failure() {
  if mirror_remote_report; then
    rm -f "$MIRROR_FAILURE_REPORT"
    echo "[$(ts)] mirrored outputs/manifests/tla_prover_remote_submission.json" >> "$LOG"
    start_watcher
    return 0
  fi
  write_mirror_failure_report
  echo "[$(ts)] handoff completed but report mirror failed" >> "$LOG"
  return 76
}

echo "[$(ts)] waiting for $RELAY_LABEL SSH host=$RELAY_HOST" >> "$LOG"

attempt=0
while true; do
  attempt=$((attempt + 1))
  if ssh_probe; then
    if [ "$MIRROR_ONLY" = "1" ]; then
      echo "[$(ts)] $RELAY_LABEL reachable; retrying remote submission report mirror only" >> "$LOG"
      cd "$LOCAL_REPO"
      mirror_or_record_failure
      exit $?
    fi
    echo "[$(ts)] $RELAY_LABEL reachable; running handoff once" >> "$LOG"
    cd "$LOCAL_REPO"
    set +e
    if [ "${#HANDOFF_ARGS[@]}" -gt 0 ]; then
      scripts/sync_macmini_and_submit_known18.sh "${HANDOFF_ARGS[@]}" >> "$LOG" 2>&1
    else
      scripts/sync_macmini_and_submit_known18.sh >> "$LOG" 2>&1
    fi
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      echo "[$(ts)] handoff completed; attempting remote submission report mirror" >> "$LOG"
      mirror_or_record_failure
      exit $?
    fi
    echo "[$(ts)] handoff failed rc=$rc" >> "$LOG"
    exit "$rc"
  fi

  echo "[$(ts)] $RELAY_LABEL not reachable attempt=$attempt; retrying in ${SLEEP_SECONDS}s" >> "$LOG"
  if [ "$MAX_ATTEMPTS" != "0" ] && [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "[$(ts)] giving up after $attempt attempts" >> "$LOG"
    exit 75
  fi

  sleep "$SLEEP_SECONDS"
done
