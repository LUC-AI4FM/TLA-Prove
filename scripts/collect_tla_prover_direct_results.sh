#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
EXPLICIT_SUBMISSION_REPORT=0
LOCAL_REPO="${CHATTLA_LOCAL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REMOTE_HOST="${CHATTLA_REMOTE_HOST:-${SOPHIA_HOST:-}}"
REMOTE_PASSWORD="${CHATTLA_REMOTE_PASSWORD:-${SOPHIA_PASSWORD:-}}"
REMOTE_SINGLE_SESSION="${CHATTLA_REMOTE_SINGLE_SESSION:-0}"
REMOTE_REPO="${CHATTLA_REMOTE_REPO:-\$HOME/ChatTLA}"
SUBMISSION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission.json"
FULL_SMOKE_SUBMISSION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission_full_smoke.json"
COLLECTION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_results_collection.json"
ASKPASS_SCRIPT=""
CONTROL_SOCKET=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --submission-report)
      SUBMISSION_REPORT="$2"
      EXPLICIT_SUBMISSION_REPORT=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/collect_tla_prover_direct_results.sh [--dry-run] [--submission-report PATH]

Mirror the targeted evidence for the TLA prover direct Sophia handoff:
submission report, qstat snapshot, preflight/qsub logs, known-18 smoke
JSONL/summary/logs, and the SFT preflight log when applicable.
Missing job result files are recorded but not fatal while jobs may be queued.
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

if [ "$EXPLICIT_SUBMISSION_REPORT" = "1" ]; then
  FULL_SMOKE_SUBMISSION_REPORT="$SUBMISSION_REPORT"
fi

if [ -z "$REMOTE_HOST" ]; then
  echo "Set CHATTLA_REMOTE_HOST or SOPHIA_HOST to the remote SSH target." >&2
  exit 2
fi

SSH_REMOTE=(
  ssh
  -o ConnectTimeout=15
  -o PreferredAuthentications=password,keyboard-interactive,hostbased
  -o PubkeyAuthentication=no
)

cleanup() {
  if [ -n "$CONTROL_SOCKET" ]; then
    ssh -S "$CONTROL_SOCKET" -O exit "$REMOTE_HOST" >/dev/null 2>&1 || true
    rm -f "$CONTROL_SOCKET"
  fi
  if [ -n "$ASKPASS_SCRIPT" ] && [ -f "$ASKPASS_SCRIPT" ]; then
    rm -f "$ASKPASS_SCRIPT"
  fi
}

trap cleanup EXIT

setup_askpass() {
  if [ -z "$REMOTE_PASSWORD" ] || [ "$DRY_RUN" = "1" ] || [ "$REMOTE_SINGLE_SESSION" = "1" ]; then
    return 0
  fi
  ASKPASS_SCRIPT="$(mktemp)"
  chmod 700 "$ASKPASS_SCRIPT"
  cat >"$ASKPASS_SCRIPT" <<EOF
#!/usr/bin/env bash
printf '%s\n' "$REMOTE_PASSWORD"
EOF
}

setup_single_session() {
  if [ "$REMOTE_SINGLE_SESSION" != "1" ] || [ -z "$REMOTE_PASSWORD" ] || [ "$DRY_RUN" = "1" ]; then
    return 0
  fi
  if ! command -v expect >/dev/null 2>&1; then
    echo "expect is required when CHATTLA_REMOTE_SINGLE_SESSION=1" >&2
    exit 2
  fi
  CONTROL_SOCKET="$(mktemp -u "${TMPDIR:-/tmp}/chattla-ssh-XXXXXX")"
  expect <<EOF
log_user 0
set timeout 60
spawn ssh -M -S "$CONTROL_SOCKET" -o ControlMaster=yes -o ControlPersist=600 -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password,keyboard-interactive,hostbased -o PubkeyAuthentication=no -fnNT "$REMOTE_HOST"
expect {
  -re "(?i)yes/no" { send "yes\r"; exp_continue }
  -re "(?i)(password|passcode|verification code|otp).*:" { send "$REMOTE_PASSWORD\r"; exp_continue }
  eof
}
catch wait result
set rc [lindex \$result 3]
exit \$rc
EOF
  SSH_REMOTE+=(-o "ControlPath=$CONTROL_SOCKET" -o ControlMaster=no)
}

with_remote_auth() {
  if [ "$REMOTE_SINGLE_SESSION" = "1" ] || [ -z "$REMOTE_PASSWORD" ] || [ "$DRY_RUN" = "1" ]; then
    "$@"
  else
    env \
      SSH_ASKPASS="$ASKPASS_SCRIPT" \
      SSH_ASKPASS_REQUIRE=force \
      DISPLAY="${DISPLAY:-chattla-askpass}" \
      "$@"
  fi
}

run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

setup_askpass
setup_single_session

requested_paths() {
  python3 - "$SUBMISSION_REPORT" "$FULL_SMOKE_SUBMISSION_REPORT" <<'PY'
import json
import sys
from pathlib import Path

primary_report_path = Path(sys.argv[1])
supplement_path = Path(sys.argv[2])


def load_report(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


report = load_report(primary_report_path)
supplement = load_report(supplement_path)
full_smoke_override_keys = {
    "full_dataset_smoke_job_id",
    "full_dataset_smoke_pbs",
    "full_dataset_smoke_qsub_log",
}
for key, value in supplement.items():
    if key in full_smoke_override_keys and value not in (None, ""):
        report[key] = value
    elif key not in report or report[key] in (None, ""):
        report[key] = value

paths = [
    "outputs/manifests/tla_prover_remote_submission.json",
    "outputs/manifests/tla_prover_remote_submission_full_smoke.json",
    "outputs/manifests/tla_prover_remote_qstat.txt",
    "outputs/logs/tla_prover_remote_preflight.log",
    "outputs/logs/tla_prover_known18_qsub.log",
    "outputs/logs/tla_prover_sft_preflight_qsub.log",
    "outputs/logs/tla_prover_final_proof_verify_qsub.log",
    "outputs/logs/autoprover_known18_corrected.log",
    "outputs/logs/autoprover_known18_corrected.err",
    "outputs/logs/autoprover_full_dataset_smoke.log",
]
if report:
    known18 = report.get("known18_job_id")
    if known18:
        job = known18.split(".", 1)[0]
        # Keep these literals for static tests and operator search:
        # known18_corrected_smoke_* and known18_corrected_smoke_${KNOWN18_JOBNUM}
        paths.extend(
            [
                f"outputs/autoprover/known18_corrected_smoke_{job}.jsonl",
                f"outputs/autoprover/known18_corrected_smoke_{job}.summary.json",
            ]
        )
    sft = report.get("sft_preflight_job_id")
    if sft:
        # Operator-search literal: sft_preflight_*.log
        paths.append(f"outputs/logs/sft_preflight_{sft.split('.', 1)[0]}.log")
    final_verify = report.get("final_proof_verify_job_id")
    if final_verify:
        job = final_verify.split(".", 1)[0]
        paths.extend(
            [
                f"outputs/logs/tlaps_verify_published_{final_verify}.log",
                f"outputs/autoprover/tlaps_verify_published_{job}/summary.json",
                f"outputs/autoprover/tlaps_verify_published_{job}/manifest.json",
            ]
        )
    full_smoke = report.get("full_dataset_smoke_job_id")
    if full_smoke:
        job = full_smoke.split(".", 1)[0]
        paths.extend(
            [
                "outputs/manifests/tla_prover_full_dataset_progress.json",
                f"outputs/autoprover/full_dataset_smoke_{job}.jsonl",
                f"outputs/autoprover/full_dataset_smoke_{job}.summary.json",
                f"outputs/logs/autoprover_full_dataset_smoke_{full_smoke}.log",
            ]
        )
for path in dict.fromkeys(paths):
    print(path)
PY
}

write_collection_report() {
  local mirrored_file="$1"
  local missing_file="$2"
  local errors_file="$3"
  python3 - "$COLLECTION_REPORT" "$SUBMISSION_REPORT" "$FULL_SMOKE_SUBMISSION_REPORT" "$mirrored_file" "$missing_file" "$errors_file" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
submission_report = Path(sys.argv[2])
supplement_report = Path(sys.argv[3])
mirrored = [line.strip() for line in Path(sys.argv[4]).read_text().splitlines() if line.strip()]
missing = [line.strip() for line in Path(sys.argv[5]).read_text().splitlines() if line.strip()]
errors = [line.strip() for line in Path(sys.argv[6]).read_text().splitlines() if line.strip()]
job_ids = {}
report = {}
full_smoke_override_keys = {
    "full_dataset_smoke_job_id",
    "full_dataset_smoke_pbs",
    "full_dataset_smoke_qsub_log",
}
for path in (submission_report, supplement_report):
    if not path.exists():
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid submission report: {exc}")
        continue
    for key, value in payload.items():
        if key in full_smoke_override_keys and value not in (None, ""):
            report[key] = value
        elif key not in report or report[key] in (None, ""):
            report[key] = value
if report:
    job_ids = {
        "known18_job_id": report.get("known18_job_id"),
        "sft_preflight_job_id": report.get("sft_preflight_job_id"),
        "final_proof_verify_job_id": report.get("final_proof_verify_job_id"),
        "full_dataset_smoke_job_id": report.get("full_dataset_smoke_job_id"),
    }
payload = {
    "ok": not errors,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "submission_report": str(submission_report),
    "collection_report": str(out),
    "job_ids": job_ids,
    "mirrored": mirrored,
    "missing": missing,
    "errors": errors,
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

cd "$LOCAL_REPO"
mkdir -p outputs/manifests outputs/logs outputs/autoprover

MIRRORED="$(mktemp)"
MISSING="$(mktemp)"
ERRORS="$(mktemp)"
trap 'rm -f "$MIRRORED" "$MISSING" "$ERRORS"' EXIT

REMOTE_QSTAT_CMD="cd '$REMOTE_REPO' && mkdir -p outputs/manifests && { date -u; qstat -u \"\$USER\" || qstat || true; } > outputs/manifests/tla_prover_remote_qstat.txt"
if [ "$DRY_RUN" = "1" ]; then
  run with_remote_auth "${SSH_REMOTE[@]}" "$REMOTE_HOST" "$REMOTE_QSTAT_CMD"
else
  set +e
  with_remote_auth "${SSH_REMOTE[@]}" "$REMOTE_HOST" "$REMOTE_QSTAT_CMD" >/dev/null 2>&1
  qstat_rc=$?
  set -e
  if [ "$qstat_rc" -ne 0 ]; then
    echo "qstat snapshot failed rc=$qstat_rc" >> "$ERRORS"
  fi
fi

while IFS= read -r rel_path; do
  [ -z "$rel_path" ] && continue
  mkdir -p "$(dirname "$LOCAL_REPO/$rel_path")"
  set +e
  if [ "$DRY_RUN" = "1" ]; then
    run with_remote_auth rsync -az -e "$(printf '%q ' "${SSH_REMOTE[@]}")" "$REMOTE_HOST:$REMOTE_REPO/$rel_path" "$LOCAL_REPO/$rel_path"
    rc=0
  else
    with_remote_auth rsync -az -e "$(printf '%q ' "${SSH_REMOTE[@]}")" "$REMOTE_HOST:$REMOTE_REPO/$rel_path" "$LOCAL_REPO/$rel_path" >/dev/null 2>&1
    rc=$?
    if [ "$rc" -eq 0 ] && [ ! -e "$LOCAL_REPO/$rel_path" ]; then
      rc=1
    fi
  fi
  set -e
  if [ "$rc" -eq 0 ]; then
    echo "$rel_path" >> "$MIRRORED"
  else
    echo "$rel_path" >> "$MISSING"
  fi
done < <(requested_paths)

if [ "$DRY_RUN" = "1" ]; then
  printf '+ write collection report %q\n' "$COLLECTION_REPORT"
else
  write_collection_report "$MIRRORED" "$MISSING" "$ERRORS"
  if [ -s "$ERRORS" ]; then
    exit 1
  fi
fi
