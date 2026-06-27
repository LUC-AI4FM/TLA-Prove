#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_REPO="${CHATTLA_LOCAL_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SUBMISSION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission.json"
COLLECTION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_results_collection.json"
WATCH_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_watch.json"
DECISION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_decision.json"
COLLECTOR="${CHATTLA_RESULTS_COLLECTOR:-$LOCAL_REPO/scripts/collect_tla_prover_remote_results.sh}"
EVALUATOR="${CHATTLA_RESULTS_EVALUATOR:-$SCRIPT_DIR/evaluate_tla_prover_remote_results.py}"
SLEEP_SECONDS="${CHATTLA_RESULTS_WATCH_SLEEP:-120}"
MAX_ATTEMPTS="${CHATTLA_RESULTS_WATCH_MAX_ATTEMPTS:-0}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --sleep-seconds)
      SLEEP_SECONDS="$2"
      shift
      ;;
    --max-attempts)
      MAX_ATTEMPTS="$2"
      shift
      ;;
    --submission-report)
      SUBMISSION_REPORT="$2"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/watch_tla_prover_remote_results.sh [--max-attempts N] [--sleep-seconds N]

Wait for outputs/manifests/tla_prover_remote_submission.json, repeatedly run
collect_tla_prover_remote_results.sh, and stop once known-18 summary evidence
and the expected SFT preflight log are mirrored locally, then write
outputs/manifests/tla_prover_remote_decision.json.
EOF
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

mkdir -p "$(dirname "$WATCH_REPORT")" "$LOCAL_REPO/outputs/logs"
LOG="$LOCAL_REPO/outputs/logs/watch_tla_prover_remote_results.log"

write_watch_report() {
  local status="$1"
  local attempts="$2"
  local message="$3"
  python3 - "$WATCH_REPORT" "$SUBMISSION_REPORT" "$COLLECTION_REPORT" "$status" "$attempts" "$message" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

watch_path = Path(sys.argv[1])
submission_path = Path(sys.argv[2])
collection_path = Path(sys.argv[3])
status = sys.argv[4]
attempts = int(sys.argv[5])
message = sys.argv[6] or None

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "attempts": attempts,
    "message": message,
    "submission_report": str(submission_path),
    "collection_report": str(collection_path),
    "decision_report": "outputs/manifests/tla_prover_remote_decision.json",
}
if submission_path.exists():
    try:
        payload["submission"] = json.loads(submission_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        payload["submission_error"] = str(exc)
if collection_path.exists():
    try:
        payload["collection"] = json.loads(collection_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        payload["collection_error"] = str(exc)
watch_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

is_complete() {
  python3 - "$SUBMISSION_REPORT" "$COLLECTION_REPORT" <<'PY'
import json
import sys
from pathlib import Path

submission_path = Path(sys.argv[1])
collection_path = Path(sys.argv[2])
if not submission_path.exists() or not collection_path.exists():
    raise SystemExit(1)
submission = json.loads(submission_path.read_text(encoding="utf-8"))
collection = json.loads(collection_path.read_text(encoding="utf-8"))
if submission.get("ok") is False:
    raise SystemExit(2)
mirrored = set(collection.get("mirrored", []))
known18 = submission.get("known18_job_id")
sft = submission.get("sft_preflight_job_id")
if not known18:
    raise SystemExit(1)
known18_job = known18.split(".", 1)[0]
# Operator-search literal: known18_corrected_smoke_${KNOWN18_JOBNUM}.summary.json
required = {f"outputs/autoprover/known18_corrected_smoke_{known18_job}.summary.json"}
if sft:
    sft_job = sft.split(".", 1)[0]
    # Operator-search literal: sft_preflight_${SFT_JOBNUM}.log
    required.add(f"outputs/logs/sft_preflight_{sft_job}.log")
missing = sorted(required - mirrored)
if missing:
    print("\n".join(missing))
    raise SystemExit(1)
PY
}

known18_summary_path() {
  python3 - "$SUBMISSION_REPORT" "$LOCAL_REPO" <<'PY'
import json
import sys
from pathlib import Path

submission = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
job_id = submission["known18_job_id"].split(".", 1)[0]
print(Path(sys.argv[2]) / "outputs" / "autoprover" / f"known18_corrected_smoke_{job_id}.summary.json")
PY
}

write_decision_report() {
  local summary_path
  summary_path="$(known18_summary_path)"
  python3 "$EVALUATOR" --summary "$summary_path" --out "$DECISION_REPORT"
}

attempt=0
while true; do
  attempt=$((attempt + 1))
  if [ ! -f "$SUBMISSION_REPORT" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] waiting for submission report attempt=$attempt" >> "$LOG"
    if [ "$MAX_ATTEMPTS" != "0" ] && [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
      write_watch_report timeout "$attempt" "submission report not present"
      exit 75
    fi
    sleep "$SLEEP_SECONDS"
    continue
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] collecting remote results attempt=$attempt" >> "$LOG"
  set +e
  "$COLLECTOR" --submission-report "$SUBMISSION_REPORT" >> "$LOG" 2>&1
  collect_rc=$?
  set -e
  if [ "$collect_rc" -ne 0 ]; then
    if is_complete; then
      set +e
      write_decision_report >> "$LOG" 2>&1
      decision_rc=$?
      set -e
      if [ "$decision_rc" -eq 0 ]; then
        write_watch_report complete "$attempt" "required evidence mirrored despite collector rc=$collect_rc; decision report written"
        exit 0
      fi
      write_watch_report evaluating "$attempt" "collector returned rc=$collect_rc and decision evaluator returned rc=$decision_rc"
    else
      write_watch_report collecting "$attempt" "collector returned rc=$collect_rc"
    fi
  elif is_complete; then
    set +e
    write_decision_report >> "$LOG" 2>&1
    decision_rc=$?
    set -e
    if [ "$decision_rc" -eq 0 ]; then
      write_watch_report complete "$attempt" "required evidence mirrored and decision report written"
      exit 0
    fi
    write_watch_report evaluating "$attempt" "decision evaluator returned rc=$decision_rc"
  else
    write_watch_report collecting "$attempt" "required evidence not mirrored yet"
  fi

  if [ "$MAX_ATTEMPTS" != "0" ] && [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    write_watch_report timeout "$attempt" "required evidence not mirrored before max attempts"
    exit 75
  fi
  sleep "$SLEEP_SECONDS"
done
