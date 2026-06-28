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
    assert any(path.name == "ai4fm_public_tlaprove_import_v1.jsonl" for path in DEFAULT_PATHS)
    assert any(path.name == "sany_tlc_pass_eval_v1.jsonl" for path in DEFAULT_PATHS)
