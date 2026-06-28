#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
SUBMIT_SFT_PREFLIGHT=0
SUBMIT_FINAL_PROOF_VERIFY=0
SUBMIT_FULL_DATASET_SMOKE=0
LOCAL_REPO="${CHATTLA_LOCAL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --submit-sft-preflight|--submit-all)
      SUBMIT_SFT_PREFLIGHT=1
      ;;
    --submit-final-proof-verify)
      SUBMIT_FINAL_PROOF_VERIFY=1
      ;;
    --submit-full-dataset-smoke)
      SUBMIT_FULL_DATASET_SMOKE=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/sync_sophia_and_submit_known18.sh [--dry-run] [--submit-sft-preflight] [--submit-final-proof-verify] [--submit-full-dataset-smoke]

Sync TLA prover handoff artifacts directly from this machine to a configured
Sophia checkout, submit the corrected known-18 TLAPS smoke, and mirror the
remote submission report back into the local repo.

Options:
  --dry-run                 Print commands without running them.
  --submit-sft-preflight    Also submit the bounded 3-step SFT startup preflight.
  --submit-final-proof-verify
                            Also submit the published 108/108 proof-artifact verification.
  --submit-full-dataset-smoke
                            Also submit the full-dataset prover smoke rerun.
  --submit-all              Alias for --submit-sft-preflight.
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

REMOTE_HOST="${CHATTLA_REMOTE_HOST:-${SOPHIA_HOST:-}}"
REMOTE_PASSWORD="${CHATTLA_REMOTE_PASSWORD:-${SOPHIA_PASSWORD:-}}"
REMOTE_REPO="${CHATTLA_REMOTE_REPO:-\$HOME/ChatTLA}"
REMOTE_TLAPM="${CHATTLA_TLAPM:-tlapm}"
LOCAL_SUBMISSION_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission.json"
MIRROR_FAILURE_REPORT="$LOCAL_REPO/outputs/manifests/tla_prover_remote_submission_mirror_failed.json"
ASKPASS_SCRIPT=""

if [ -z "$REMOTE_HOST" ]; then
  echo "Set CHATTLA_REMOTE_HOST or SOPHIA_HOST to the remote SSH target." >&2
  exit 2
fi

RSYNC_SSH=(
  ssh
  -o ConnectTimeout=15
  -o PreferredAuthentications=password,keyboard-interactive,hostbased
  -o PubkeyAuthentication=no
)

cleanup() {
  if [ -n "$ASKPASS_SCRIPT" ] && [ -f "$ASKPASS_SCRIPT" ]; then
    rm -f "$ASKPASS_SCRIPT"
  fi
}

trap cleanup EXIT

setup_askpass() {
  if [ -z "$REMOTE_PASSWORD" ] || [ "$DRY_RUN" = "1" ]; then
    return 0
  fi
  ASKPASS_SCRIPT="$(mktemp)"
  chmod 700 "$ASKPASS_SCRIPT"
  cat >"$ASKPASS_SCRIPT" <<EOF
#!/usr/bin/env bash
printf '%s\n' "$REMOTE_PASSWORD"
EOF
}

with_remote_auth() {
  if [ -z "$REMOTE_PASSWORD" ] || [ "$DRY_RUN" = "1" ]; then
    "$@"
  else
    env \
      SSH_ASKPASS="$ASKPASS_SCRIPT" \
      SSH_ASKPASS_REQUIRE=force \
      DISPLAY="${DISPLAY:-chattla-askpass}" \
      "$@"
  fi
}

FILES=(
  src/
  scripts/autoprover_smoke.py
  scripts/collect_tla_prover_direct_results.sh
  scripts/summarize_autoprover_smoke.py
  scripts/qsub_autoprover_known18_corrected_smoke.pbs
  scripts/qsub_autoprover_full_dataset_smoke.pbs
  scripts/qsub_sophia_tla_prover_sft_preflight.pbs
  scripts/build_tla_prover_eval_corpus.py
  scripts/build_sany_tlc_eval_corpus.py
  scripts/build_tla_prover_manifest.py
  scripts/check_tla_prover_pr_ready.py
  scripts/collect_tla_prover_remote_results.sh
  scripts/doctor_tla_prover_handoff.py
  scripts/evaluate_tla_prover_remote_results.py
  scripts/diagnose_sany_tlc_pass_corpus.py
  scripts/preflight_tla_prover_corpora.py
  scripts/preflight_tla_prover_remote.py
  scripts/probe_tla_prover_control_planes.py
  scripts/status_tla_prover_handoff.py
  scripts/submit_tla_prover_remote_jobs.sh
  scripts/sync_sophia_and_submit_known18.sh
  data/processed/tla_prover/tlaps_candidate_modules_18.txt
  data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl
  data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json
  data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl
  data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json
  data/processed/prover_eval.jsonl
  data/processed/prover_eval.summary.json
  data/processed/sany_tlc_pass_sft_v1.jsonl
  data/processed/sany_tlc_pass_sft_v1.summary.json
  data/processed/sany_tlc_pass_eval_v1.jsonl
  data/processed/sany_tlc_pass_eval_v1.summary.json
  outputs/manifests/sany_tlc_pass_corpus_diagnostic.json
  outputs/manifests/tla_prover_corpus_preflight.json
  outputs/manifests/tla_prover_artifacts_v1.json
)

SFT_PREFLIGHT_FILES=(
  configs/
)
FINAL_PROOF_VERIFY_FILES=(
  scripts/verify_published_tlaps_proof_artifact.py
  scripts/qsub_verify_published_tlaps_proof_artifact.pbs
  outputs/hf_publish/chattla-tla-prover-108-108/tlaps_reproduced_final_160816.tar.gz
  outputs/hf_publish/chattla-tla-prover-108-108/metadata/summary.json
  outputs/hf_publish/chattla-tla-prover-108-108/metadata/manifest.json
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

write_mirror_failure_report() {
  mkdir -p "$(dirname "$MIRROR_FAILURE_REPORT")"
  python3 - "$MIRROR_FAILURE_REPORT" "$REMOTE_HOST" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "stage": "mirror_remote_report",
    "exit_code": 76,
    "remote_host": sys.argv[2],
    "next_action": "Retry mirror only; do not resubmit known-18 until this report is cleared.",
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

cd "$LOCAL_REPO"
setup_askpass
python3 scripts/build_tla_prover_eval_corpus.py >/dev/null
python3 scripts/build_sany_tlc_eval_corpus.py >/dev/null
python3 scripts/diagnose_sany_tlc_pass_corpus.py >/dev/null
python3 scripts/preflight_tla_prover_corpora.py >/dev/null
python3 scripts/build_tla_prover_manifest.py >/dev/null

ALL_FILES=("${FILES[@]}")
while IFS= read -r module_path; do
  [ -z "$module_path" ] && continue
  ALL_FILES+=("$module_path")
done < data/processed/tla_prover/tlaps_candidate_modules_18.txt

if [ "$SUBMIT_SFT_PREFLIGHT" = "1" ]; then
  ALL_FILES+=("${SFT_PREFLIGHT_FILES[@]}")
fi
if [ "$SUBMIT_FINAL_PROOF_VERIFY" = "1" ]; then
  ALL_FILES+=("${FINAL_PROOF_VERIFY_FILES[@]}")
fi

run with_remote_auth "${RSYNC_SSH[@]}" "$REMOTE_HOST" "mkdir -p '$REMOTE_REPO'"
run with_remote_auth "${RSYNC_SSH[@]}" "$REMOTE_HOST" "cd '$REMOTE_REPO' && mkdir -p scripts data/processed/tla_prover outputs/manifests outputs/logs outputs/autoprover outputs/hf_publish/chattla-tla-prover-108-108/metadata"
for file in "${ALL_FILES[@]}"; do
  run with_remote_auth rsync -az --relative -e "$(printf '%q ' "${RSYNC_SSH[@]}")" "$file" "$REMOTE_HOST:$REMOTE_REPO/"
done

REMOTE_SUBMIT="cd '$REMOTE_REPO' && CHATTLA_TLAPM='$REMOTE_TLAPM' scripts/submit_tla_prover_remote_jobs.sh"
if [ "$SUBMIT_SFT_PREFLIGHT" = "1" ]; then
  REMOTE_SUBMIT="$REMOTE_SUBMIT --submit-sft-preflight"
fi
if [ "$SUBMIT_FINAL_PROOF_VERIFY" = "1" ]; then
  REMOTE_SUBMIT="$REMOTE_SUBMIT --submit-final-proof-verify"
fi
if [ "$SUBMIT_FULL_DATASET_SMOKE" = "1" ]; then
  REMOTE_SUBMIT="$REMOTE_SUBMIT --submit-full-dataset-smoke"
fi
run with_remote_auth "${RSYNC_SSH[@]}" "$REMOTE_HOST" "$REMOTE_SUBMIT"

LOCAL_REPORT_DIR="$(dirname "$LOCAL_SUBMISSION_REPORT")"
run mkdir -p "$LOCAL_REPORT_DIR"
REMOTE_SUBMISSION_REPORT="$REMOTE_REPO/outputs/manifests/tla_prover_remote_submission.json"
if [ "$DRY_RUN" = "1" ]; then
  run with_remote_auth rsync -az -e "$(printf '%q ' "${RSYNC_SSH[@]}")" "$REMOTE_HOST:$REMOTE_SUBMISSION_REPORT" "$LOCAL_SUBMISSION_REPORT"
else
  if with_remote_auth rsync -az -e "$(printf '%q ' "${RSYNC_SSH[@]}")" "$REMOTE_HOST:$REMOTE_SUBMISSION_REPORT" "$LOCAL_SUBMISSION_REPORT"; then
    rm -f "$MIRROR_FAILURE_REPORT"
  else
    write_mirror_failure_report
    exit 76
  fi
fi
