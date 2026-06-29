import json
import subprocess
import sys
from pathlib import Path

from scripts.preflight_tla_prover_remote import run_preflight


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    for rel in [
        "src/shared/tlc/tla2tools.jar",
        "scripts/autoprover_smoke.py",
        "scripts/summarize_autoprover_smoke.py",
        "scripts/qsub_autoprover_known18_corrected_smoke.pbs",
        "outputs/diamond_gen/example/AtomicRegister.tla",
    ]:
        _write(repo / rel)
    _write(
        repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        "outputs/diamond_gen/example/AtomicRegister.tla\n",
    )
    _write(
        repo / "outputs/manifests/tla_prover_artifacts_v1.json",
        json.dumps(
            {
                "artifacts": {
                    "known18_module_list": {
                        "exists": True,
                        "path": "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
                        "sha256": "abc",
                    }
                }
            }
        ),
    )
    _write(repo / "outputs/manifests/tla_prover_corpus_preflight.json", json.dumps({"ok": True}))
    return repo


def test_remote_preflight_accepts_minimal_known18_repo(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)

    report = run_preflight(repo=repo, module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt")

    assert report["ok"] is True
    assert report["module_count"] == 1


def test_remote_preflight_rejects_missing_module_path(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / "outputs/diamond_gen/example/AtomicRegister.tla").unlink()

    report = run_preflight(repo=repo, module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt")

    assert report["ok"] is False
    assert any("missing module listed" in error for error in report["errors"])


def test_remote_preflight_requires_sft_dependencies_when_enabled(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        sft_preflight=True,
    )

    assert report["ok"] is False
    assert any("data/processed/prover_eval.jsonl" in error for error in report["errors"])
    assert any("src/training/train.py" in error for error in report["errors"])


def test_remote_preflight_accepts_public_sft_fallback_when_local_train_missing(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    for rel in [
        "configs/accelerate_fsdp.yaml",
        "data/processed/prover_eval.jsonl",
        "outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "src/training/train.py",
        "src/training/tlc_eval_callback.py",
    ]:
        _write(repo / rel)

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        sft_preflight=True,
    )

    assert report["ok"] is True
    assert (
        report["resolved_sft_train_file"]
        == "outputs/hf_publish/chattla-tla-prover-corpora-v1/data/train/chattla_tla_prover_sft_v1.jsonl"
    )
    assert report["resolved_sft_corpus"]["alias"] == "default"


def test_remote_preflight_accepts_requested_expanded_sft_train_file(tmp_path: Path, monkeypatch) -> None:
    repo = _minimal_repo(tmp_path)
    for rel in [
        "configs/accelerate_fsdp.yaml",
        "data/processed/prover_eval.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.summary.json",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "src/training/train.py",
        "src/training/tlc_eval_callback.py",
    ]:
        _write(repo / rel)

    monkeypatch.setenv(
        "CHATTLA_TLA_PROVER_TRAIN_FILE",
        "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl",
    )

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        sft_preflight=True,
    )

    assert report["ok"] is True
    assert (
        report["resolved_sft_train_file"]
        == "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl"
    )
    assert report["resolved_sft_corpus"]["alias"] == "expanded"


def test_remote_preflight_accepts_requested_full_public_alias(tmp_path: Path, monkeypatch) -> None:
    repo = _minimal_repo(tmp_path)
    for rel in [
        "configs/accelerate_fsdp.yaml",
        "data/processed/prover_eval.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.summary.json",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "src/training/train.py",
        "src/training/tlc_eval_callback.py",
    ]:
        _write(repo / rel)

    monkeypatch.setenv("CHATTLA_TLA_PROVER_TRAIN_FILE", "full-public")

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        sft_preflight=True,
    )

    assert report["ok"] is True
    assert (
        report["resolved_sft_train_file"]
        == "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl"
    )
    assert report["resolved_sft_corpus"]["alias"] == "full-public"


def test_remote_preflight_checks_sft_tools_when_required(tmp_path: Path, monkeypatch) -> None:
    repo = _minimal_repo(tmp_path)
    for rel in [
        "configs/accelerate_fsdp.yaml",
        "data/processed/prover_eval.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "src/training/train.py",
        "src/training/tlc_eval_callback.py",
    ]:
        _write(repo / rel)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    java = fake_bin / "java"
    java.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    java.chmod(0o755)
    tlapm = fake_bin / "tlapm"
    tlapm.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    tlapm.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.setenv("CHATTLA_PYTHON", str(tmp_path / "missing-python"))
    monkeypatch.setenv("CHATTLA_BASE_MODEL", str(tmp_path / "missing-model"))

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        sft_preflight=True,
        require_tools=True,
        tlapm=tlapm,
    )

    assert report["ok"] is False
    assert any("python not found" in error for error in report["errors"])
    assert any("base model path not found" in error for error in report["errors"])


def test_remote_preflight_uses_default_tlapm_when_env_is_unset(tmp_path: Path, monkeypatch) -> None:
    repo = _minimal_repo(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    java = fake_bin / "java"
    java.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    java.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.delenv("CHATTLA_TLAPM", raising=False)

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        require_tools=True,
    )

    assert report["ok"] is False
    assert any("tlapm not found on PATH: tlapm" in error for error in report["errors"])
    assert not any("tlapm is not executable: ." in error for error in report["errors"])


def test_remote_preflight_reports_import_probe_timeout(tmp_path: Path, monkeypatch) -> None:
    repo = _minimal_repo(tmp_path)
    for rel in [
        "configs/accelerate_fsdp.yaml",
        "data/processed/prover_eval.jsonl",
        "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl",
        "scripts/qsub_sophia_tla_prover_sft_preflight.pbs",
        "src/training/train.py",
        "src/training/tlc_eval_callback.py",
    ]:
        _write(repo / rel)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    java = fake_bin / "java"
    java.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    java.chmod(0o755)
    tlapm = fake_bin / "tlapm"
    tlapm.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    tlapm.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.setenv("CHATTLA_PYTHON", sys.executable)
    monkeypatch.setenv("CHATTLA_PYTHON_IMPORT_TIMEOUT", "7")

    def _boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", args[0]), timeout=kwargs["timeout"])

    monkeypatch.setattr("scripts.preflight_tla_prover_remote.subprocess.run", _boom)

    report = run_preflight(
        repo=repo,
        module_list=repo / "data/processed/tla_prover/tlaps_candidate_modules_18.txt",
        sft_preflight=True,
        require_tools=True,
        tlapm=tlapm,
    )

    assert report["ok"] is False
    assert any("python import probe timed out after 7s" in error for error in report["errors"])
