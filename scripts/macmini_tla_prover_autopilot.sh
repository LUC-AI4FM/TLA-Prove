#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CHATTLA_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SOPHIA_CTL="${SOPHIA_CTL:-$HOME/.ssh/${CHATTLA_SOPHIA_CTL_NAME:-chattla-remote-ctl}}"
REMOTE_HOST="${CHATTLA_REMOTE_HOST:-${SOPHIA_HOST:-}}"
HF_NAMESPACE="${CHATTLA_HF_NAMESPACE:-${CHATTLA_HF_ORG:-${HF_ORG:-${USER:-HF}}}}"
export CHATTLA_HF_NAMESPACE="$HF_NAMESPACE"
export CHATTLA_HF_PROVER_DATASET_NAME="${CHATTLA_HF_PROVER_DATASET_NAME:-chattla-tla-prover-108-108}"
export CHATTLA_BASE_MODEL_NAME="${CHATTLA_BASE_MODEL_NAME:-chattla-20b}"
export CHATTLA_HF_PROVER_DATASET="${CHATTLA_HF_PROVER_DATASET:-$CHATTLA_HF_NAMESPACE/$CHATTLA_HF_PROVER_DATASET_NAME}"
export CHATTLA_BASE_MODEL="${CHATTLA_BASE_MODEL:-$CHATTLA_HF_NAMESPACE/$CHATTLA_BASE_MODEL_NAME}"
cd "$REPO" || exit 1

mkdir -p outputs/logs outputs/autopilot data/processed/tla_prover
LOG="outputs/logs/macmini_tla_prover_autopilot.log"
STATUS="outputs/logs/macmini_tla_prover_autopilot.status.json"
MAX_LOG_BYTES="${CHATTLA_AUTOPILOT_LOG_MAX_BYTES:-10485760}"
exec >>"$LOG" 2>&1

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

rotate_log() {
  [ -f "$LOG" ] || return 0
  bytes="$(wc -c < "$LOG" | tr -d ' ')"
  if [ "${bytes:-0}" -gt "$MAX_LOG_BYTES" ]; then
    mv "$LOG" "$LOG.1"
    : > "$LOG"
  fi
}

write_status() {
  state="$1"
  cat > "$STATUS" <<JSON
{
  "updated_at": "$(ts)",
  "state": "$state",
  "pid": $$,
  "repo": "$REPO",
  "sophia_control_socket": "$SOPHIA_CTL"
}
JSON
}

echo "[$(ts)] macmini autopilot start host=$(hostname) repo=$REPO"
echo "[$(ts)] objective: all-dataset TLA prover -> TLC/SANY/TLAPS passer -> Qwen-style fine-tune seed"

while true; do
  rotate_log
  write_status "heartbeat"
  echo "[$(ts)] heartbeat"
  if [ -S "$SOPHIA_CTL" ]; then
    echo "[$(ts)] remote control socket present"
    if [ -f outputs/logs/current_sophia_full_dataset_smoke_job.txt ]; then
      job="$(cat outputs/logs/current_sophia_full_dataset_smoke_job.txt)"
      if [ -n "$REMOTE_HOST" ]; then
        ssh -o BatchMode=yes -S "$SOPHIA_CTL" \
          "$REMOTE_HOST" \
          "cd ChatTLA && (qstat -f '$job' 2>/dev/null | egrep 'job_state|queue|exec_host|resources_used.walltime|Exit_status' || qstat -x -f '$job' 2>/dev/null | egrep 'job_state|Exit_status|resources_used.walltime|comment' || true) && ls -l outputs/autoprover/full_dataset_smoke_${job}* 2>/dev/null || true"
      else
        echo "[$(ts)] remote control socket present but CHATTLA_REMOTE_HOST/SOPHIA_HOST missing"
      fi
    fi
  else
    echo "[$(ts)] remote control socket missing"
  fi
  python3 - <<'PY'
import json
import os
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

repo = Path(os.environ.get("CHATTLA_REPO", str(Path.home() / "GitHub" / "ChatTLA" / "ChatTLA")))
out = repo / "outputs" / "autopilot"
out.mkdir(parents=True, exist_ok=True)
report = {"generated_at": datetime.now(timezone.utc).isoformat()}


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


try:
    dataset_namespace = os.environ.get("CHATTLA_HF_NAMESPACE", os.environ.get("CHATTLA_HF_ORG", "HF"))
    dataset_name = os.environ.get("CHATTLA_HF_PROVER_DATASET_NAME", "chattla-tla-prover-108-108")
    dataset_id = os.environ.get("CHATTLA_HF_PROVER_DATASET", f"{dataset_namespace}/{dataset_name}")
    ds = fetch_json(f"https://huggingface.co/api/datasets/{dataset_id}")
    report["hf_dataset_sha"] = ds.get("sha")
    report["hf_dataset_files"] = sorted(s.get("rfilename") for s in ds.get("siblings", []))
    rows_url = (
        "https://datasets-server.huggingface.co/first-rows?"
        f"dataset={dataset_id}&config=default&split=train"
    )
    first = fetch_json(rows_url)
    report["hf_dataset_viewer_rows"] = len(first.get("rows", []))
    report["hf_dataset_viewer_features"] = [f.get("name") for f in first.get("features", [])]
except Exception as exc:
    report["hf_dataset_error"] = repr(exc)

try:
    base_model_name = os.environ.get("CHATTLA_BASE_MODEL_NAME", "chattla-20b")
    model_id = os.environ.get("CHATTLA_BASE_MODEL", f"{dataset_namespace}/{base_model_name}")
    model = fetch_json(f"https://huggingface.co/api/models/{model_id}")
    report["base_model_id"] = model.get("id")
    report["base_model_sha"] = model.get("sha")
    report["base_model_tags"] = model.get("tags", [])[:20]
    report["base_model_files"] = sorted(s.get("rfilename") for s in model.get("siblings", []))[:80]
except Exception as exc:
    report["base_model_error"] = repr(exc)

artifact = (
    repo
    / "outputs"
    / "hf_publish"
    / "chattla-tla-prover-108-108"
    / "tlaps_reproduced_final_160816.tar.gz"
)
sft = repo / "data" / "processed" / "tla_prover" / "verified_tlaps_sft_seed.jsonl"
if artifact.exists():
    rows = []
    with tarfile.open(artifact, "r:gz") as archive:
        proof_members = [
            member
            for member in archive.getmembers()
            if member.isfile()
            and "/proofs/" in member.name
            and member.name.endswith(".tla")
            and "/.tlacache/" not in member.name
        ]
        for member in sorted(proof_members, key=lambda item: item.name):
            module = Path(member.name).stem
            handle = archive.extractfile(member)
            if handle is None:
                continue
            proof_text = handle.read().decode("utf-8", errors="replace")
            rows.append(
                {
                    "module": module,
                    "source_artifact": "tlaps_reproduced_final_160816.tar.gz",
                    "verifier": "TLAPS 1.5.0 --threads 1",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are ChatTLA, a TLA+ proof assistant. "
                                "Produce TLAPS-checkable TLA+ modules and proofs only."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Produce the complete TLAPS-checked proof module for {module}.",
                        },
                        {"role": "assistant", "content": proof_text},
                    ],
                    "completion": proof_text,
                }
            )
    sft.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
    report["sft_seed_path"] = str(sft)
    report["sft_seed_rows"] = len(rows)
    report["sft_seed_chars"] = sum(len(row["completion"]) for row in rows)
else:
    report["artifact_missing"] = str(artifact)

report_path = out / "macmini_tla_prover_report.json"
report_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
PY
  sleep "${CHATTLA_MACMINI_AUTOPILOT_SLEEP:-900}"
done
