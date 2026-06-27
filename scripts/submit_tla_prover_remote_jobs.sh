#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMIT_SFT_PREFLIGHT=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift
      ;;
    --submit-sft-preflight|--submit-all)
      SUBMIT_SFT_PREFLIGHT=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/submit_tla_prover_remote_jobs.sh [--repo PATH] [--submit-sft-preflight]

Run remote preflight checks inside a synced Sophia checkout, submit the
corrected known-18 TLAPS smoke, optionally submit the bounded SFT startup
preflight, and write outputs/manifests/tla_prover_remote_submission.json.
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

cd "$REPO"
mkdir -p outputs/manifests outputs/logs

REPORT="outputs/manifests/tla_prover_remote_submission.json"
PREFLIGHT="${CHATTLA_REMOTE_PREFLIGHT:-scripts/preflight_tla_prover_remote.py}"
TLAPM="${CHATTLA_TLAPM:-tlapm}"
PBS_ACCOUNT="${CHATTLA_PBS_ACCOUNT:-}"
PBS_QUEUE="${CHATTLA_PBS_QUEUE:-}"
PBS_FILESYSTEMS="${CHATTLA_PBS_FILESYSTEMS:-}"
PBS_SELECT_KNOWN18="${CHATTLA_PBS_SELECT_KNOWN18:-${CHATTLA_PBS_SELECT:-}}"
PBS_WALLTIME_KNOWN18="${CHATTLA_PBS_WALLTIME_KNOWN18:-${CHATTLA_PBS_WALLTIME:-}}"
PBS_SELECT_SFT="${CHATTLA_PBS_SELECT_SFT:-${CHATTLA_PBS_SELECT:-}}"
PBS_WALLTIME_SFT="${CHATTLA_PBS_WALLTIME_SFT:-${CHATTLA_PBS_WALLTIME:-}}"
HOSTNAME_VALUE="$(hostname 2>/dev/null || echo unknown)"
KNOWN18_JOB_ID=""
SFT_PREFLIGHT_JOB_ID=""

write_report() {
  local ok="$1"
  local stage="$2"
  local exit_code="$3"
  local error="$4"
  python3 - "$REPORT" "$ok" "$stage" "$exit_code" "$error" "$KNOWN18_JOB_ID" "$SFT_PREFLIGHT_JOB_ID" "$SUBMIT_SFT_PREFLIGHT" "$REPO" "$HOSTNAME_VALUE" "$TLAPM" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

report_path = Path(sys.argv[1])
ok = sys.argv[2] == "true"
stage = sys.argv[3]
exit_code = int(sys.argv[4])
error = sys.argv[5] or None
known18_job_id = sys.argv[6] or None
sft_preflight_job_id = sys.argv[7] or None
submit_sft_preflight = sys.argv[8] == "1"
repo = sys.argv[9]
hostname = sys.argv[10]
tlapm = sys.argv[11]

report = {
    "ok": ok,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repo": repo,
    "hostname": hostname,
    "stage": stage,
    "exit_code": exit_code,
    "error": error,
    "tlapm": tlapm,
    "known18_job_id": known18_job_id,
    "sft_preflight_job_id": sft_preflight_job_id,
    "submit_sft_preflight": submit_sft_preflight,
    "known18_pbs": "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
    "sft_preflight_pbs": "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
    "preflight_log": "outputs/logs/tla_prover_remote_preflight.log",
    "known18_qsub_log": "outputs/logs/tla_prover_known18_qsub.log",
    "sft_preflight_qsub_log": "outputs/logs/tla_prover_sft_preflight_qsub.log",
}
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2, sort_keys=True))
PY
}

run_stage() {
  local stage="$1"
  local output_file="$2"
  shift 2
  set +e
  "$@" > "$output_file" 2>&1
  local rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    write_report false "$stage" "$rc" "$(tail -n 20 "$output_file")"
    exit "$rc"
  fi
}

PREFLIGHT_ARGS=(--require-tools --tlapm "$TLAPM")
if [ "$SUBMIT_SFT_PREFLIGHT" = "1" ]; then
  PREFLIGHT_ARGS+=(--sft-preflight)
fi

export CHATTLA_TLAPM="$TLAPM"
run_stage preflight outputs/logs/tla_prover_remote_preflight.log "$PREFLIGHT" "${PREFLIGHT_ARGS[@]}"

qsub_submit() {
  local select_spec="$1"
  local walltime="$2"
  shift 2
  if [ -n "$PBS_ACCOUNT" ]; then
    set -- -A "$PBS_ACCOUNT" "$@"
  fi
  if [ -n "$PBS_QUEUE" ]; then
    set -- -q "$PBS_QUEUE" "$@"
  fi
  if [ -n "$select_spec" ]; then
    set -- -l "select=$select_spec" "$@"
  fi
  if [ -n "$walltime" ]; then
    set -- -l "walltime=$walltime" "$@"
  fi
  if [ -n "$PBS_FILESYSTEMS" ]; then
    set -- -l "filesystems=$PBS_FILESYSTEMS" "$@"
  fi
  qsub "$@"
}

run_stage known18_qsub outputs/logs/tla_prover_known18_qsub.log qsub_submit "$PBS_SELECT_KNOWN18" "$PBS_WALLTIME_KNOWN18" scripts/qsub_autoprover_known18_corrected_smoke.pbs
KNOWN18_JOB_ID="$(cat outputs/logs/tla_prover_known18_qsub.log)"
if [ "$SUBMIT_SFT_PREFLIGHT" = "1" ]; then
  run_stage sft_preflight_qsub outputs/logs/tla_prover_sft_preflight_qsub.log qsub_submit "$PBS_SELECT_SFT" "$PBS_WALLTIME_SFT" scripts/qsub_sophia_tla_prover_sft_preflight.pbs
  SFT_PREFLIGHT_JOB_ID="$(cat outputs/logs/tla_prover_sft_preflight_qsub.log)"
fi

write_report true submitted 0 ""
