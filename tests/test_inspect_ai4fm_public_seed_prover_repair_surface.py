import json
import subprocess
from pathlib import Path

from scripts.inspect_ai4fm_public_seed_prover_repair_surface import build_report


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


def test_build_report_summarizes_import_blocked_repair_surface(tmp_path: Path) -> None:
    source = tmp_path / "repair.jsonl"
    source_summary = tmp_path / "repair.summary.json"
    seed_modules = tmp_path / "seed.jsonl"

    _write_jsonl(
        source,
        [
            {"module": "SpecA", "repo": "org/repo-a", "source_path": "SpecA.tla", "content": "---- MODULE SpecA ----\n====\n"},
            {"module": "SpecB", "repo": "org/repo-a", "source_path": "SpecB.tla", "content": "---- MODULE SpecB ----\n====\n"},
            {"module": "SpecC", "repo": "org/repo-b", "source_path": "SpecC.tla", "content": "---- MODULE SpecC ----\n====\n"},
        ],
    )
    _write(source_summary, json.dumps({"kept_rows": 3, "excluded_sany_clean_rows": 2}))
    _write_jsonl(
        seed_modules,
        [
            {"module": "LocalHelper", "repo": "org/repo-a", "source_path": "LocalHelper.tla", "content": "---- MODULE LocalHelper ----\n====\n"},
            {"module": "SharedHelper", "repo": "org/repo-c", "source_path": "SharedHelper.tla", "content": "---- MODULE SharedHelper ----\n====\n"},
        ],
    )

    def fake_validate(_content: str, *, module_name: str):
        if module_name == "SpecA":
            raw = "In module SpecA\nCannot find source file for module TLAPS imported in module SpecA.\n*** Errors: 1\n"
            return _Sany(False, ["Cannot find source file for module TLAPS imported in module SpecA.", "*** Errors: 1"], raw)
        if module_name == "SpecB":
            raw = (
                "In module SpecB\n"
                "Cannot find source file for module LocalHelper imported in module SpecB.\n"
                "Cannot find source file for module SharedHelper imported in module SpecB.\n"
                "*** Errors: 2\n"
            )
            return _Sany(
                False,
                ["Cannot find source file for module LocalHelper imported in module SpecB.", "*** Errors: 2"],
                raw,
            )
        raw = "In module SpecC\nUnknown operator: FooBar\n*** Errors: 1\n"
        return _Sany(False, ["Unknown operator: FooBar", "*** Errors: 1"], raw)

    report = build_report(
        source=source,
        source_summary=source_summary,
        seed_modules=seed_modules,
        validate_module=fake_validate,
        workers=1,
    )

    assert report["repair_surface"] == {
        "rows": 3,
        "unique_modules": 3,
        "unique_repos": 2,
        "excluded_sany_clean_rows": 2,
    }
    assert report["failure_categories"] == [
        {"name": "missing_import", "count": 2},
        {"name": "unknown_operator", "count": 1},
    ]
    assert report["missing_imports"]["rows_with_missing_imports"] == 2
    assert report["missing_imports"]["rows_recoverable_from_seed_surface_or_tlaps_stub"] == 2
    assert report["missing_imports"]["availability_counts"] == {
        "cross_repo_seed_module": 1,
        "same_repo_seed_module": 1,
        "tlaps_standard_module": 1,
    }
    assert report["missing_imports"]["top_missing_modules"][0]["module"] == "TLAPS"
    assert report["by_repo"]["top_repair_repos"][0] == {"name": "org/repo-a", "count": 2}
    assert report["warnings"] == []


def test_cli_writes_repair_surface_report(tmp_path: Path) -> None:
    source = tmp_path / "repair.jsonl"
    source_summary = tmp_path / "repair.summary.json"
    seed_modules = tmp_path / "seed.jsonl"
    out = tmp_path / "report.json"

    _write_jsonl(
        source,
        [{"module": "SpecA", "repo": "org/repo-a", "source_path": "SpecA.tla", "content": "---- MODULE SpecA ----\n====\n"}],
    )
    _write(source_summary, json.dumps({"kept_rows": 1, "excluded_sany_clean_rows": 0}))
    _write_jsonl(seed_modules, [])
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspect_ai4fm_public_seed_prover_repair_surface.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--source",
            str(source),
            "--source-summary",
            str(source_summary),
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
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert stdout["repair_surface"]["rows"] == 1
    assert saved == stdout
