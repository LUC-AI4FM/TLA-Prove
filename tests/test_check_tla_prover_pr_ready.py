from pathlib import Path

import subprocess

from scripts.check_tla_prover_pr_ready import (
    LOCAL_REPAIR_STATUS_COMMAND,
    SLOW_PYTEST_FILES,
    SYNC_HF_PUBLISH_CORPORA_METADATA_COMMAND,
    build_commands,
    build_report,
    readiness_files,
    scan_files,
)


def test_scan_files_flags_private_hosts_and_paths(tmp_path: Path) -> None:
    candidate = tmp_path / "script.sh"
    candidate.write_text(
        "\n".join(
            [
                "ssh " + "eric" + "spencer@" + "100." + "117.97.102",
                "export CHATTLA_TLAPM=/grand/" + "EVITA/user/tools/tlapm",
                "open /Users/" + "eric" + "/GitHub/ChatTLA/ChatTLA/scripts/check_tla_prover_pr_ready.py",
                "snapshot=" + "plan" + "tain:/home/" + "espen" + "cer2/ChatTLA/data/processed/long_ralph/run_20260609_083126",
                "still blocked by final " + "manual publish " + "approval",
                "dataset=EricSpencer00/chattla-tla-prover-corpora-v1",
            ]
        ),
        encoding="utf-8",
    )

    findings = scan_files([candidate])

    assert len(findings) == 8
    assert {finding["pattern"] for finding in findings} == {
        "private_ssh_user",
        "private_tailscale_or_lan_ip",
        "site_storage_path",
        "local_workspace_repo_path",
        "remote_home_repo_path",
        "manual_publish_approval",
        "site_lab_host",
        "site_lab_user",
    }


def test_build_commands_includes_compact_prover_remote_suite() -> None:
    commands = build_commands()
    joined = "\n".join(" ".join(command) for command in commands)

    assert "python3 -m py_compile" in joined
    assert "scripts/check_public_dataset_claims.py" in joined
    assert "scripts/build_ai4fm_public_seed_file_manifest.py" in joined
    assert "scripts/build_ai4fm_public_seed_license_manifest.py" in joined
    assert "scripts/build_ai4fm_public_seed_prover_candidates.py" in joined
    assert "scripts/build_ai4fm_public_seed_prover_shape_corpora.py" in joined
    assert "scripts/build_ai4fm_public_seed_tla_modules.py" in joined
    assert "scripts/build_ai4fm_public_tlaprove_import.py" in joined
    assert "scripts/build_ai4fm_public_discovery_manifest.py" in joined
    assert "scripts/build_formalllm_public_module_manifest.py" in joined
    assert "scripts/build_formalllm_public_prover_surface.py" in joined
    assert "scripts/build_tla_prover_corpus_experiment_matrix.py" in joined
    assert "scripts/inspect_ai4fm_org_surface.py" in joined
    assert "scripts/inspect_ai4fm_public_tlaprove_corpora.py" in joined
    assert "scripts/inspect_ai4fm_public_dataset_surface.py" in joined
    assert "scripts/inspect_ai4fm_public_seed_prover_funnel.py" in joined
    assert "scripts/inspect_ai4fm_public_seed_prover_repair_surface.py" in joined
    assert "scripts/materialize_processed_tla_corpus.py" in joined
    assert "scripts/inspect_hf_publish_readiness.py" in joined
    assert "scripts/build_benchmark_repair_pairs.py" in joined
    assert "scripts/build_tla_prover_synthetic_repair_pairs.py" in joined
    assert "scripts/build_tla_prover_repair_corpus.py" in joined
    assert "scripts/train_rl_repair.py" in joined
    assert "scripts/build_tla_prover_full_dataset_failure_analysis.py" in joined
    assert "scripts/build_tla_prover_full_dataset_repair_queue.py" in joined
    assert "scripts/build_tla_prover_full_dataset_repair_evidence.py" in joined
    assert "scripts/build_tla_prover_patch_worklist.py" in joined
    assert "scripts/build_tla_prover_full_dataset_validated_repair_pairs.py" in joined
    assert "scripts/sync_hf_publish_corpora_metadata.py" in joined
    assert "scripts/upload_v11.py" in joined
    assert "scripts/build_tla_prover_lane_comparison_plan.py" in joined
    assert "scripts/compare_tla_prover_eval_results.py" in joined
    assert "scripts/train_tla_prover_local.py" in joined
    assert "scripts/train_tla_prover_repair_local.py" in joined
    assert "tests/test_build_ai4fm_public_discovery_manifest.py" in joined
    assert "tests/test_build_formalllm_public_module_manifest.py" in joined
    assert "tests/test_build_formalllm_public_prover_surface.py" in joined
    assert "tests/test_inspect_ai4fm_org_surface.py" in joined
    assert "tests/test_inspect_ai4fm_public_tlaprove_corpora.py" in joined
    assert "tests/test_inspect_ai4fm_public_dataset_surface.py" in joined
    assert "tests/test_inspect_ai4fm_public_seed_prover_funnel.py" in joined
    assert "tests/test_inspect_ai4fm_public_seed_prover_repair_surface.py" in joined
    assert "tests/test_inspect_hf_publish_readiness.py" in joined
    assert "tests/test_sany_validator.py" in joined
    assert "tests/test_build_benchmark_repair_pairs.py" in joined
    assert "tests/test_build_tla_prover_synthetic_repair_pairs.py" in joined
    assert "tests/test_build_tla_prover_repair_corpus.py" in joined
    assert "tests/test_build_tla_prover_full_dataset_failure_analysis.py" in joined
    assert "tests/test_build_tla_prover_full_dataset_repair_queue.py" in joined
    assert "tests/test_build_tla_prover_full_dataset_repair_evidence.py" in joined
    assert "tests/test_build_tla_prover_patch_worklist.py" in joined
    assert "tests/test_build_tla_prover_full_dataset_validated_repair_pairs.py" in joined
    assert "tests/test_repair_dataset.py" in joined
    assert "tests/test_train_rl_repair.py" in joined
    assert "tests/test_train_tla_prover_local.py" in joined
    assert "tests/test_build_tla_prover_lane_comparison_plan.py" in joined
    assert "tests/test_compare_tla_prover_eval_results.py" in joined
    assert "tests/test_train_tla_prover_repair_local.py" in joined
    assert "tests/test_qsub_fc128_artifact_preflight.py" in joined
    assert "tests/test_build_tla_prover_corpus_experiment_matrix.py" in joined
    assert "tests/test_prover_diagnostic_fallbacks.py" in joined
    assert "tests/test_prover_corpus_selection.py" in joined
    assert "tests/test_train_prover_defaults.py" in joined
    assert "tests/test_sync_hf_publish_corpora_metadata.py" in joined
    assert "tests/test_upload_v11.py" in joined
    assert "tests/test_materialize_processed_tla_corpus.py" in joined
    assert "tests/test_build_tla_prover_manifest.py" in joined
    assert "tests/test_build_ai4fm_public_tlaprove_import.py" in joined
    assert "tests/test_build_ai4fm_public_seed_file_manifest.py" in joined
    assert "tests/test_build_ai4fm_public_seed_license_manifest.py" in joined
    assert "tests/test_build_ai4fm_public_seed_prover_candidates.py" in joined
    assert "tests/test_build_ai4fm_public_seed_prover_shape_corpora.py" in joined
    assert "tests/test_build_ai4fm_public_seed_tla_modules.py" in joined
    assert "tests/test_check_public_dataset_claims.py" in joined
    assert "tests/test_legacy_prover_chunk_pipeline_paths.py" in joined
    assert "tests/test_publish_hf.py" in joined
    assert "tests/test_remote_handoff_script.py" not in joined
    assert "tests/test_collect_tla_prover_remote_results.py" not in joined
    assert "tests/test_preflight_tla_prover_remote.py" not in joined
    assert "tests/test_wait_handoff_launchagent_installer.py" not in joined
    assert "tests/test_status_tla_prover_handoff.py" not in joined
    assert "tests/test_probe_tla_prover_control_planes.py" not in joined
    assert "tests/test_submit_tla_prover_remote_jobs.py" not in joined
    assert "tests/test_doctor_tla_prover_handoff.py" not in joined


def test_build_commands_can_include_slow_remote_handoff_suite() -> None:
    commands = build_commands(include_slow_pytest=True)
    joined = "\n".join(" ".join(command) for command in commands)

    assert "tests/test_remote_handoff_script.py" in joined
    assert "tests/test_submit_tla_prover_remote_jobs.py" in joined
    assert "tests/test_collect_tla_prover_remote_results.py" in joined
    assert SLOW_PYTEST_FILES == [
        "tests/test_collect_tla_prover_remote_results.py",
        "tests/test_preflight_tla_prover_remote.py",
        "tests/test_wait_handoff_launchagent_installer.py",
        "tests/test_status_tla_prover_handoff.py",
        "tests/test_probe_tla_prover_control_planes.py",
        "tests/test_remote_handoff_script.py",
        "tests/test_submit_tla_prover_remote_jobs.py",
        "tests/test_doctor_tla_prover_handoff.py",
    ]


def test_readiness_files_include_curated_tracked_outputs(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "tracked.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)

    raw_summary = tmp_path / "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json"
    raw_summary.parent.mkdir(parents=True, exist_ok=True)
    raw_summary.write_text("{}\n", encoding="utf-8")
    formalllm_public_manifest_summary = tmp_path / "data/processed/formalllm_public_module_manifest_v1.summary.json"
    formalllm_public_manifest_summary.write_text("{}\n", encoding="utf-8")
    formalllm_public_prover_surface_summary = tmp_path / "data/processed/formalllm_public_prover_surface_v1.summary.json"
    formalllm_public_prover_surface_summary.write_text("{}\n", encoding="utf-8")
    synthetic_summary = tmp_path / "data/processed/tla_prover_synthetic_repair_pairs_v1.summary.json"
    synthetic_summary.write_text("{}\n", encoding="utf-8")

    for rel in [
        "outputs/autoprover/tlaps_verify_published_161016/manifest.json",
        "outputs/autoprover/tlaps_verify_published_161016/summary.json",
        "outputs/manifests/ai4fm_org_surface.json",
        "outputs/manifests/ai4fm_public_dataset_surface.json",
        "outputs/manifests/ai4fm_public_seed_prover_funnel.json",
        "outputs/manifests/ai4fm_public_seed_prover_repair_surface.json",
        "outputs/manifests/ai4fm_public_seed_license_surface.json",
        "outputs/manifests/hf_publish_readiness.json",
        "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
        "outputs/manifests/tla_prover_full_dataset_repair_queue.jsonl",
        "outputs/manifests/tla_prover_full_dataset_repair_queue.summary.json",
        "outputs/manifests/tla_prover_full_dataset_repair_evidence.jsonl",
        "outputs/manifests/tla_prover_full_dataset_repair_evidence.summary.json",
        "outputs/manifests/tla_prover_patch_worklist.json",
        "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json",
        "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        "outputs/manifests/tla_prover_lane_comparison_plan.json",
        "outputs/manifests/tla_prover_next_experiment.json",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    paths = {path.relative_to(tmp_path).as_posix() for path in readiness_files(tmp_path)}

    assert "outputs/autoprover/tlaps_verify_published_161016/manifest.json" in paths
    assert "outputs/autoprover/tlaps_verify_published_161016/summary.json" in paths
    assert "outputs/manifests/ai4fm_org_surface.json" in paths
    assert "outputs/manifests/ai4fm_public_dataset_surface.json" in paths
    assert "outputs/manifests/ai4fm_public_seed_prover_funnel.json" in paths
    assert "outputs/manifests/ai4fm_public_seed_prover_repair_surface.json" in paths
    assert "outputs/manifests/ai4fm_public_seed_license_surface.json" in paths
    assert "outputs/manifests/hf_publish_readiness.json" in paths
    assert "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json" in paths
    assert "outputs/manifests/tla_prover_full_dataset_repair_queue.jsonl" in paths
    assert "outputs/manifests/tla_prover_full_dataset_repair_queue.summary.json" in paths
    assert "outputs/manifests/tla_prover_full_dataset_repair_evidence.jsonl" in paths
    assert "outputs/manifests/tla_prover_full_dataset_repair_evidence.summary.json" in paths
    assert "outputs/manifests/tla_prover_patch_worklist.json" in paths
    assert "data/processed/tla_prover_full_dataset_validated_repair_pairs_v1.summary.json" in paths
    assert "outputs/manifests/tla_prover_corpus_experiment_matrix.json" in paths
    assert "outputs/manifests/tla_prover_lane_comparison_plan.json" in paths
    assert "outputs/manifests/tla_prover_next_experiment.json" in paths
    assert "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json" in paths
    assert "data/processed/formalllm_public_module_manifest_v1.summary.json" in paths
    assert "data/processed/formalllm_public_prover_surface_v1.summary.json" in paths
    assert "data/processed/tla_prover_synthetic_repair_pairs_v1.summary.json" in paths


def test_readiness_files_can_include_untracked_scripts_but_not_outputs(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    tracked = tmp_path / "scripts" / "tracked.py"
    untracked_script = tmp_path / "scripts" / "scratch.pbs"
    untracked_output = tmp_path / "outputs" / "manifests" / "scratch.json"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("print('tracked')\n", encoding="utf-8")
    untracked_script.write_text("#PBS -A EVITA\n", encoding="utf-8")
    untracked_output.parent.mkdir(parents=True)
    untracked_output.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/tracked.py"], cwd=tmp_path, check=True)

    default_paths = {path.relative_to(tmp_path).as_posix() for path in readiness_files(tmp_path)}
    strict_paths = {
        path.relative_to(tmp_path).as_posix()
        for path in readiness_files(tmp_path, include_untracked_scripts=True)
    }

    assert "scripts/tracked.py" in default_paths
    assert "scripts/scratch.pbs" not in default_paths
    assert "scripts/tracked.py" in strict_paths
    assert "scripts/scratch.pbs" in strict_paths
    assert "outputs/manifests/scratch.json" not in strict_paths


def test_build_report_recommends_hf_metadata_sync(monkeypatch) -> None:
    def fake_run_commands(commands, *, repo):
        return [
            {
                "command": ["python3", "scripts/check_public_dataset_claims.py"],
                "returncode": 1,
                "stdout_tail": '{"ok": false, "findings": []}',
                "stderr_tail": "",
            }
        ]

    monkeypatch.setattr("scripts.check_tla_prover_pr_ready.scan_files", lambda paths: [])
    monkeypatch.setattr("scripts.check_tla_prover_pr_ready.run_commands", fake_run_commands)
    monkeypatch.setattr(
        "scripts.check_tla_prover_pr_ready._local_repair_runtime_status",
        lambda repo: {"path": "outputs/manifests/tla_prover_local_repair_plan.json", "present": False},
    )

    report = build_report(run_tests=True)

    assert report["ok"] is False
    assert report["recommended_fixes"] == [
        {
            "reason": "HF publish bundle metadata is out of sync with the tracked local source artifacts.",
            "command": SYNC_HF_PUBLISH_CORPORA_METADATA_COMMAND,
        }
    ]


def test_build_report_surfaces_local_repair_runtime_status(monkeypatch, tmp_path: Path) -> None:
    plan_path = tmp_path / "outputs" / "manifests" / "tla_prover_local_repair_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        """
{
  "schema": "chattla_tla_prover_local_repair_plan_v1",
  "runtime_import_timeout_s": 10.0,
  "bootstrap_recommendation": {
    "reason": "selected_python_missing_training_dependencies",
    "command": "bash scripts/launch_rl.sh setup",
    "message": "bootstrap repo env"
  },
  "preflight_report": {
    "ok": false,
    "runtime_dependencies": {
      "ok": false,
      "missing": [
        {"module": "datasets.Dataset"},
        {"module": "trl.GRPOTrainer"}
      ]
    }
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("scripts.check_tla_prover_pr_ready.scan_files", lambda paths: [])
    monkeypatch.setattr("scripts.check_tla_prover_pr_ready.readiness_files", lambda repo, include_untracked_scripts=False: [])
    monkeypatch.setattr(
        "scripts.check_tla_prover_pr_ready.run_commands",
        lambda commands, *, repo: [
            {"command": ["python3", "scripts/check_public_dataset_claims.py"], "returncode": 0, "stdout_tail": "", "stderr_tail": ""},
            {"command": ["python3", "scripts/train_tla_prover_repair_local.py"], "returncode": 0, "stdout_tail": "", "stderr_tail": ""},
        ],
    )

    report = build_report(repo=tmp_path, run_tests=True)

    assert report["local_repair_runtime_status"] == {
        "path": "outputs/manifests/tla_prover_local_repair_plan.json",
        "present": True,
        "preflight_ok": False,
        "local_runtime_ready": False,
        "observed_timeout_s": 10.0,
        "runtime_import_timeout_s": 10.0,
        "timeout_reprobe_recommended": False,
        "runtime_missing_modules": ["datasets.Dataset", "trl.GRPOTrainer"],
        "bootstrap_recommendation": {
            "reason": "selected_python_missing_training_dependencies",
            "command": "bash scripts/launch_rl.sh setup",
            "message": "bootstrap repo env",
        },
    }
    assert {
        "reason": "Local repair runtime is not ready on this machine.",
        "command": "bash scripts/launch_rl.sh setup",
    } in report["recommended_fixes"]


def test_build_report_recommends_local_runtime_reprobe_for_short_timeout_manifest(monkeypatch, tmp_path: Path) -> None:
    plan_path = tmp_path / "outputs" / "manifests" / "tla_prover_local_repair_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        """
{
  "schema": "chattla_tla_prover_local_repair_plan_v1",
  "bootstrap_recommendation": {
    "reason": "selected_python_runtime_import_timeouts",
    "command": null,
    "message": "imports timed out"
  },
  "preflight_report": {
    "ok": false,
    "runtime_dependencies": {
      "ok": false,
      "missing": [
        {"module": "datasets.Dataset", "error": "TimeoutExpired: import timed out after 2.0s"},
        {"module": "trl.GRPOTrainer", "error": "TimeoutExpired: import timed out after 2.0s"}
      ]
    }
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("scripts.check_tla_prover_pr_ready.scan_files", lambda paths: [])
    monkeypatch.setattr("scripts.check_tla_prover_pr_ready.readiness_files", lambda repo, include_untracked_scripts=False: [])
    monkeypatch.setattr(
        "scripts.check_tla_prover_pr_ready.run_commands",
        lambda commands, *, repo: [
            {"command": ["python3", "scripts/check_public_dataset_claims.py"], "returncode": 0, "stdout_tail": "", "stderr_tail": ""},
        ],
    )

    report = build_report(repo=tmp_path, run_tests=True)

    assert report["local_repair_runtime_status"] == {
        "path": "outputs/manifests/tla_prover_local_repair_plan.json",
        "present": True,
        "preflight_ok": False,
        "local_runtime_ready": False,
        "observed_timeout_s": 2.0,
        "runtime_import_timeout_s": None,
        "timeout_reprobe_recommended": True,
        "runtime_missing_modules": ["datasets.Dataset", "trl.GRPOTrainer"],
        "bootstrap_recommendation": {
            "reason": "selected_python_runtime_import_timeouts",
            "command": None,
            "message": "imports timed out",
        },
    }
    assert {
        "reason": "Local repair runtime status was collected with a shorter import timeout than the default bounded preflight.",
        "command": LOCAL_REPAIR_STATUS_COMMAND,
    } in report["recommended_fixes"]
