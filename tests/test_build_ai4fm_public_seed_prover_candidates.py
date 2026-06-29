import json
from pathlib import Path

from scripts.build_ai4fm_public_seed_prover_candidates import build_prover_candidates, write_outputs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class _Sany:
    def __init__(self, valid: bool, errors: list[str] | None = None) -> None:
        self.valid = valid
        self.errors = errors or []
        self.raw_output = "\n".join(self.errors)


def test_build_prover_candidates_keeps_only_sany_valid_autoprover_rows(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    candidate = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS Naturals\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    non_candidate = "---- MODULE LibraryOnly ----\nFoo == 1\n====\n"
    invalid = "---- MODULE ParseBad ----\nVARIABLE x\nInit == x =\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "CandidateA.tla", "content": candidate},
            {"repo": "example/beta", "module": "LibraryOnly", "source_path": "LibraryOnly.tla", "content": non_candidate},
            {"repo": "example/gamma", "module": "ParseBad", "source_path": "ParseBad.tla", "content": invalid},
            {"repo": "example/delta", "module": "Missing", "source_path": "Missing.tla"},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "ParseBad":
            return _Sany(False, ["*** Parse error"])
        return _Sany(True)

    rows, summary = build_prover_candidates(source, validate_module=fake_validate, workers=1)

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert summary["source_rows"] == 4
    assert summary["kept_rows"] == 1
    assert summary["skipped"] == {
        "missing_module_content": 1,
        "not_autoprover_candidate": 1,
        "sany_invalid": 1,
    }
    assert summary["sample_sany_invalid"][0]["module"] == "ParseBad"
    assert summary["sample_sany_invalid"][0]["detail"] == "*** Parse error"
    assert summary["sample_not_autoprover_candidate"][0]["module"] == "LibraryOnly"


def test_build_prover_candidates_tracks_duplicate_modules(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    candidate_a = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS Naturals\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "a/CandidateA.tla", "content": candidate_a},
            {"repo": "example/beta", "module": "CandidateA", "source_path": "b/CandidateA.tla", "content": candidate_a},
        ],
    )

    rows, summary = build_prover_candidates(
        source,
        validate_module=lambda *_args, **_kwargs: _Sany(True),
        workers=1,
    )

    assert len(rows) == 2
    assert summary["duplicate_modules"] == {"CandidateA": 2}


def test_build_prover_candidates_accepts_source_label_override(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    candidate = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS Naturals\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "CandidateA.tla", "content": candidate},
        ],
    )

    _rows, summary = build_prover_candidates(
        source,
        validate_module=lambda *_args, **_kwargs: _Sany(True),
        workers=1,
        source_label="data/processed/ai4fm_public_seed_tla_modules_v1.jsonl",
    )

    assert summary["source_path"] == "data/processed/ai4fm_public_seed_tla_modules_v1.jsonl"


def test_write_outputs_handles_out_of_repo_target(tmp_path: Path) -> None:
    out = tmp_path / "ai4fm_public_seed_prover_candidates_v1.jsonl"
    rows = [{"module": "CandidateA", "repo": "example/alpha", "source_path": "CandidateA.tla", "content": "---- MODULE CandidateA ----\n====\n"}]
    summary = {"kept_rows": 1}

    final_summary = write_outputs(rows, summary, out)

    assert final_summary["out"] == str(out)
    assert final_summary["summary"] == str(out.with_suffix(".summary.json"))


def test_build_prover_candidates_accepts_nonstandard_dash_count_module_header(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    candidate = (
        "--- MODULE CandidateA ---\n"
        "EXTENDS Naturals\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "CandidateA.tla", "content": candidate},
        ],
    )

    rows, summary = build_prover_candidates(
        source,
        validate_module=lambda *_args, **_kwargs: _Sany(True),
        workers=1,
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert "missing_module_content" not in summary["skipped"]


def test_build_prover_candidates_recovers_rows_via_dependency_staging(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS Helper\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    helper = "---- MODULE Helper ----\nFoo == 1\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "CandidateA.tla", "content": main},
            {"repo": "example/alpha", "module": "Helper", "source_path": "Helper.tla", "content": helper},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module Helper imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        helper_path = path.parent / "Helper.tla"
        if helper_path.exists():
            return _Sany(True)
        return _Sany(False, ["Cannot find source file for module Helper imported in module CandidateA.", "*** Errors: 1"])

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == ["Helper"]
    assert summary["dependency_staging"]["attempted_rows"] == 1
    assert summary["dependency_staging"]["recovered_rows"] == 1
    assert summary["dependency_staging"]["sample_recovered"][0]["staged_modules"] == ["Helper"]


def test_build_prover_candidates_prefers_real_cross_repo_helper_over_rewire_stub(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS SharedHelper\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    helper_real = "---- MODULE SharedHelper ----\nFoo == 1\n====\n"
    helper_rewire = "---- MODULE SharedHelper ----\nBar == 2\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "specs/CandidateA.tla", "content": main},
            {"repo": "tlaplus/CommunityModules", "module": "SharedHelper", "source_path": "modules/SharedHelper.tla", "content": helper_real},
            {"repo": "apalache-mc/apalache", "module": "SharedHelper", "source_path": "src/tla/__rewire_shared_helper_in_apalache.tla", "content": helper_rewire},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module SharedHelper imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        helper = path.parent / "SharedHelper.tla"
        if helper.exists() and "Foo == 1" in helper.read_text(encoding="utf-8"):
            return _Sany(True)
        return _Sany(False, ["wrong helper chosen", "*** Errors: 1"])

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == ["SharedHelper"]
    assert summary["dependency_staging"]["recovered_rows"] == 1


def test_build_prover_candidates_uses_supplemental_helper_source(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    helper_source = tmp_path / "helper_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS SharedHelper\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    helper = "---- MODULE SharedHelper ----\nFoo == 1\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "specs/CandidateA.tla", "content": main},
        ],
    )
    _write_jsonl(
        helper_source,
        [
            {"module": "SharedHelper", "source_path": "helpers/SharedHelper.tla", "content": helper},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module SharedHelper imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        helper_path = path.parent / "SharedHelper.tla"
        if helper_path.exists() and "Foo == 1" in helper_path.read_text(encoding="utf-8"):
            return _Sany(True)
        return _Sany(False, ["wrong helper chosen", "*** Errors: 1"])

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
        helper_source_paths=[helper_source],
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == ["SharedHelper"]
    assert summary["dependency_staging"]["recovered_rows"] == 1


def test_build_prover_candidates_prefers_real_tlaps_module_over_stub(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    helper_source = tmp_path / "helper_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS TLAPS\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    real_tlaps = "---- MODULE TLAPS ----\nSMTT(X) == TRUE\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "specs/CandidateA.tla", "content": main},
        ],
    )
    _write_jsonl(
        helper_source,
        [
            {"repo": "tlaplus/tlapm", "module": "TLAPS", "source_path": "library/TLAPS.tla", "content": real_tlaps},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module TLAPS imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        helper_path = path.parent / "TLAPS.tla"
        if helper_path.exists() and "SMTT(X) == TRUE" in helper_path.read_text(encoding="utf-8"):
            return _Sany(True)
        return _Sany(False, ["wrong tlaps helper chosen", "*** Errors: 1"])

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
        helper_source_paths=[helper_source],
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == ["TLAPS"]
    assert summary["dependency_staging"]["recovered_rows"] == 1


def test_build_prover_candidates_prefers_best_same_repo_helper_path(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS SharedHelper\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    helper_good = "---- MODULE SharedHelper ----\nFoo == 1\n====\n"
    helper_bad = "---- MODULE SharedHelper ----\nBar == 2\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "specs/byz/CandidateA.tla", "content": main},
            {"repo": "example/alpha", "module": "SharedHelper", "source_path": "specs/byz/SharedHelper.tla", "content": helper_good},
            {"repo": "example/alpha", "module": "SharedHelper", "source_path": "specs/other/SharedHelper.tla", "content": helper_bad},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module SharedHelper imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        helper_path = path.parent / "SharedHelper.tla"
        if helper_path.exists() and "Foo == 1" in helper_path.read_text(encoding="utf-8"):
            return _Sany(True)
        return _Sany(False, ["wrong same-repo helper chosen", "*** Errors: 1"])

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == ["SharedHelper"]
    assert summary["dependency_staging"]["recovered_rows"] == 1


def test_build_prover_candidates_prefers_community_utility_helper_when_same_repo_copy_is_unrelated(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS Functions\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    helper_same_repo = "---- MODULE Functions ----\nFoo == 1\n====\n"
    helper_community = "---- MODULE Functions ----\nSumFunctionOnSet(S, f) == 1\n====\n"
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "specifications/byz/CandidateA.tla", "content": main},
            {"repo": "example/alpha", "module": "Functions", "source_path": "specifications/other/Functions.tla", "content": helper_same_repo},
            {"repo": "tlaplus/CommunityModules", "module": "Functions", "source_path": "modules/Functions.tla", "content": helper_community},
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module Functions imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        helper_path = path.parent / "Functions.tla"
        if helper_path.exists() and "SumFunctionOnSet" in helper_path.read_text(encoding="utf-8"):
            return _Sany(True)
        return _Sany(False, ["wrong utility helper chosen", "*** Errors: 1"])

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == ["Functions"]
    assert summary["dependency_staging"]["recovered_rows"] == 1


def test_build_prover_candidates_recovers_deep_transitive_import_chain(tmp_path: Path) -> None:
    source = tmp_path / "seed_modules.jsonl"
    main = (
        "---- MODULE CandidateA ----\n"
        "EXTENDS Helper1\n"
        "VARIABLE x\n"
        "vars == <<x>>\n"
        "Init == x = 0\n"
        "Next == x' = x\n"
        "Spec == Init /\\ [][Next]_vars\n"
        "TypeOK == x \\in 0..1\n"
        "====\n"
    )
    helper_rows = [
        {"repo": "example/alpha", "module": f"Helper{i}", "source_path": f"Helper{i}.tla", "content": f"---- MODULE Helper{i} ----\nFoo{i} == {i}\n====\n"}
        for i in range(1, 10)
    ]
    _write_jsonl(
        source,
        [
            {"repo": "example/alpha", "module": "CandidateA", "source_path": "CandidateA.tla", "content": main},
            *helper_rows,
        ],
    )

    def fake_validate(content: str, *, module_name: str) -> _Sany:
        if module_name == "CandidateA":
            return _Sany(False, ["Cannot find source file for module Helper1 imported in module CandidateA.", "*** Errors: 1"])
        return _Sany(True)

    def fake_validate_file(path: Path) -> _Sany:
        for index in range(1, 10):
            helper_path = path.parent / f"Helper{index}.tla"
            if not helper_path.exists():
                imported_by = "CandidateA" if index == 1 else f"Helper{index - 1}"
                return _Sany(
                    False,
                    [f"Cannot find source file for module Helper{index} imported in module {imported_by}.", "*** Errors: 1"],
                )
        return _Sany(True)

    rows, summary = build_prover_candidates(
        source,
        validate_module=fake_validate,
        validate_file=fake_validate_file,
        workers=1,
    )

    assert [row["module"] for row in rows] == ["CandidateA"]
    assert rows[0]["dependency_staging"]["staged_modules"] == [f"Helper{i}" for i in range(1, 10)]
    assert summary["dependency_staging"]["recovered_rows"] == 1
