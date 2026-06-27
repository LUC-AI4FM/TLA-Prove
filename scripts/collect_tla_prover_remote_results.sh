#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
LOCAL_REPO="${CHATTLA_LOCAL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RELAY_HOST="${CHATTLA_RELAY_HOST:-${CHATTLA_MAC_HOST:-ericspencer@erics-mac-mini.local}}"
RELAY_KEY="${CHATTLA_RELAY_KEY:-${CHATTLA_MAC_KEY:-$HOME/.ssh/id_ed25519_mac_mini}}"
RELAY_REPO="${CHATTLA_RELAY_REPO:-${CHATTLA_MAC_REPO:-/Users/ericspencer/GitHub/ChatTLA/ChatTLA}}"
RELAY_LABEL="${CHATTLA_RELAY_LABEL:-Mac mini}"
SOPHIA_CTL="${SOPHIA_CTL:-/Users/ericspencer/.ssh/codex-sophia-ctl}"
SOPHIA_HOST="${SOPHIA_HOST:-eric-spencer@sophia.alcf.anl.gov}"
SUBMISSION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission.json"
COLLECTION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_results_collection.json"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --submission-report)
      SUBMISSION_REPORT="$2"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/collect_tla_prover_remote_results.sh [--dry-run] [--submission-report PATH]

Mirror the targeted evidence for the TLA prover remote handoff through the Mac
mini Sophia control socket: submission report, qstat snapshot, preflight/qsub
logs, known-18 smoke JSONL/summary/logs, and SFT preflight log when applicable.
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

SSH_MAC=(
  ssh
  -o ConnectTimeout=15
  -o BatchMode=yes
  -o PubkeyAuthentication=yes
  -o PasswordAuthentication=no
  -o IdentitiesOnly=yes
  -i "$RELAY_KEY"
)

RSYNC_MAC=(
  rsync -az
  -e "ssh -o ConnectTimeout=15 -o BatchMode=yes -o PubkeyAuthentication=yes -o PasswordAuthentication=no -o IdentitiesOnly=yes -i $RELAY_KEY"
)

run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

jobnum() {
  printf '%s' "$1" | awk -F. '{print $1}'
}

requested_paths() {
  python3 - "$SUBMISSION_REPORT" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
paths = [
    "outputs/manifests/tla_prover_remote_submission.json",
    "outputs/manifests/tla_prover_remote_qstat.txt",
    "outputs/logs/tla_prover_remote_preflight.log",
    "outputs/logs/tla_prover_known18_qsub.log",
    "outputs/logs/tla_prover_sft_preflight_qsub.log",
    "outputs/logs/autoprover_known18_corrected.log",
    "outputs/logs/autoprover_known18_corrected.err",
]
if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
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
for path in dict.fromkeys(paths):
    print(path)
PY
}

write_collection_report() {
  local mirrored_file="$1"
  local missing_file="$2"
  local errors_file="$3"
  python3 - "$COLLECTION_REPORT" "$SUBMISSION_REPORT" "$mirrored_file" "$missing_file" "$errors_file" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
submission_report = Path(sys.argv[2])
mirrored = [line.strip() for line in Path(sys.argv[3]).read_text().splitlines() if line.strip()]
missing = [line.strip() for line in Path(sys.argv[4]).read_text().splitlines() if line.strip()]
errors = [line.strip() for line in Path(sys.argv[5]).read_text().splitlines() if line.strip()]
job_ids = {}
if submission_report.exists():
    try:
        report = json.loads(submission_report.read_text(encoding="utf-8"))
        job_ids = {
            "known18_job_id": report.get("known18_job_id"),
            "sft_preflight_job_id": report.get("sft_preflight_job_id"),
        }
    except json.JSONDecodeError as exc:
        errors.append(f"invalid submission report: {exc}")
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

if [ "$DRY_RUN" = "1" ]; then
  run "${SSH_MAC[@]}" "$RELAY_HOST" "ssh -o BatchMode=yes -S '$SOPHIA_CTL' '$SOPHIA_HOST' 'cd ChatTLA && mkdir -p outputs/manifests && { date -u; qstat -u eric-spencer || qstat -u \"\$USER\" || true; } > outputs/manifests/tla_prover_remote_qstat.txt'"
else
  set +e
  "${SSH_MAC[@]}" "$RELAY_HOST" "ssh -o BatchMode=yes -S '$SOPHIA_CTL' '$SOPHIA_HOST' 'cd ChatTLA && mkdir -p outputs/manifests && { date -u; qstat -u eric-spencer || qstat -u \"\$USER\" || true; } > outputs/manifests/tla_prover_remote_qstat.txt'" >/dev/null 2>&1
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
    run "${SSH_MAC[@]}" "$RELAY_HOST" "cd '$RELAY_REPO' && mkdir -p '$(dirname "$rel_path")' && rsync -az -e \"ssh -o BatchMode=yes -S '$SOPHIA_CTL'\" '$SOPHIA_HOST:ChatTLA/$rel_path' '$RELAY_REPO/$rel_path'"
    run "${RSYNC_MAC[@]}" "$RELAY_HOST:$RELAY_REPO/$rel_path" "$LOCAL_REPO/$rel_path"
    rc=0
  else
    "${SSH_MAC[@]}" "$RELAY_HOST" "cd '$RELAY_REPO' && mkdir -p '$(dirname "$rel_path")' && rsync -az -e \"ssh -o BatchMode=yes -S '$SOPHIA_CTL'\" '$SOPHIA_HOST:ChatTLA/$rel_path' '$RELAY_REPO/$rel_path'" >/dev/null 2>&1
    rc1=$?
    "${RSYNC_MAC[@]}" "$RELAY_HOST:$RELAY_REPO/$rel_path" "$LOCAL_REPO/$rel_path" >/dev/null 2>&1
    rc2=$?
    if [ "$rc1" -eq 0 ] && [ "$rc2" -eq 0 ] && [ -e "$LOCAL_REPO/$rel_path" ]; then
      rc=0
    else
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
