#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
SUBMIT_SFT_PREFLIGHT=0
INSTALL_LAUNCHAGENTS=0
SFT_CORPUS="${CHATTLA_TLA_PROVER_CORPUS:-default}"
SCRIPT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --sft-corpus)
      SFT_CORPUS="$2"
      shift
      ;;
    --submit-sft-preflight|--submit-all)
      SUBMIT_SFT_PREFLIGHT=1
      ;;
    --install-launchagents)
      INSTALL_LAUNCHAGENTS=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/sync_macmini_and_submit_known18.sh [--dry-run] [--sft-corpus default|expanded|full-public|shape-ready|shape-ready-not-sany|PATH] [--submit-sft-preflight]

Sync TLA prover handoff artifacts to a configured relay host, sync them
through that host's remote control socket, and submit the corrected known-18
TLAPS smoke.

Options:
  --dry-run                 Print commands without running them.
  --sft-corpus              Choose the default prover corpus, a named public corpus lane, or an explicit JSONL path.
  --submit-sft-preflight    Also submit the bounded 3-step SFT startup preflight.
  --submit-all              Alias for --submit-sft-preflight.
  --install-launchagents    Also install persistent relay LaunchAgents after sync.
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

LOCAL_REPO="${CHATTLA_LOCAL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RELAY_HOST="${CHATTLA_RELAY_HOST:-${CHATTLA_MAC_HOST:-}}"
RELAY_KEY="${CHATTLA_RELAY_KEY:-${CHATTLA_MAC_KEY:-$HOME/.ssh/id_ed25519}}"
RELAY_REPO="${CHATTLA_RELAY_REPO:-${CHATTLA_MAC_REPO:-$HOME/ChatTLA}}"
RELAY_LABEL="${CHATTLA_RELAY_LABEL:-relay}"
SOPHIA_CTL="${SOPHIA_CTL:-$HOME/.ssh/${CHATTLA_SOPHIA_CTL_NAME:-chattla-remote-ctl}}"
REMOTE_HOST="${CHATTLA_REMOTE_HOST:-${SOPHIA_HOST:-}}"
REMOTE_REPO="${CHATTLA_REMOTE_REPO:-ChatTLA}"
REMOTE_TLAPM="${CHATTLA_TLAPM:-tlapm}"
LOCAL_PROVER_TRAIN_FILE="data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl"
LOCAL_PROVER_TRAIN_SUMMARY="data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json"
PUBLIC_PROVER_TRAIN_FILE="outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl"
PUBLIC_PROVER_TRAIN_SUMMARY="outputs/hf_publish/chattla-tla-prover-corpora-v1/metadata/chattla_tla_prover_sft_v1.summary.json"
resolve_requested_train_file() {
  python3 "$SCRIPT_REPO/scripts/tla_prover_corpus_paths.py" --resolve-request "$1"
}

REQUESTED_TRAIN_FILE="${CHATTLA_TLA_PROVER_TRAIN_FILE:-}"
if [ -z "$REQUESTED_TRAIN_FILE" ]; then
  REQUESTED_TRAIN_FILE="$(resolve_requested_train_file "$SFT_CORPUS")"
fi
REMOTE_TRAIN_FILE="${REQUESTED_TRAIN_FILE:-$LOCAL_PROVER_TRAIN_FILE}"

if [ -z "$RELAY_HOST" ]; then
  echo "Set CHATTLA_RELAY_HOST or CHATTLA_MAC_HOST to the relay SSH target." >&2
  exit 2
fi
if [ -z "$REMOTE_HOST" ]; then
  echo "Set CHATTLA_REMOTE_HOST or SOPHIA_HOST to the remote SSH target." >&2
  exit 2
fi

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

FILES=(
  src/
  scripts/autoprover_smoke.py
  scripts/summarize_autoprover_smoke.py
  scripts/qsub_autoprover_known18_corrected_smoke.pbs
  scripts/qsub_sophia_tla_prover_sft_preflight.pbs
  scripts/install_handoff_doctor_launchagent.sh
  scripts/macmini_codex_goal_supervisor.sh
  scripts/macmini_tla_prover_autopilot.sh
  scripts/install_macmini_launchagents.sh
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
  scripts/sync_macmini_and_submit_known18.sh
  scripts/wait_for_macmini_and_handoff_known18.sh
  scripts/watch_tla_prover_remote_results.sh
  data/processed/tla_prover/tlaps_candidate_modules_18.txt
  data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl
  data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json
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

run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

cd "$LOCAL_REPO"
python3 scripts/build_tla_prover_eval_corpus.py >/dev/null
python3 scripts/build_sany_tlc_eval_corpus.py >/dev/null
python3 scripts/diagnose_sany_tlc_pass_corpus.py >/dev/null
python3 scripts/preflight_tla_prover_corpora.py >/dev/null
python3 scripts/build_tla_prover_manifest.py >/dev/null

TRAIN_FILE_TO_SYNC="$LOCAL_PROVER_TRAIN_FILE"
TRAIN_SUMMARY_TO_SYNC="$LOCAL_PROVER_TRAIN_SUMMARY"
if [ -n "$REQUESTED_TRAIN_FILE" ]; then
  TRAIN_FILE_TO_SYNC="$REQUESTED_TRAIN_FILE"
  case "$TRAIN_FILE_TO_SYNC" in
    *.jsonl)
      TRAIN_SUMMARY_TO_SYNC="${TRAIN_FILE_TO_SYNC%.jsonl}.summary.json"
      ;;
    *)
      TRAIN_SUMMARY_TO_SYNC=""
      ;;
  esac
elif [ ! -f "$TRAIN_FILE_TO_SYNC" ] && [ -f "$PUBLIC_PROVER_TRAIN_FILE" ]; then
  TRAIN_FILE_TO_SYNC="$PUBLIC_PROVER_TRAIN_FILE"
  TRAIN_SUMMARY_TO_SYNC="$PUBLIC_PROVER_TRAIN_SUMMARY"
  REMOTE_TRAIN_FILE="$PUBLIC_PROVER_TRAIN_FILE"
fi
if [ ! -f "$TRAIN_FILE_TO_SYNC" ]; then
  echo "Missing prover train file: $TRAIN_FILE_TO_SYNC" >&2
  exit 2
fi

ALL_FILES=("${FILES[@]}")
ALL_FILES+=("$TRAIN_FILE_TO_SYNC")
[ -n "$TRAIN_SUMMARY_TO_SYNC" ] && [ -f "$TRAIN_SUMMARY_TO_SYNC" ] && ALL_FILES+=("$TRAIN_SUMMARY_TO_SYNC")
while IFS= read -r module_path; do
  [ -z "$module_path" ] && continue
  ALL_FILES+=("$module_path")
done < data/processed/tla_prover/tlaps_candidate_modules_18.txt

if [ "$SUBMIT_SFT_PREFLIGHT" = "1" ]; then
  ALL_FILES+=("${SFT_PREFLIGHT_FILES[@]}")
fi

run "${SSH_MAC[@]}" "$RELAY_HOST" "mkdir -p '$RELAY_REPO/__sync_stage__'"
for file in "${ALL_FILES[@]}"; do
  run "${RSYNC_MAC[@]}" --relative "$file" "$RELAY_HOST:$RELAY_REPO/"
done

if [ "$INSTALL_LAUNCHAGENTS" = "1" ]; then
  INSTALL_MACMINI_CMD="CHATTLA_REPO='$RELAY_REPO' scripts/install_macmini_launchagents.sh"
else
  INSTALL_MACMINI_CMD="scripts/install_macmini_launchagents.sh --dry-run"
fi
run "${SSH_MAC[@]}" "$RELAY_HOST" "cd '$RELAY_REPO' && chmod +x scripts/macmini_codex_goal_supervisor.sh scripts/macmini_tla_prover_autopilot.sh scripts/install_macmini_launchagents.sh scripts/install_handoff_doctor_launchagent.sh scripts/sync_macmini_and_submit_known18.sh scripts/wait_for_macmini_and_handoff_known18.sh scripts/watch_tla_prover_remote_results.sh scripts/submit_tla_prover_remote_jobs.sh scripts/preflight_tla_prover_remote.py scripts/preflight_tla_prover_corpora.py scripts/build_tla_prover_eval_corpus.py scripts/build_sany_tlc_eval_corpus.py scripts/diagnose_sany_tlc_pass_corpus.py scripts/collect_tla_prover_remote_results.sh scripts/evaluate_tla_prover_remote_results.py scripts/status_tla_prover_handoff.py scripts/doctor_tla_prover_handoff.py 2>/dev/null || true && $INSTALL_MACMINI_CMD"

run "${SSH_MAC[@]}" "$RELAY_HOST" "ssh -o BatchMode=yes -S '$SOPHIA_CTL' '$REMOTE_HOST' 'cd '$REMOTE_REPO' && mkdir -p scripts data/processed/tla_prover outputs/manifests outputs/logs outputs/autoprover'"
for file in "${ALL_FILES[@]}"; do
  run "${SSH_MAC[@]}" "$RELAY_HOST" "cd '$RELAY_REPO' && rsync -az --relative '$file' -e \"ssh -o BatchMode=yes -S '$SOPHIA_CTL'\" '$REMOTE_HOST:$REMOTE_REPO/'"
done

REMOTE_SUBMIT="cd '$REMOTE_REPO' && CHATTLA_TLAPM='$REMOTE_TLAPM' CHATTLA_TLA_PROVER_TRAIN_FILE='$REMOTE_TRAIN_FILE' scripts/submit_tla_prover_remote_jobs.sh"
if [ "$SUBMIT_SFT_PREFLIGHT" = "1" ]; then
  REMOTE_SUBMIT="$REMOTE_SUBMIT --submit-sft-preflight"
fi
run "${SSH_MAC[@]}" "$RELAY_HOST" "ssh -o BatchMode=yes -S '$SOPHIA_CTL' '$REMOTE_HOST' '$REMOTE_SUBMIT'"
