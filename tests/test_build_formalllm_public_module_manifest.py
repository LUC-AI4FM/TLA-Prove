import json
import subprocess
from pathlib import Path

from scripts.build_formalllm_public_module_manifest import build_manifest


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_manifest_classifies_canonical_and_auxiliary_formalllm_files(tmp_path: Path) -> None:
    formalllm_repo = tmp_path / "FormaLLM"
    formalllm_root = formalllm_repo / "data"
    family = formalllm_root / "FamilyOne"
    _write(family / "tla" / "Alpha_clean.tla", "---- MODULE Alpha ----\n====\n")
    _write(family / "tla" / "Alpha.tla", "---- MODULE Alpha ----\n====\n")
    _write(family / "cfg" / "Alpha.cfg", "SPECIFICATION Spec\n")
    _write(formalllm_root / "FamilyTwo" / "toolbox" / "MC.tla", "---- MODULE MC ----\n====\n")
    _write(formalllm_root / "FamilyTwo" / "toolbox" / "MC.cfg", "SPECIFICATION Spec\n")

    rows, summary = build_manifest(formalllm_root=formalllm_root)

    assert len(rows) == 5
    assert summary["kept_rows"] == 5
    assert summary["category_counts"] == {
        "auxiliary_cfg": 1,
        "auxiliary_tla": 1,
        "canonical_cfg": 1,
        "canonical_clean_tla": 1,
        "canonical_variant_tla": 1,
    }
    assert summary["repo_tla_files"] == 3
    assert summary["repo_cfg_files"] == 2
    assert summary["canonical_tree_tla_files"] == 2
    assert summary["canonical_clean_tla_files"] == 1
    assert summary["canonical_variant_tla_files"] == 1
    assert summary["auxiliary_tla_files"] == 1
    assert summary["canonical_cfg_files"] == 1
    assert summary["auxiliary_cfg_files"] == 1


def test_cli_writes_formalllm_public_module_manifest(tmp_path: Path) -> None:
    formalllm_repo = tmp_path / "FormaLLM"
    formalllm_root = formalllm_repo / "data"
    family = formalllm_root / "FamilyOne"
    _write(family / "tla" / "Alpha_clean.tla", "---- MODULE Alpha ----\n====\n")
    out = tmp_path / "formalllm_public_module_manifest_v1.jsonl"
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_formalllm_public_module_manifest.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--formalllm-root",
            str(formalllm_root),
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = json.loads(result.stdout)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["category"] == "canonical_clean_tla"
    assert stdout["kept_rows"] == 1
    assert out.with_suffix(".summary.json").exists()
