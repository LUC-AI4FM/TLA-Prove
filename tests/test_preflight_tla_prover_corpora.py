import json
from pathlib import Path

from scripts.preflight_tla_prover_corpora import DEFAULT_PATHS, check_jsonl, build_report


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_check_jsonl_accepts_harmony_messages(tmp_path: Path) -> None:
    path = tmp_path / "ok.jsonl"
    _write(
        path,
        [
            {
                "messages": [
                    {"role": "developer", "content": "dev"},
                    {"role": "user", "content": "task"},
                    {"role": "assistant", "channel": "analysis", "content": "plan"},
                    {"role": "assistant", "channel": "final", "content": "answer"},
                ]
            }
        ],
    )

    result = check_jsonl(path)

    assert result["ok"] is True
    assert result["rows"] == 1
    assert result["errors"] == []
    assert result["path"] == str(path)


def test_check_jsonl_rejects_system_role_and_missing_final(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    _write(path, [{"messages": [{"role": "system", "content": "dev"}, {"role": "user", "content": "task"}]}])

    result = check_jsonl(path)

    assert result["ok"] is False
    assert any("role system" in err for err in result["errors"])
    assert any("assistant final" in err for err in result["errors"])


def test_build_report_includes_sany_tlc_diagnostic(tmp_path: Path) -> None:
    sany = tmp_path / "sany_tlc_pass_sft_v1.jsonl"
    holdout = tmp_path / "diamond_eval_holdout.jsonl"
    _write(
        sany,
        [
            {
                "_tier": "sany_tlc_pass",
                "_module": "TrainA",
                "_evidence": {
                    "sany_pass": True,
                    "tier": "gold",
                    "is_diamond": True,
                    "distinct_states": 3,
                    "invariants_checked": 1,
                    "mutation_caught": True,
                    "trivial_invariant": False,
                },
                "messages": [
                    {"role": "developer", "content": "dev"},
                    {"role": "user", "content": "task"},
                    {"role": "assistant", "channel": "final", "content": "---- MODULE TrainA ----\n====\nSPECIFICATION Spec\n"},
                ],
            }
        ],
    )
    _write(holdout, [])

    report = build_report([sany], holdout=holdout, sany_summary=None)

    assert report["ok"] is True
    assert report["sany_tlc_diagnostic"]["ok"] is True


def test_default_paths_include_prover_eval_gate() -> None:
    assert any(path.name == "prover_eval.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "formalllm_eval_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "chattla_tla_prover_sft_public_expanded_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "chattla_tla_prover_sft_public_all_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "ai4fm_public_tlaprove_import_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "ai4fm_public_seed_tla_modules_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "ai4fm_public_seed_prover_candidates_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "sany_tlc_pass_eval_v1.jsonl" for path in DEFAULT_PATHS)


def test_check_jsonl_accepts_direct_content_rows(tmp_path: Path) -> None:
    path = tmp_path / "seed_candidates.jsonl"
    _write(
        path,
        [
            {
                "repo": "example/alpha",
                "module": "CandidateA",
                "source_path": "CandidateA.tla",
                "content": "---- MODULE CandidateA ----\nEXTENDS Naturals\n====\n",
            }
        ],
    )

    result = check_jsonl(path)

    assert result["ok"] is True
    assert result["rows"] == 1
    assert result["errors"] == []


def test_check_jsonl_accepts_nonstandard_dash_count_module_header(tmp_path: Path) -> None:
    path = tmp_path / "seed_candidates_alt_header.jsonl"
    _write(
        path,
        [
            {
                "repo": "example/alpha",
                "module": "CandidateA",
                "source_path": "CandidateA.tla",
                "content": "--- MODULE CandidateA ---\nEXTENDS Naturals\n====\n",
            }
        ],
    )

    result = check_jsonl(path)

    assert result["ok"] is True
    assert result["rows"] == 1
    assert result["errors"] == []


def test_check_jsonl_rejects_direct_content_module_header_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "seed_candidates_bad.jsonl"
    _write(
        path,
        [
            {
                "repo": "example/alpha",
                "module": "CandidateA",
                "source_path": "CandidateA.tla",
                "content": "---- MODULE Other ----\nEXTENDS Naturals\n====\n",
            }
        ],
    )

    result = check_jsonl(path)

    assert result["ok"] is False
    assert any("module/header mismatch" in err for err in result["errors"])


def test_build_report_proves_formalllm_rows_are_present_in_train_corpora(tmp_path: Path) -> None:
    formalllm = tmp_path / "formalllm_eval_v1.jsonl"
    train = tmp_path / "chattla_tla_prover_sft_v1.jsonl"
    expanded = tmp_path / "chattla_tla_prover_sft_public_expanded_v1.jsonl"
    full_public = tmp_path / "chattla_tla_prover_sft_public_all_v1.jsonl"
    row_a = {
        "_prompt_id": "formalllm/FamilyA/0001/Alpha",
        "messages": [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "task-a"},
            {"role": "assistant", "channel": "final", "content": "answer-a"},
        ],
    }
    row_b = {
        "_prompt_id": "formalllm/FamilyB/0002/Beta",
        "messages": [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "task-b"},
            {"role": "assistant", "channel": "final", "content": "answer-b"},
        ],
    }
    _write(formalllm, [row_a, row_b])
    _write(train, [row_a, row_b, row_a])
    _write(expanded, [row_b, row_a])
    _write(full_public, [row_a, row_b])

    report = build_report([train, expanded, full_public, formalllm], sany_summary=None)

    assert report["ok"] is True
    assert report["formalllm_coverage"]["ok"] is True
    corpora = {item["path"]: item for item in report["formalllm_coverage"]["corpora"]}
    assert corpora[str(train)]["matched_distinct_rows"] == 2
    assert corpora[str(train)]["extra_occurrences_over_formalllm_rows"] == 1
    assert corpora[str(expanded)]["missing_rows"] == 0
    assert corpora[str(full_public)]["missing_rows"] == 0


def test_build_report_flags_missing_formalllm_rows_in_train_corpus(tmp_path: Path) -> None:
    formalllm = tmp_path / "formalllm_eval_v1.jsonl"
    train = tmp_path / "chattla_tla_prover_sft_v1.jsonl"
    row_a = {
        "_prompt_id": "formalllm/FamilyA/0001/Alpha",
        "messages": [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "task-a"},
            {"role": "assistant", "channel": "final", "content": "answer-a"},
        ],
    }
    row_b = {
        "_prompt_id": "formalllm/FamilyB/0002/Beta",
        "messages": [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "task-b"},
            {"role": "assistant", "channel": "final", "content": "answer-b"},
        ],
    }
    _write(formalllm, [row_a, row_b])
    _write(train, [row_a])

    report = build_report([train, formalllm], sany_summary=None)

    assert report["ok"] is False
    assert report["formalllm_coverage"]["ok"] is False
    item = report["formalllm_coverage"]["corpora"][0]
    assert item["missing_rows"] == 1
    assert item["missing_prompt_ids_sample"] == ["formalllm/FamilyB/0002/Beta"]
