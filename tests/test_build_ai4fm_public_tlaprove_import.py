import json
from pathlib import Path

from scripts.build_ai4fm_public_tlaprove_import import (
    build_import,
    source_specs,
    write_outputs,
)


def _assistant_messages(final_text: str) -> list[dict]:
    return [
        {"role": "system", "content": "dev"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "analysis"},
        {"role": "assistant", "content": final_text},
    ]


def test_build_import_normalizes_and_dedupes_public_corpora() -> None:
    rows, summary = build_import(
        {
            "processed_train": [
                {
                    "_prompt_id": "train/1",
                    "_source": "processed_train",
                    "messages": _assistant_messages("---- MODULE A ----\n====\nSPECIFICATION Spec\n"),
                }
            ],
            "diamond_sft_v3": [
                {
                    "_prompt_id": "diamond/dup",
                    "_source": "diamond_sft_v3",
                    "messages": _assistant_messages("---- MODULE A ----\n====\nSPECIFICATION Spec\n"),
                },
                {
                    "_prompt_id": "diamond/2",
                    "_source": "diamond_sft_v3",
                    "messages": _assistant_messages("---- MODULE B ----\n====\nSPECIFICATION Spec\n"),
                },
            ],
            "processed_eval": [
                {"messages": _assistant_messages("---- MODULE Eval ----\n====\nSPECIFICATION Spec\n")}
            ],
            "diamond_eval_holdout": [
                {
                    "module": "HoldoutA",
                    "batch": "protocols",
                    "tier": "gold",
                    "topic_desc": "Holdout task",
                    "spec": "---- MODULE HoldoutA ----\nTypeOK == TRUE\n====\n",
                    "sany_pass": True,
                    "is_diamond": True,
                    "mutation_caught": True,
                    "trivial_invariant": False,
                    "distinct_states": 4,
                    "invariants_checked": 1,
                }
            ],
            "ralph_train": [
                {
                    "prompt": "Write the TLA+ module RalphA.",
                    "reference": "---- MODULE RalphA ----\nTypeOK == TRUE\n====\n",
                    "source": "ralph_gen",
                    "spec_id": "ralph:1",
                    "normalized_sha1": "abc",
                    "topic": "existing",
                    "difficulty": "med",
                    "aux_modules": {},
                }
            ],
            "ralph_dev": [],
        },
        generated_at="2026-06-28T00:00:00+00:00",
    )

    assert [row["_module"] for row in rows] == ["A", "B", "Eval", "HoldoutA", "RalphA"]
    assert rows[0]["messages"][0]["role"] == "developer"
    assert rows[0]["messages"][2]["channel"] == "analysis"
    assert rows[0]["messages"][3]["channel"] == "final"
    assert rows[0]["_ai4fm_public_corpora"] == ["diamond_sft_v3", "processed_train"]
    assert rows[0]["_canonical_final_sha256"]
    assert rows[3]["messages"][1]["content"] == "Write a TLA+ specification for the following:\n\nHoldout task\n"
    assert rows[3]["messages"][-1]["content"].endswith("INVARIANT TypeOK\n")
    assert rows[4]["messages"][1]["content"] == "Write the TLA+ module RalphA."
    assert rows[4]["messages"][-1]["content"].endswith("INVARIANT TypeOK\n")

    assert summary["raw_rows"] == 6
    assert summary["kept_rows"] == 5
    assert summary["duplicate_rows_collapsed"] == 1
    assert summary["per_corpus"]["processed_train"]["kept_rows"] == 1
    assert summary["per_corpus"]["diamond_sft_v3"]["kept_rows"] == 1
    assert summary["per_corpus"]["diamond_eval_holdout"]["kept_rows"] == 1
    assert summary["per_corpus"]["ralph_train"]["kept_rows"] == 1


def test_source_specs_cover_all_public_tlaprove_inputs() -> None:
    specs = source_specs()

    assert set(specs) == {
        "processed_train",
        "processed_eval",
        "diamond_eval_holdout",
        "diamond_sft_v3",
        "ralph_train",
        "ralph_dev",
    }
    assert specs["diamond_eval_holdout"]["kind"] == "holdout"
    assert specs["ralph_train"]["kind"] == "ralph"


def test_source_specs_can_include_additional_public_jsonl_surface() -> None:
    specs = source_specs(include_additional_public_jsonl=True)

    assert "toy_train" in specs
    assert "toy_eval" in specs
    assert "diamond_gen_communication_protocols" in specs
    assert "diamond_gen_diamond_generated" in specs
    assert specs["toy_train"]["kind"] == "messages"
    assert specs["diamond_gen_communication_protocols"]["kind"] == "holdout"


def test_build_import_summary_is_json_serializable(tmp_path: Path) -> None:
    rows, summary = build_import(
        {name: [] for name in source_specs()},
        generated_at="2026-06-28T00:00:00+00:00",
    )

    assert rows == []
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["kept_rows"] == 0


def test_build_import_can_keep_raw_duplicate_rows() -> None:
    rows, summary = build_import(
        {
            "processed_train": [
                {
                    "_prompt_id": "train/1",
                    "_source": "processed_train",
                    "messages": _assistant_messages("---- MODULE A ----\n====\nSPECIFICATION Spec\n"),
                }
            ],
            "diamond_sft_v3": [
                {
                    "_prompt_id": "diamond/dup",
                    "_source": "diamond_sft_v3",
                    "messages": _assistant_messages("---- MODULE A ----\n====\nSPECIFICATION Spec\n"),
                }
            ],
            "processed_eval": [],
            "diamond_eval_holdout": [],
            "ralph_train": [],
            "ralph_dev": [],
        },
        generated_at="2026-06-28T00:00:00+00:00",
        dedupe=False,
    )

    assert [row["_module"] for row in rows] == ["A", "A"]
    assert rows[0]["_ai4fm_public_corpora"] == ["processed_train"]
    assert rows[1]["_ai4fm_public_corpora"] == ["diamond_sft_v3"]
    assert summary["raw_rows"] == 2
    assert summary["kept_rows"] == 2
    assert summary["duplicate_rows_collapsed"] == 0
    assert summary["dedupe_exact_final_spec"] is False


def test_build_import_can_include_additional_public_jsonl_surface() -> None:
    rows, summary = build_import(
        {
            "processed_train": [],
            "diamond_sft_v3": [],
            "processed_eval": [],
            "diamond_eval_holdout": [],
            "ralph_train": [],
            "ralph_dev": [],
            "toy_train": [
                {
                    "_toy": True,
                    "messages": _assistant_messages("---- MODULE ToyTrain ----\n====\nSPECIFICATION Spec\n"),
                }
            ],
            "diamond_gen_communication_protocols": [
                {
                    "module": "AltBit",
                    "tier": "gold",
                    "topic_desc": "Alternating bit protocol.",
                    "spec": "---- MODULE AltBit ----\nTypeOK == TRUE\n====\n",
                    "is_diamond": True,
                    "mutation_caught": True,
                    "trivial_invariant": False,
                    "distinct_states": 8,
                    "invariants_checked": 2,
                }
            ],
        },
        generated_at="2026-06-28T00:00:00+00:00",
        include_additional_public_jsonl=True,
    )

    assert [row["_module"] for row in rows] == ["ToyTrain", "AltBit"]
    assert rows[0]["_ai4fm_public_corpora"] == ["toy_train"]
    assert rows[1]["_ai4fm_public_corpora"] == ["diamond_gen_communication_protocols"]
    assert summary["raw_rows"] == 2
    assert summary["kept_rows"] == 2
    assert summary["per_corpus"]["toy_train"]["kept_rows"] == 1
    assert summary["per_corpus"]["diamond_gen_communication_protocols"]["kept_rows"] == 1


def test_write_outputs_accepts_out_of_repo_target(tmp_path: Path) -> None:
    rows = [{"messages": [{"role": "developer", "content": "dev"}, {"role": "user", "content": "u"}, {"role": "assistant", "channel": "final", "content": "---- MODULE A ----\n====\n"}]}]
    summary = {
        "schema": "chattla_ai4fm_public_tlaprove_import_v1",
        "generated_at": "2026-06-28T00:00:00+00:00",
        "repo": {"nameWithOwner": "LUC-AI4FM/TLA-Prove"},
        "raw_rows": 1,
        "kept_rows": 1,
        "duplicate_rows_collapsed": 0,
        "dedupe_exact_final_spec": False,
        "per_corpus": {},
    }

    out = tmp_path / "ai4fm_public_tlaprove_import_raw_v1.jsonl"
    final_summary = write_outputs(rows, summary, out)

    assert final_summary["out"] == str(out)
    assert final_summary["summary"] == str(out.with_suffix(".summary.json"))
