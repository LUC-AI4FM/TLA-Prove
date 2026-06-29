from pathlib import Path

import subprocess

from scripts.check_tla_prover_pr_ready import build_commands, readiness_files, scan_files


def test_scan_files_flags_private_hosts_and_paths(tmp_path: Path) -> None:
    candidate = tmp_path / "script.sh"
    candidate.write_text(
        "\n".join(
            [
                "ssh " + "eric" + "spencer@" + "100." + "117.97.102",
                "export CHATTLA_TLAPM=/grand/" + "EVITA/user/tools/tlapm",
                "dataset=EricSpencer00/chattla-tla-prover-corpora-v1",
            ]
        ),
        encoding="utf-8",
    )

    findings = scan_files([candidate])

    assert len(findings) == 3
    assert {finding["pattern"] for finding in findings} == {
        "private_ssh_user",
        "private_tailscale_or_lan_ip",
        "site_storage_path",
    }


def test_build_commands_includes_compact_prover_remote_suite() -> None:
    commands = build_commands()
    joined = "\n".join(" ".join(command) for command in commands)

    assert "python3 -m py_compile" in joined
    assert "scripts/check_public_dataset_claims.py" in joined
    assert "scripts/build_ai4fm_public_seed_file_manifest.py" in joined
    assert "scripts/build_ai4fm_public_seed_license_manifest.py" in joined
    assert "scripts/build_ai4fm_public_seed_prover_candidates.py" in joined
    assert "scripts/build_ai4fm_public_seed_tla_modules.py" in joined
    assert "scripts/build_ai4fm_public_tlaprove_import.py" in joined
    assert "scripts/build_ai4fm_public_discovery_manifest.py" in joined
    assert "scripts/inspect_ai4fm_org_surface.py" in joined
    assert "scripts/inspect_ai4fm_public_tlaprove_corpora.py" in joined
    assert "scripts/inspect_ai4fm_public_dataset_surface.py" in joined
    assert "scripts/inspect_ai4fm_public_seed_prover_funnel.py" in joined
    assert "scripts/materialize_processed_tla_corpus.py" in joined
    assert "scripts/inspect_hf_publish_readiness.py" in joined
    assert "scripts/sync_hf_publish_corpora_metadata.py" in joined
    assert "scripts/upload_v11.py" in joined
    assert "tests/test_remote_handoff_script.py" in joined
    assert "tests/test_build_ai4fm_public_discovery_manifest.py" in joined
    assert "tests/test_inspect_ai4fm_org_surface.py" in joined
    assert "tests/test_inspect_ai4fm_public_tlaprove_corpora.py" in joined
    assert "tests/test_inspect_ai4fm_public_dataset_surface.py" in joined
    assert "tests/test_inspect_ai4fm_public_seed_prover_funnel.py" in joined
    assert "tests/test_inspect_hf_publish_readiness.py" in joined
    assert "tests/test_qsub_fc128_artifact_preflight.py" in joined
    assert "tests/test_prover_diagnostic_fallbacks.py" in joined
    assert "tests/test_train_prover_defaults.py" in joined
    assert "tests/test_sync_hf_publish_corpora_metadata.py" in joined
    assert "tests/test_upload_v11.py" in joined
    assert "tests/test_materialize_processed_tla_corpus.py" in joined
    assert "tests/test_preflight_tla_prover_remote.py" in joined
    assert "tests/test_build_tla_prover_manifest.py" in joined
    assert "tests/test_build_ai4fm_public_tlaprove_import.py" in joined
    assert "tests/test_build_ai4fm_public_seed_file_manifest.py" in joined
    assert "tests/test_build_ai4fm_public_seed_license_manifest.py" in joined
    assert "tests/test_build_ai4fm_public_seed_prover_candidates.py" in joined
    assert "tests/test_build_ai4fm_public_seed_tla_modules.py" in joined
    assert "tests/test_check_public_dataset_claims.py" in joined
    assert "tests/test_legacy_prover_chunk_pipeline_paths.py" in joined
    assert "tests/test_publish_hf.py" in joined


def test_readiness_files_include_curated_tracked_outputs(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "tracked.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)

    raw_summary = tmp_path / "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json"
    raw_summary.parent.mkdir(parents=True, exist_ok=True)
    raw_summary.write_text("{}\n", encoding="utf-8")

    for rel in [
        "outputs/autoprover/tlaps_verify_published_161016/manifest.json",
        "outputs/autoprover/tlaps_verify_published_161016/summary.json",
        "outputs/manifests/ai4fm_org_surface.json",
        "outputs/manifests/ai4fm_public_dataset_surface.json",
        "outputs/manifests/ai4fm_public_seed_prover_funnel.json",
        "outputs/manifests/ai4fm_public_seed_license_surface.json",
        "outputs/manifests/hf_publish_readiness.json",
        "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json",
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
    assert "outputs/manifests/ai4fm_public_seed_license_surface.json" in paths
    assert "outputs/manifests/hf_publish_readiness.json" in paths
    assert "outputs/manifests/hf_publish_readiness.chattla_20b_fc128best.json" in paths
    assert "data/processed/ai4fm_public_tlaprove_import_raw_v1.summary.json" in paths


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
