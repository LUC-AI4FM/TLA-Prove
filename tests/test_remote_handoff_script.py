from pathlib import Path
import os
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_macmini_and_submit_known18.sh"
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
