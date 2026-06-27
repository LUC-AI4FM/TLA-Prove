import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "watch_tla_prover_remote_results.sh"


def test_watch_results_script_has_expected_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--max-attempts" in text
    assert "--sleep-seconds" in text
    assert "collect_tla_prover_remote_results.sh" in text
    assert "tla_prover_remote_submission.json" in text
    assert "tla_prover_remote_results_collection.json" in text
    assert "tla_prover_remote_watch.json" in text
    assert "evaluate_tla_prover_remote_results.py" in text
    assert "tla_prover_remote_decision.json" in text
    assert "known18_corrected_smoke_${KNOWN18_JOBNUM}.summary.json" in text
    assert "sft_preflight_${SFT_JOBNUM}.log" in text
    assert "exit 75" in text


def test_watch_results_waits_for_submission_report_then_completes(tmp_path: Path) -> None:
    submission = tmp_path / "outputs/manifests/tla_prover_remote_submission.json"
    collection = tmp_path / "outputs/manifests/tla_prover_remote_results_collection.json"
    collector_count = tmp_path / "collector_count"
    fake_collector = tmp_path / "collector.sh"
    fake_collector.write_text(
        f"""#!/usr/bin/env bash
count=$(cat {collector_count} 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > {collector_count}
mkdir -p {collection.parent}
mkdir -p {tmp_path}/outputs/autoprover
cat > {tmp_path}/outputs/autoprover/known18_corrected_smoke_170001.summary.json <<'JSON'
{{
  "rows": 18,
  "statuses": {{"tlaps_proved": 18}},
  "tlaps_checked": 18,
  "tlaps_total_obligations": 180,
  "tlaps_proved_obligations": 180,
  "tlaps_failed_obligations": 0
}}
JSON
cat > {collection} <<'JSON'
{{
  "ok": true,
  "job_ids": {{
    "known18_job_id": "170001.sophia-pbs-01",
    "sft_preflight_job_id": "170002.sophia-pbs-01"
  }},
  "mirrored": [
    "outputs/autoprover/known18_corrected_smoke_170001.summary.json",
    "outputs/logs/sft_preflight_170002.log"
  ],
  "missing": [],
  "errors": []
}}
JSON
""",
        encoding="utf-8",
    )
    fake_collector.chmod(0o755)
    submission.parent.mkdir(parents=True)
    submission.write_text(
        json.dumps(
            {
                "ok": True,
                "known18_job_id": "170001.sophia-pbs-01",
                "sft_preflight_job_id": "170002.sophia-pbs-01",
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["CHATTLA_LOCAL_REPO"] = str(tmp_path)
    env["CHATTLA_RESULTS_COLLECTOR"] = str(fake_collector)

    subprocess.run(
        ["bash", str(SCRIPT), "--max-attempts", "2", "--sleep-seconds", "0"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    watch = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_watch.json").read_text())
    assert watch["status"] == "complete"
    assert watch["attempts"] == 1
    assert collector_count.read_text(encoding="utf-8").strip() == "1"
    decision = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_decision.json").read_text())
    assert decision["verdict"] == "advance"


def test_watch_results_times_out_without_submission_report(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CHATTLA_LOCAL_REPO"] = str(tmp_path)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--max-attempts", "2", "--sleep-seconds", "0"],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 75
    watch = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_watch.json").read_text())
    assert watch["status"] == "timeout"
    assert watch["attempts"] == 2


def test_watch_results_completes_when_collector_rc_nonzero_but_evidence_ready(tmp_path: Path) -> None:
    submission = tmp_path / "outputs/manifests/tla_prover_remote_submission.json"
    collection = tmp_path / "outputs/manifests/tla_prover_remote_results_collection.json"
    fake_collector = tmp_path / "collector.sh"
    fake_collector.write_text(
        f"""#!/usr/bin/env bash
mkdir -p {collection.parent} {tmp_path}/outputs/autoprover
cat > {tmp_path}/outputs/autoprover/known18_corrected_smoke_170001.summary.json <<'JSON'
{{
  "rows": 18,
  "statuses": {{"tlaps_proved": 18}},
  "tlaps_checked": 18
}}
JSON
cat > {collection} <<'JSON'
{{
  "ok": false,
  "mirrored": ["outputs/autoprover/known18_corrected_smoke_170001.summary.json"],
  "missing": [],
  "errors": ["qstat snapshot failed rc=255"]
}}
JSON
exit 1
""",
        encoding="utf-8",
    )
    fake_collector.chmod(0o755)
    submission.parent.mkdir(parents=True)
    submission.write_text(
        json.dumps({"ok": True, "known18_job_id": "170001.sophia-pbs-01", "sft_preflight_job_id": None}),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["CHATTLA_LOCAL_REPO"] = str(tmp_path)
    env["CHATTLA_RESULTS_COLLECTOR"] = str(fake_collector)

    subprocess.run(
        ["bash", str(SCRIPT), "--max-attempts", "2", "--sleep-seconds", "0"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    watch = json.loads((tmp_path / "outputs/manifests/tla_prover_remote_watch.json").read_text())
    assert watch["status"] == "complete"
