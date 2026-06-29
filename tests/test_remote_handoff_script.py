from pathlib import Path
import json
import os
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_macmini_and_submit_known18.sh"
DIRECT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_sophia_and_submit_known18.sh"
WAIT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wait_for_macmini_and_handoff_known18.sh"
REPO = SCRIPT.parents[1]


def test_remote_handoff_script_mentions_required_artifacts_and_dry_run() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "--dry-run" in text
    assert "--submit-sft-preflight" in text
    assert "tlaps_candidate_modules_18.txt" in text
    assert "qsub_autoprover_known18_corrected_smoke.pbs" in text
    assert "qsub_sophia_tla_prover_sft_preflight.pbs" in text
    assert "install_macmini_launchagents.sh" in text
    assert "install_handoff_doctor_launchagent.sh" in text
    assert "tla_prover_artifacts_v1.json" in text
    assert "tla_prover_corpus_preflight.json" in text
    assert "build_tla_prover_eval_corpus.py" in text
    assert "build_sany_tlc_eval_corpus.py" in text
    assert "preflight_tla_prover_corpora.py" in text
    assert "diagnose_sany_tlc_pass_corpus.py" in text
    assert "preflight_tla_prover_remote.py" in text
    assert "evaluate_tla_prover_remote_results.py" in text
    assert "sany_tlc_pass_corpus_diagnostic.json" in text
    assert "probe_tla_prover_control_planes.py" in text
    assert "submit_tla_prover_remote_jobs.sh" in text
    assert "data/processed/prover_eval.jsonl" in text
    assert "data/processed/sany_tlc_pass_eval_v1.jsonl" in text
    assert "--relative" in text
    assert "ALL_FILES" in text
    assert "REMOTE_SUBMIT" in text
    assert "rsync" in text
    assert "chattla-remote-ctl" in text
    assert "--install-launchagents" in text


def test_direct_sophia_handoff_script_mentions_required_artifacts_and_dry_run() -> None:
    text = DIRECT_SCRIPT.read_text(encoding="utf-8")

    assert "--dry-run" in text
    assert "--submit-sft-preflight" in text
    assert "--submit-final-proof-verify" in text
    assert "--submit-full-dataset-smoke" in text
    assert "tlaps_candidate_modules_18.txt" in text
    assert "qsub_autoprover_known18_corrected_smoke.pbs" in text
    assert "qsub_sophia_tla_prover_sft_preflight.pbs" in text
    assert "qsub_verify_published_tlaps_proof_artifact.pbs" in text
    assert "qsub_autoprover_full_dataset_smoke.pbs" in text
    assert "verify_published_tlaps_proof_artifact.py" in text
    assert "tlaps_reproduced_final_160816.tar.gz" in text
    assert "outputs/hf_publish/chattla-tla-prover-108-108/metadata/summary.json" in text
    assert "outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl" in text
    assert "tla_prover_artifacts_v1.json" in text
    assert "tla_prover_corpus_preflight.json" in text
    assert "build_tla_prover_eval_corpus.py" in text
    assert "build_sany_tlc_eval_corpus.py" in text
    assert "preflight_tla_prover_corpora.py" in text
    assert "diagnose_sany_tlc_pass_corpus.py" in text
    assert "submit_tla_prover_remote_jobs.sh" in text
    assert "collect_tla_prover_direct_results.sh" in text
    assert "data/processed/prover_eval.jsonl" in text
    assert "data/processed/sany_tlc_pass_eval_v1.jsonl" in text
    assert "CHATTLA_REMOTE_HOST" in text
    assert "CHATTLA_REMOTE_PASSWORD" in text
    assert "SOPHIA_PASSWORD" in text
    assert "SSH_ASKPASS_REQUIRE=force" in text
    assert "CHATTLA_REMOTE_SINGLE_SESSION" in text
    assert "ControlMaster" in text
    assert "expect" in text
    assert "--relative" in text
    assert "ALL_FILES" in text
    assert "tla_prover_remote_submission.json" in text
    assert "tla_prover_remote_submission_mirror_failed.json" in text


def test_direct_sophia_handoff_dry_run_syncs_known18_modules_and_sft_dependencies() -> None:
    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_REMOTE_HOST": "user@remote.example",
            "CHATTLA_REMOTE_REPO": "~/ChatTLA",
            "CHATTLA_TLAPM": "/opt/tlaps/bin/tlapm",
        }
    )
    result = subprocess.run(
        [str(DIRECT_SCRIPT), "--dry-run", "--submit-sft-preflight"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    module_paths = [
        line.strip()
        for line in (REPO / "data/processed/tla_prover/tlaps_candidate_modules_18.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert module_paths
    for module_path in module_paths:
        assert module_path in result.stdout

    normalized = result.stdout.replace("\\ ", " ")
    assert "src/" in normalized
    assert "configs/" in normalized
    assert "data/processed/prover_eval.jsonl" in normalized
    assert "data/processed/sany_tlc_pass_eval_v1.jsonl" in normalized
    assert "scripts/submit_tla_prover_remote_jobs.sh --submit-sft-preflight" in normalized
    assert "CHATTLA_TLA_PROVER_TRAIN_FILE" in normalized
    assert "outputs/manifests/tla_prover_remote_submission.json" in normalized
    assert "user@remote.example" in normalized


def test_direct_sophia_handoff_dry_run_syncs_final_verify_artifacts() -> None:
    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_REMOTE_HOST": "user@remote.example",
            "CHATTLA_REMOTE_REPO": "~/ChatTLA",
            "CHATTLA_TLAPM": "/opt/tlaps/bin/tlapm",
        }
    )
    result = subprocess.run(
        [str(DIRECT_SCRIPT), "--dry-run", "--submit-final-proof-verify"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    normalized = result.stdout.replace("\\ ", " ")
    assert "scripts/verify_published_tlaps_proof_artifact.py" in normalized
    assert "scripts/qsub_verify_published_tlaps_proof_artifact.pbs" in normalized
    assert "outputs/hf_publish/chattla-tla-prover-108-108/tlaps_reproduced_final_160816.tar.gz" in normalized
    assert "outputs/hf_publish/chattla-tla-prover-108-108/metadata/summary.json" in normalized
    assert "scripts/submit_tla_prover_remote_jobs.sh --submit-final-proof-verify" in normalized


def test_direct_sophia_handoff_dry_run_syncs_full_smoke_artifacts() -> None:
    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_REMOTE_HOST": "user@remote.example",
            "CHATTLA_REMOTE_REPO": "~/ChatTLA",
            "CHATTLA_TLAPM": "/opt/tlaps/bin/tlapm",
        }
    )
    result = subprocess.run(
        [str(DIRECT_SCRIPT), "--dry-run", "--submit-full-dataset-smoke"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    normalized = result.stdout.replace("\\ ", " ")
    assert "scripts/qsub_autoprover_full_dataset_smoke.pbs" in normalized
    assert "scripts/submit_tla_prover_remote_jobs.sh --submit-full-dataset-smoke" in normalized


def test_direct_sophia_handoff_writes_mirror_failed_sentinel_on_report_copy_error(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state = tmp_path / "rsync_count"
    ssh = fake_bin / "ssh"
    ssh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    ssh.chmod(0o755)
    rsync = fake_bin / "rsync"
    rsync.write_text(
        """#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in
    *outputs/manifests/tla_prover_remote_submission.json)
      exit 23
      ;;
  esac
done
exit 0
""",
        encoding="utf-8",
    )
    rsync.chmod(0o755)

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for rel in [
        "scripts/build_tla_prover_eval_corpus.py",
        "scripts/build_sany_tlc_eval_corpus.py",
        "scripts/diagnose_sany_tlc_pass_corpus.py",
        "scripts/preflight_tla_prover_corpora.py",
        "scripts/build_tla_prover_manifest.py",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        path.chmod(0o755)
    (repo / "src").mkdir()
    (repo / "configs").mkdir()
    (repo / "outputs/manifests").mkdir(parents=True)
    (repo / "data/processed/tla_prover").mkdir(parents=True)
    (repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt").write_text(
        "outputs/diamond_gen/example/AtomicRegister.tla\n",
        encoding="utf-8",
    )
    (repo / "outputs/diamond_gen/example").mkdir(parents=True)
    (repo / "outputs/diamond_gen/example/AtomicRegister.tla").write_text("---- MODULE AtomicRegister ----\n====\n", encoding="utf-8")
    for rel in [
        "scripts/autoprover_smoke.py",
        "scripts/collect_tla_prover_direct_results.sh",
        "scripts/summarize_autoprover_smoke.py",
        "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "scripts/check_tla_prover_pr_ready.py",
        "scripts/collect_tla_prover_remote_results.sh",
        "scripts/doctor_tla_prover_handoff.py",
        "scripts/evaluate_tla_prover_remote_results.py",
        "scripts/preflight_tla_prover_remote.py",
        "scripts/probe_tla_prover_control_planes.py",
        "scripts/status_tla_prover_handoff.py",
        "scripts/submit_tla_prover_remote_jobs.sh",
        "scripts/sync_sophia_and_submit_known18.sh",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "data/processed/prover_eval.jsonl",
        "data/processed/prover_eval.summary.json",
        "data/processed/sany_tlc_pass_sft_v1.jsonl",
        "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "data/processed/sany_tlc_pass_eval_v1.jsonl",
        "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "outputs/manifests/tla_prover_corpus_preflight.json",
        "outputs/manifests/tla_prover_artifacts_v1.json",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("x\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(repo),
            "CHATTLA_REMOTE_HOST": "user@remote.example",
            "CHATTLA_REMOTE_REPO": "~/ChatTLA",
        }
    )

    result = subprocess.run(
        ["bash", str(DIRECT_SCRIPT)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 76
    report = json.loads((repo / "outputs/manifests/tla_prover_remote_submission_mirror_failed.json").read_text())
    assert report["stage"] == "mirror_remote_report"
    assert report["exit_code"] == 76
    assert report["remote_host"] == "user@remote.example"


def test_direct_sophia_handoff_writes_local_failure_report_on_transport_error(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    ssh = fake_bin / "ssh"
    ssh.write_text("#!/usr/bin/env bash\necho 'transport failed' >&2\nexit 255\n", encoding="utf-8")
    ssh.chmod(0o755)
    rsync = fake_bin / "rsync"
    rsync.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    rsync.chmod(0o755)

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for rel in [
        "scripts/build_tla_prover_eval_corpus.py",
        "scripts/build_sany_tlc_eval_corpus.py",
        "scripts/diagnose_sany_tlc_pass_corpus.py",
        "scripts/preflight_tla_prover_corpora.py",
        "scripts/build_tla_prover_manifest.py",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        path.chmod(0o755)
    (repo / "src").mkdir()
    (repo / "outputs/manifests").mkdir(parents=True)
    (repo / "data/processed/tla_prover").mkdir(parents=True)
    (repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt").write_text(
        "outputs/diamond_gen/example/AtomicRegister.tla\n",
        encoding="utf-8",
    )
    (repo / "outputs/diamond_gen/example").mkdir(parents=True)
    (repo / "outputs/diamond_gen/example/AtomicRegister.tla").write_text("---- MODULE AtomicRegister ----\n====\n", encoding="utf-8")
    for rel in [
        "scripts/autoprover_smoke.py",
        "scripts/collect_tla_prover_direct_results.sh",
        "scripts/summarize_autoprover_smoke.py",
        "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
        "scripts/qsub_autoprover_full_dataset_smoke.pbs",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "scripts/check_tla_prover_pr_ready.py",
        "scripts/collect_tla_prover_remote_results.sh",
        "scripts/doctor_tla_prover_handoff.py",
        "scripts/evaluate_tla_prover_remote_results.py",
        "scripts/preflight_tla_prover_remote.py",
        "scripts/probe_tla_prover_control_planes.py",
        "scripts/status_tla_prover_handoff.py",
        "scripts/submit_tla_prover_remote_jobs.sh",
        "scripts/sync_sophia_and_submit_known18.sh",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "data/processed/prover_eval.jsonl",
        "data/processed/prover_eval.summary.json",
        "data/processed/sany_tlc_pass_sft_v1.jsonl",
        "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "data/processed/sany_tlc_pass_eval_v1.jsonl",
        "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "outputs/manifests/tla_prover_corpus_preflight.json",
        "outputs/manifests/tla_prover_artifacts_v1.json",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("x\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(repo),
            "CHATTLA_REMOTE_HOST": "user@remote.example",
        }
    )

    result = subprocess.run(
        ["bash", str(DIRECT_SCRIPT)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 255
    report = json.loads((repo / "outputs/manifests/tla_prover_remote_submission.json").read_text())
    assert report["ok"] is False
    assert report["stage"] == "connect_remote_repo"
    assert report["exit_code"] == 255
    assert "transport failed" in report["error"]
    assert report["remote_host"] == "user@remote.example"


def test_direct_sophia_handoff_single_session_uses_expect_when_enabled(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "ssh").write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
    (fake_bin / "rsync").write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
    (fake_bin / "expect").write_text(
        "#!/usr/bin/env bash\n"
        "printf 'called\\n' >> \"$EXPECT_LOG\"\n"
        "cat >/dev/null\n"
        "exit 0\n",
        encoding="utf-8",
    )
    for name in ["ssh", "rsync", "expect"]:
        (fake_bin / name).chmod(0o755)

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for rel in [
        "scripts/build_tla_prover_eval_corpus.py",
        "scripts/build_sany_tlc_eval_corpus.py",
        "scripts/diagnose_sany_tlc_pass_corpus.py",
        "scripts/preflight_tla_prover_corpora.py",
        "scripts/build_tla_prover_manifest.py",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        path.chmod(0o755)
    (repo / "src").mkdir()
    (repo / "outputs/manifests").mkdir(parents=True)
    (repo / "data/processed/tla_prover").mkdir(parents=True)
    (repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt").write_text(
        "outputs/diamond_gen/example/AtomicRegister.tla\n",
        encoding="utf-8",
    )
    (repo / "outputs/diamond_gen/example").mkdir(parents=True)
    (repo / "outputs/diamond_gen/example/AtomicRegister.tla").write_text("---- MODULE AtomicRegister ----\n====\n", encoding="utf-8")
    for rel in [
        "scripts/autoprover_smoke.py",
        "scripts/collect_tla_prover_direct_results.sh",
        "scripts/summarize_autoprover_smoke.py",
        "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
        "scripts/qsub_autoprover_full_dataset_smoke.pbs",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "scripts/check_tla_prover_pr_ready.py",
        "scripts/collect_tla_prover_remote_results.sh",
        "scripts/doctor_tla_prover_handoff.py",
        "scripts/evaluate_tla_prover_remote_results.py",
        "scripts/preflight_tla_prover_remote.py",
        "scripts/probe_tla_prover_control_planes.py",
        "scripts/status_tla_prover_handoff.py",
        "scripts/submit_tla_prover_remote_jobs.sh",
        "scripts/sync_sophia_and_submit_known18.sh",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl",
        "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.summary.json",
        "data/processed/prover_eval.jsonl",
        "data/processed/prover_eval.summary.json",
        "data/processed/sany_tlc_pass_sft_v1.jsonl",
        "data/processed/sany_tlc_pass_sft_v1.summary.json",
        "data/processed/sany_tlc_pass_eval_v1.jsonl",
        "data/processed/sany_tlc_pass_eval_v1.summary.json",
        "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json",
        "outputs/manifests/tla_prover_corpus_preflight.json",
        "outputs/manifests/tla_prover_artifacts_v1.json",
    ]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("x\n", encoding="utf-8")

    expect_log = tmp_path / "expect.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(repo),
            "CHATTLA_REMOTE_HOST": "user@remote.example",
            "CHATTLA_REMOTE_PASSWORD": "one-time",
            "CHATTLA_REMOTE_SINGLE_SESSION": "1",
            "EXPECT_LOG": str(expect_log),
        }
    )

    result = subprocess.run(
        ["bash", str(DIRECT_SCRIPT)],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert expect_log.read_text(encoding="utf-8").strip() == "called"


def test_remote_handoff_dry_run_syncs_known18_modules_and_sft_dependencies() -> None:
    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_RELAY_HOST": "relay.example",
            "CHATTLA_RELAY_KEY": "/tmp/relay_key",
            "CHATTLA_RELAY_REPO": "/tmp/relay-repo",
            "CHATTLA_REMOTE_HOST": "remote-hpc",
            "SOPHIA_CTL": "/tmp/remote-ctl",
            "CHATTLA_TLAPM": "/opt/tlaps/bin/tlapm",
        }
    )
    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "--submit-sft-preflight"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    module_paths = [
        line.strip()
        for line in (REPO / "data/processed/tla_prover/tlaps_candidate_modules_18.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert module_paths
    for module_path in module_paths:
        assert module_path in result.stdout

    normalized = result.stdout.replace("\\ ", " ")
    assert "src/" in normalized
    assert "configs/" in normalized
    assert "data/processed/prover_eval.jsonl" in normalized
    assert "data/processed/sany_tlc_pass_eval_v1.jsonl" in normalized
    assert "scripts/install_macmini_launchagents.sh --dry-run" in normalized
    assert "scripts/submit_tla_prover_remote_jobs.sh --submit-sft-preflight" in normalized


def test_remote_handoff_dry_run_honors_relay_env_over_mac_aliases() -> None:
    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_RELAY_HOST": "relay.example",
            "CHATTLA_RELAY_KEY": "/tmp/relay_key",
            "CHATTLA_RELAY_REPO": "/tmp/relay-repo",
            "CHATTLA_REMOTE_HOST": "remote-hpc",
        }
    )

    result = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    normalized = result.stdout.replace("\\ ", " ")
    assert "relay.example" in normalized
    assert "/tmp/relay_key" in normalized
    assert "/tmp/relay-repo" in normalized


def test_remote_handoff_install_launchagents_is_explicit_opt_in() -> None:
    env = os.environ.copy()
    env.update(
        {
            "CHATTLA_RELAY_HOST": "relay.example",
            "CHATTLA_RELAY_KEY": "/tmp/relay_key",
            "CHATTLA_RELAY_REPO": "/tmp/relay-repo",
            "CHATTLA_REMOTE_HOST": "remote-hpc",
        }
    )
    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "--install-launchagents"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    normalized = result.stdout.replace("\\ ", " ")
    assert "CHATTLA_REPO=" in normalized
    assert "scripts/install_macmini_launchagents.sh" in normalized
    assert "scripts/install_macmini_launchagents.sh --dry-run" not in normalized


def test_wait_wrapper_polls_macmini_and_execs_handoff_once() -> None:
    text = WAIT_SCRIPT.read_text(encoding="utf-8")

    assert "BatchMode=yes" in text
    assert "PasswordAuthentication=no" in text
    assert "IdentitiesOnly=yes" in text
    assert "ConnectTimeout=10" in text
    assert "CHATTLA_MAC_HOST" in text
    assert "CHATTLA_RELAY_HOST" in text
    assert "CHATTLA_MAC_KEY" in text
    assert "outputs/logs" in text
    assert "sync_macmini_and_submit_known18.sh" in text
    assert "scripts/sync_macmini_and_submit_known18.sh" in text
    assert "tla_prover_remote_submission.json" in text
    assert "watch_tla_prover_remote_results.sh" in text
    assert "exit 75" in text
    assert "cat $MAC_KEY" not in text


def test_wait_wrapper_retries_then_runs_handoff_once(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    state = tmp_path / "ssh_count"
    handoff_count = tmp_path / "handoff_count"
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        f"""#!/usr/bin/env bash
count=$(cat {state} 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > {state}
if [ "$count" -lt 3 ]; then
  exit 255
fi
exit 0
""",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o755)
    fake_rsync = fake_bin / "rsync"
    fake_rsync.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_rsync.chmod(0o755)

    fake_repo = tmp_path / "repo"
    (fake_repo / "scripts").mkdir(parents=True)
    fake_handoff = fake_repo / "scripts" / "sync_macmini_and_submit_known18.sh"
    fake_handoff.write_text(
        f"""#!/usr/bin/env bash
count=$(cat {handoff_count} 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > {handoff_count}
printf '%s\n' "$@" > {tmp_path / "handoff_args"}
""",
        encoding="utf-8",
    )
    fake_handoff.chmod(0o755)
    fake_watcher = fake_repo / "scripts" / "watch_tla_prover_remote_results.sh"
    fake_watcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_watcher.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(fake_repo),
                "CHATTLA_HANDOFF_LOG_DIR": str(tmp_path / "logs"),
                "CHATTLA_MACMINI_WAIT_SLEEP": "0",
                "CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS": "5",
                "CHATTLA_RELAY_HOST": "relay.example",
                "CHATTLA_REMOTE_HOST": "remote-hpc",
            }
        )

    subprocess.run(
        ["bash", str(WAIT_SCRIPT), "--submit-sft-preflight"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert int(state.read_text(encoding="utf-8").strip()) >= 3
    assert handoff_count.read_text(encoding="utf-8").strip() == "1"
    assert "--submit-sft-preflight" in (tmp_path / "handoff_args").read_text(encoding="utf-8")
    assert (tmp_path / "logs" / "wait_for_macmini_handoff.log").exists()


def test_wait_wrapper_gives_up_without_handoff(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
    fake_ssh.chmod(0o755)

    fake_repo = tmp_path / "repo"
    (fake_repo / "scripts").mkdir(parents=True)
    fake_handoff = fake_repo / "scripts" / "sync_macmini_and_submit_known18.sh"
    fake_handoff.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    fake_handoff.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(fake_repo),
                "CHATTLA_HANDOFF_LOG_DIR": str(tmp_path / "logs"),
                "CHATTLA_MACMINI_WAIT_SLEEP": "0",
                "CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS": "2",
                "CHATTLA_RELAY_HOST": "relay.example",
                "CHATTLA_REMOTE_HOST": "remote-hpc",
            }
        )

    result = subprocess.run(
        ["bash", str(WAIT_SCRIPT)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 75
    log_text = (tmp_path / "logs" / "wait_for_macmini_handoff.log").read_text(encoding="utf-8")
    assert "giving up after 2 attempts" in log_text


def test_wait_wrapper_returns_error_when_submission_report_mirror_fails(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_ssh.chmod(0o755)
    fake_rsync = fake_bin / "rsync"
    fake_rsync.write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
    fake_rsync.chmod(0o755)

    fake_repo = tmp_path / "repo"
    (fake_repo / "scripts").mkdir(parents=True)
    fake_handoff = fake_repo / "scripts" / "sync_macmini_and_submit_known18.sh"
    fake_handoff.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_handoff.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(fake_repo),
                "CHATTLA_HANDOFF_LOG_DIR": str(tmp_path / "logs"),
                "CHATTLA_MACMINI_WAIT_SLEEP": "0",
                "CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS": "1",
                "CHATTLA_RELAY_HOST": "relay.example",
                "CHATTLA_REMOTE_HOST": "remote-hpc",
            }
        )

    result = subprocess.run(
        ["bash", str(WAIT_SCRIPT)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 76
    log_text = (tmp_path / "logs" / "wait_for_macmini_handoff.log").read_text(encoding="utf-8")
    assert "report mirror failed" in log_text
    sentinel = fake_repo / "outputs/manifests/tla_prover_remote_submission_mirror_failed.json"
    assert sentinel.exists()


def test_wait_wrapper_mirror_only_does_not_resubmit(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_ssh.chmod(0o755)
    fake_rsync = fake_bin / "rsync"
    fake_rsync.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_rsync.chmod(0o755)

    fake_repo = tmp_path / "repo"
    (fake_repo / "scripts").mkdir(parents=True)
    handoff_marker = tmp_path / "handoff_ran"
    fake_handoff = fake_repo / "scripts" / "sync_macmini_and_submit_known18.sh"
    fake_handoff.write_text(f"#!/usr/bin/env bash\ntouch {handoff_marker}\nexit 0\n", encoding="utf-8")
    fake_handoff.chmod(0o755)
    watcher_marker = tmp_path / "watcher_ran"
    fake_watcher = fake_repo / "scripts" / "watch_tla_prover_remote_results.sh"
    fake_watcher.write_text(f"#!/usr/bin/env bash\ntouch {watcher_marker}\nexit 0\n", encoding="utf-8")
    fake_watcher.chmod(0o755)
    sentinel = fake_repo / "outputs/manifests/tla_prover_remote_submission_mirror_failed.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("{}", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "CHATTLA_LOCAL_REPO": str(fake_repo),
                "CHATTLA_HANDOFF_LOG_DIR": str(tmp_path / "logs"),
                "CHATTLA_RELAY_HOST": "relay.example",
                "CHATTLA_REMOTE_HOST": "remote-hpc",
            }
        )

    subprocess.run(
        ["bash", str(WAIT_SCRIPT), "--mirror-report-only"],
        cwd=REPO,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert not handoff_marker.exists()
    assert watcher_marker.exists()
    assert not sentinel.exists()


def test_wait_wrapper_uses_relay_env_for_probe(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    seen_args = tmp_path / "ssh_args"
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        f"""#!/usr/bin/env bash
printf '%s\n' "$@" >> {seen_args}
exit 255
""",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o755)

    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "CHATTLA_LOCAL_REPO": str(fake_repo),
            "CHATTLA_HANDOFF_LOG_DIR": str(tmp_path / "logs"),
            "CHATTLA_MACMINI_WAIT_SLEEP": "0",
            "CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS": "1",
            "CHATTLA_RELAY_HOST": "relay.example",
            "CHATTLA_RELAY_KEY": "/tmp/relay_key",
            "CHATTLA_REMOTE_HOST": "remote-hpc",
        }
    )

    subprocess.run(
        ["bash", str(WAIT_SCRIPT)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
    )

    args = seen_args.read_text(encoding="utf-8")
    assert "relay.example" in args
    assert "/tmp/relay_key" in args
