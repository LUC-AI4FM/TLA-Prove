#!/usr/bin/env bash
set -u

REPO="${CHATTLA_REPO:-$HOME/GitHub/ChatTLA/ChatTLA}"
SOPHIA_CTL="${SOPHIA_CTL:-$HOME/.ssh/codex-sophia-ctl}"
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
    echo "[$(ts)] sophia control socket present"
    if [ -f outputs/logs/current_sophia_full_dataset_smoke_job.txt ]; then
      job="$(cat outputs/logs/current_sophia_full_dataset_smoke_job.txt)"
      ssh -o BatchMode=yes -S "$SOPHIA_CTL" \
        eric-spencer@sophia.alcf.anl.gov \
        "cd ChatTLA && (qstat -f '$job' 2>/dev/null | egrep 'job_state|queue|exec_host|resources_used.walltime|Exit_status' || qstat -x -f '$job' 2>/dev/null | egrep 'job_state|Exit_status|resources_used.walltime|comment' || true) && ls -l outputs/autoprover/full_dataset_smoke_${job}* 2>/dev/null || true"
    fi
  else
    echo "[$(ts)] sophia control socket missing"
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
    ds = fetch_json("https://huggingface.co/api/datasets/EricSpencer00/chattla-tla-prover-108-108")
    report["hf_dataset_sha"] = ds.get("sha")
    report["hf_dataset_files"] = sorted(s.get("rfilename") for s in ds.get("siblings", []))
    rows_url = (
        "https://datasets-server.huggingface.co/first-rows?"
        "dataset=EricSpencer00/chattla-tla-prover-108-108&config=default&split=train"
    )
    first = fetch_json(rows_url)
    report["hf_dataset_viewer_rows"] = len(first.get("rows", []))
    report["hf_dataset_viewer_features"] = [f.get("name") for f in first.get("features", [])]
except Exception as exc:
    report["hf_dataset_error"] = repr(exc)

try:
    model = fetch_json("https://huggingface.co/api/models/EricSpencer00/chattla-20b")
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
