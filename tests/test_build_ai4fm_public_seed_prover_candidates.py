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
