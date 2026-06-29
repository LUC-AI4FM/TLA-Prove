import json
import subprocess
from pathlib import Path

from scripts.build_ai4fm_public_seed_prover_recovery_probe import build_probe


class _Sany:
    def __init__(self, valid: bool, errors: list[str], raw_output: str) -> None:
        self.valid = valid
        self.errors = errors
        self.raw_output = raw_output


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    _write(path, "\n".join(json.dumps(row) for row in rows) + "\n")


def test_build_probe_measures_current_builder_outcomes(tmp_path: Path) -> None:
    repair_queue = tmp_path / "repair_queue.jsonl"
    full_source = tmp_path / "full_source.jsonl"
    _write_jsonl(
        repair_queue,
        [
            {
                "repo": "org/repo-a",
                "module": "SpecA",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "repair_priority": "p1",
                "recommended_action": "stage_tlaps_standard_module",
            },
            {
                "repo": "org/repo-b",
                "module": "SpecB",
                "source_path": "SpecB.tla",
                "content_sha256": "bbb",
                "repair_priority": "p3",
                "recommended_action": "stage_cross_repo_seed_helpers",
            },
            {
                "repo": "org/repo-c",
                "module": "SpecC",
                "source_path": "SpecC.tla",
                "content_sha256": "ccc",
                "repair_priority": "p4",
                "recommended_action": "expand_public_dependency_surface",
            },
        ],
    )
    _write_jsonl(
        full_source,
        [
            {
                "repo": "org/repo-a",
                "module": "SpecA",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "content": "---- MODULE SpecA ----\n====\n",
            },
            {
                "repo": "org/repo-b",
                "module": "SpecB",
                "source_path": "SpecB.tla",
                "content_sha256": "bbb",
                "content": "---- MODULE SpecB ----\n====\n",
            },
            {
                "repo": "org/repo-c",
                "module": "SpecC",
                "source_path": "SpecC.tla",
                "content_sha256": "ccc",
                "content": "---- MODULE SpecC ----\n====\n",
            },
            {
                "repo": "org/repo-z",
                "module": "SharedHelper",
                "source_path": "SharedHelper.tla",
                "content_sha256": "zzz",
                "content": "---- MODULE SharedHelper ----\n====\n",
            },
        ],
    )

    def fake_validate_module(_content: str, *, module_name: str):
        if module_name == "SpecA":
            return _Sany(False, ["Cannot find source file for module TLAPS imported in module SpecA."], "Cannot find source file for module TLAPS imported in module SpecA.\n")
        if module_name == "SpecB":
            return _Sany(False, ["Cannot find source file for module SharedHelper imported in module SpecB."], "Cannot find source file for module SharedHelper imported in module SpecB.\n")
        return _Sany(False, ["Cannot find source file for module MissingHelper imported in module SpecC."], "Cannot find source file for module MissingHelper imported in module SpecC.\n")

    def fake_validate_file(path: Path):
        module = path.stem
        if module == "SpecA":
            return _Sany(False, ["*** Errors: 2"], "*** Errors: 2\n")
        if module == "SpecB":
            return _Sany(False, ["Cannot find source file for module AnotherHelper imported in module SpecB."], "Cannot find source file for module AnotherHelper imported in module SpecB.\n")
        return _Sany(False, ["Cannot find source file for module MissingHelper imported in module SpecC."], "Cannot find source file for module MissingHelper imported in module SpecC.\n")

    rows, summary = build_probe(
        repair_queue=repair_queue,
        full_source=full_source,
        validate_module=fake_validate_module,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert [row["probe_status"] for row in rows] == [
        "post_stage_non_import_error",
        "still_missing_imports_after_staging",
        "still_missing_imports_after_staging",
    ]
    assert rows[0]["staged_modules"] == ["TLAPS"]
    assert rows[1]["staged_modules"] == ["SharedHelper"]
    assert rows[1]["unresolved_missing_imports"] == ["AnotherHelper"]
    assert summary["rows_recovered_current_builder"] == 0
    assert summary["probe_status_counts"] == {
        "post_stage_non_import_error": 1,
        "still_missing_imports_after_staging": 2,
    }
    assert summary["status_by_recommended_action"]["stage_tlaps_standard_module"]["post_stage_non_import_error"] == 1
    assert summary["top_unresolved_missing_modules"][0]["module"] in {"AnotherHelper", "MissingHelper"}


def test_cli_writes_recovery_probe(tmp_path: Path) -> None:
    repair_queue = tmp_path / "repair_queue.jsonl"
    full_source = tmp_path / "full_source.jsonl"
    out = tmp_path / "probe.jsonl"
    _write_jsonl(
        repair_queue,
        [
            {
                "repo": "org/repo-a",
                "module": "SpecA",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "repair_priority": "p1",
                "recommended_action": "stage_tlaps_standard_module",
            }
        ],
    )
    _write_jsonl(
        full_source,
        [
            {
                "repo": "org/repo-a",
                "module": "SpecA",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "content": "---- MODULE SpecA ----\n====\n",
            }
        ],
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_ai4fm_public_seed_prover_recovery_probe.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--repair-queue",
            str(repair_queue),
            "--full-source",
            str(full_source),
            "--workers",
            "1",
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
    assert stdout["kept_rows"] == 1
    assert out.with_suffix(".summary.json").exists()
