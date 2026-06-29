import json
import subprocess
from pathlib import Path

from scripts.build_ai4fm_public_seed_prover_repair_queue import build_queue


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


def test_build_queue_prioritizes_repair_rows(tmp_path: Path) -> None:
    source = tmp_path / "repair.jsonl"
    seed_modules = tmp_path / "seed.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "SpecA",
                "repo": "org/repo-a",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "content": "---- MODULE SpecA ----\n====\n",
            },
            {
                "module": "SpecB",
                "repo": "org/repo-a",
                "source_path": "SpecB.tla",
                "content_sha256": "bbb",
                "content": "---- MODULE SpecB ----\n====\n",
            },
            {
                "module": "SpecC",
                "repo": "org/repo-b",
                "source_path": "SpecC.tla",
                "content_sha256": "ccc",
                "content": "---- MODULE SpecC ----\n====\n",
            },
            {
                "module": "SpecD",
                "repo": "org/repo-d",
                "source_path": "SpecD.tla",
                "content_sha256": "ddd",
                "content": "---- MODULE SpecD ----\n====\n",
            },
        ],
    )
    _write_jsonl(
        seed_modules,
        [
            {"module": "LocalHelper", "repo": "org/repo-a", "source_path": "LocalHelper.tla", "repo_head_sha": "sha-a"},
            {"module": "SharedHelper", "repo": "org/repo-c", "source_path": "SharedHelper.tla", "repo_head_sha": "sha-c"},
        ],
    )

    def fake_validate(_content: str, *, module_name: str):
        if module_name == "SpecA":
            raw = "Cannot find source file for module TLAPS imported in module SpecA.\n*** Errors: 1\n"
            return _Sany(False, ["Cannot find source file for module TLAPS imported in module SpecA."], raw)
        if module_name == "SpecB":
            raw = "Cannot find source file for module LocalHelper imported in module SpecB.\n*** Errors: 1\n"
            return _Sany(False, ["Cannot find source file for module LocalHelper imported in module SpecB."], raw)
        if module_name == "SpecC":
            raw = "Cannot find source file for module SharedHelper imported in module SpecC.\n*** Errors: 1\n"
            return _Sany(False, ["Cannot find source file for module SharedHelper imported in module SpecC."], raw)
        raw = "Cannot find source file for module MissingHelper imported in module SpecD.\n*** Errors: 1\n"
        return _Sany(False, ["Cannot find source file for module MissingHelper imported in module SpecD."], raw)

    rows, summary = build_queue(
        source=source,
        seed_modules=seed_modules,
        validate_module=fake_validate,
        workers=1,
    )

    assert [row["repair_priority"] for row in rows] == ["p1", "p2", "p3", "p4"]
    assert rows[0]["recommended_action"] == "stage_tlaps_standard_module"
    assert rows[1]["recommended_action"] == "stage_same_repo_seed_helpers"
    assert rows[2]["recommended_action"] == "stage_cross_repo_seed_helpers"
    assert rows[3]["recommended_action"] == "expand_public_dependency_surface"
    assert rows[1]["missing_import_details"][0]["candidate_helpers"][0]["source_path"] == "LocalHelper.tla"
    assert rows[2]["missing_import_details"][0]["candidate_helpers"][0]["repo"] == "org/repo-c"
    assert rows[3]["recoverable_without_new_source"] is False
    assert summary["recoverable_without_new_source_rows"] == 3
    assert summary["blocked_on_missing_public_dependency_rows"] == 1
    assert summary["priority_counts"] == {"p1": 1, "p2": 1, "p3": 1, "p4": 1}
    assert summary["recommended_action_counts"]["stage_cross_repo_seed_helpers"] == 1
    assert summary["missing_import_availability_counts"] == {
        "cross_repo_seed_module": 1,
        "missing_from_seed_surface": 1,
        "same_repo_seed_module": 1,
        "tlaps_standard_module": 1,
    }


def test_cli_writes_repair_queue(tmp_path: Path) -> None:
    source = tmp_path / "repair.jsonl"
    seed_modules = tmp_path / "seed.jsonl"
    out = tmp_path / "repair_queue.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "SpecA",
                "repo": "org/repo-a",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "content": "---- MODULE SpecA ----\nEXTENDS TLAPS\n====\n",
            }
        ],
    )
    _write_jsonl(seed_modules, [])
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_ai4fm_public_seed_prover_repair_queue.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--source",
            str(source),
            "--seed-modules",
            str(seed_modules),
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
    assert rows[0]["repair_priority"] == "p1"
    assert stdout["kept_rows"] == 1
    assert out.with_suffix(".summary.json").exists()


def test_build_queue_uses_post_stage_missing_imports_for_priority(tmp_path: Path) -> None:
    source = tmp_path / "repair.jsonl"
    seed_modules = tmp_path / "seed.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "SpecA",
                "repo": "org/repo-a",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "content": "---- MODULE SpecA ----\nEXTENDS TLAPS\n====\n",
            }
        ],
    )
    _write_jsonl(
        seed_modules,
        [
            {
                "module": "TLAPS",
                "repo": "tlaplus/tlaplus",
                "source_path": "TLAPS.tla",
                "repo_head_sha": "sha-tlaps",
                "content": "---- MODULE TLAPS ----\nPTL == TRUE\n====\n",
            }
        ],
    )

    def fake_validate(_content: str, *, module_name: str):
        assert module_name == "SpecA"
        raw = "Cannot find source file for module TLAPS imported in module SpecA.\n*** Errors: 1\n"
        return _Sany(False, ["Cannot find source file for module TLAPS imported in module SpecA."], raw)

    def fake_validate_file(path: Path):
        if (path.parent / "TLAPS.tla").exists():
            raw = (
                "Cannot find source file for module FiniteSetTheorems imported in module SpecA.\n"
                "*** Errors: 1\n"
            )
            return _Sany(
                False,
                ["Cannot find source file for module FiniteSetTheorems imported in module SpecA."],
                raw,
            )
        raw = "Cannot find source file for module TLAPS imported in module SpecA.\n*** Errors: 1\n"
        return _Sany(False, ["Cannot find source file for module TLAPS imported in module SpecA."], raw)

    rows, summary = build_queue(
        source=source,
        seed_modules=seed_modules,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert rows[0]["initial_missing_imports"] == ["TLAPS"]
    assert rows[0]["staged_modules"] == ["TLAPS"]
    assert rows[0]["missing_imports"] == ["FiniteSetTheorems"]
    assert rows[0]["recommended_action"] == "expand_public_dependency_surface"
    assert rows[0]["recoverable_without_new_source"] is False
    assert rows[0]["missing_import_details"][0]["availability"] == "missing_from_seed_surface"
    assert summary["recoverable_without_new_source_rows"] == 0
    assert summary["blocked_on_missing_public_dependency_rows"] == 1


def test_build_queue_accepts_supplemental_helper_source(tmp_path: Path) -> None:
    source = tmp_path / "repair.jsonl"
    seed_modules = tmp_path / "seed.jsonl"
    helper_source = tmp_path / "helper.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "SpecA",
                "repo": "org/repo-a",
                "source_path": "SpecA.tla",
                "content_sha256": "aaa",
                "content": "---- MODULE SpecA ----\n====\n",
            }
        ],
    )
    _write_jsonl(seed_modules, [])
    _write_jsonl(
        helper_source,
        [
            {
                "module": "SharedHelper",
                "repo": "formalllm/public",
                "source_path": "helpers/SharedHelper.tla",
                "repo_head_sha": "sha-helper",
                "content": "---- MODULE SharedHelper ----\n====\n",
            }
        ],
    )

    def fake_validate(_content: str, *, module_name: str):
        assert module_name == "SpecA"
        raw = "Cannot find source file for module SharedHelper imported in module SpecA.\n*** Errors: 1\n"
        return _Sany(False, ["Cannot find source file for module SharedHelper imported in module SpecA."], raw)

    rows, summary = build_queue(
        source=source,
        seed_modules=seed_modules,
        helper_source_paths=[helper_source],
        validate_module=fake_validate,
        workers=1,
    )

    assert rows[0]["recommended_action"] == "stage_cross_repo_seed_helpers"
    assert rows[0]["recoverable_without_new_source"] is True
    assert rows[0]["missing_import_details"][0]["candidate_helpers"][0]["repo"] == "formalllm/public"
    assert summary["helper_source_paths"] == [str(helper_source)]
    assert summary["helper_source_rows"] == 1
