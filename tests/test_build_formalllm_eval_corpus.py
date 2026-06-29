import hashlib
import json
from pathlib import Path

from scripts.build_formalllm_eval_corpus import build_rows


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_rows_prefers_clean_files_and_appends_cfg(tmp_path: Path) -> None:
    family = tmp_path / "FamilyA"
    _write(
        family / "FamilyA.json",
        json.dumps(
            {
                "data": [
                    {
                        "id": "0001",
                        "model": "Alpha",
                        "tla_original": "Alpha.tla",
                        "tla_clean": "Alpha_clean.tla",
                        "comments": "Alpha_comments.txt",
                        "comments_clean": "Alpha_comments_clean.txt",
                        "cfg": "Alpha.cfg",
                    }
                ]
            }
        ),
    )
    _write(family / "txt" / "Alpha_comments.txt", "original prompt")
    _write(family / "txt" / "Alpha_comments_clean.txt", "clean prompt")
    _write(family / "tla" / "Alpha.tla", "---- MODULE Alpha ----\nTypeOK == TRUE\n====\n")
    _write(family / "tla" / "Alpha_clean.tla", "---- MODULE Alpha ----\nEXTENDS Naturals\nTypeOK == TRUE\n====\n")
    _write(family / "cfg" / "Alpha.cfg", "SPECIFICATION Spec\nINVARIANT TypeOK\nCONSTANT N = 3\n")

    rows, summary = build_rows(tmp_path)

    assert summary["rows"] == 1
    assert summary["families_seen"] == 1
    row = rows[0]
    assert row["_tier"] == "formalllm_eval"
    assert row["_source"] == "formalllm_clean_v1"
    assert row["_family"] == "FamilyA"
    assert row["_module"] == "Alpha"
    assert row["_prompt_id"] == "formalllm/FamilyA/0001/Alpha"
    assert row["messages"][1]["content"].endswith("clean prompt\n")
    final = row["messages"][-1]["content"]
    assert "EXTENDS Naturals" in final
    assert "SPECIFICATION Spec" in final
    assert "CONSTANT N = 3" in final


def test_build_rows_falls_back_to_original_files(tmp_path: Path) -> None:
    family = tmp_path / "FamilyB"
    _write(
        family / "FamilyB.json",
        json.dumps(
            {
                "data": [
                    {
                        "id": "0002",
                        "model": "Beta",
                        "tla_original": "Beta.tla",
                        "tla_clean": "Beta_clean.tla",
                        "comments": "Beta_comments.txt",
                        "comments_clean": "Beta_comments_clean.txt",
                        "cfg": None,
                    }
                ]
            }
        ),
    )
    _write(family / "txt" / "Beta_comments.txt", "fallback prompt")
    _write(family / "tla" / "Beta.tla", "---- MODULE Beta ----\nTypeOK == TRUE\n====\n")
    (family / "cfg").mkdir(parents=True, exist_ok=True)

    rows, summary = build_rows(tmp_path)

    assert summary["rows"] == 1
    row = rows[0]
    assert row["messages"][1]["content"].endswith("fallback prompt\n")
    final = row["messages"][-1]["content"]
    assert "SPECIFICATION Spec" in final
    assert "INVARIANT TypeOK" in final


def test_build_rows_can_recover_prompt_from_family_alias_and_readme(tmp_path: Path) -> None:
    family = tmp_path / "GameFamily"
    _write(
        family / "GameFamily.json",
        json.dumps(
            {
                "data": [
                    {
                        "id": "0003",
                        "model": "MCWidget",
                        "tla_original": "MCWidget.tla",
                        "tla_clean": "MCWidget_clean.tla",
                        "comments": None,
                        "comments_clean": None,
                        "cfg": None,
                    },
                    {
                        "id": "0004",
                        "model": "GameFamily",
                        "tla_original": "GameFamily.tla",
                        "tla_clean": "GameFamily_clean.tla",
                        "comments": None,
                        "comments_clean": None,
                        "cfg": None,
                    },
                ]
            }
        ),
    )
    _write(family / "txt" / "Widget_comments_clean.txt", "widget prompt")
    _write(family / "README.md", "family readme prompt")
    _write(family / "tla" / "MCWidget_clean.tla", "---- MODULE MCWidget ----\n====\n")
    _write(family / "tla" / "GameFamily_clean.tla", "---- MODULE GameFamily ----\n====\n")

    rows, summary = build_rows(tmp_path)

    assert summary["rows"] == 2
    prompts = {row["_module"]: row["messages"][1]["content"] for row in rows}
    assert prompts["MCWidget"].endswith("widget prompt\n")
    assert prompts["GameFamily"].endswith("family readme prompt\n")


def test_checked_in_formalllm_eval_matches_builder_output() -> None:
    repo = Path(__file__).resolve().parents[1]
    out = repo / "data/processed/formalllm_eval_v1.jsonl"
    rows, summary = build_rows(repo / "data/FormaLLM/data")
    serialized = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    checked_summary = json.loads(out.with_suffix(".summary.json").read_text(encoding="utf-8"))

    assert out.read_text(encoding="utf-8") == serialized
    assert checked_summary["rows"] == summary["rows"] == len(rows) == 205
    assert checked_summary["jsonl_sha256"] == hashlib.sha256(serialized.encode("utf-8")).hexdigest()
