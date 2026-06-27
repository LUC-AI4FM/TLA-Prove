import json
from pathlib import Path

from scripts.build_tla_prover_eval_corpus import build_rows, split_final_theorem


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_split_final_theorem_keeps_prior_lemmas_in_preamble() -> None:
    proof_module = """---- MODULE Sample ----
EXTENDS TLAPS, Naturals

LEMMA Helper == 1 = 1
PROOF
<1> QED
  OBVIOUS

THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK
PROOF
<1>1. Init => TypeOK
  BY DEF Init, TypeOK
<1> QED
  BY <1>1, PTL DEF Spec
====
"""

    split = split_final_theorem(proof_module)

    assert "LEMMA Helper" in split.preamble
    assert split.statement == "THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK"
    assert split.proof.startswith("PROOF\n<1>1.")
    assert "====" not in split.proof


def test_build_rows_emits_tlaps_callback_compatible_eval_rows(tmp_path: Path) -> None:
    source = tmp_path / "traces.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "Sample",
                "verified": True,
                "proof_module": """---- MODULE Sample ----
EXTENDS TLAPS, Naturals
Init == TRUE
Next == TRUE
Spec == Init /\\ [][Next]_<<>>
TypeOK == TRUE

THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK
PROOF
<1>1. Init => TypeOK
  BY DEF Init, TypeOK
<1> QED
  BY <1>1, PTL DEF Spec
====
""",
                "target_theorem": "ChatTLA_TypeOKSafety == Spec => []TypeOK",
                "source": {"raw_log": "outputs/raw/Sample.log"},
                "tlaps": {"proved": 2, "total": 2, "failed": 0, "exit_code": 0},
            }
        ],
    )

    rows, summary = build_rows(source)

    assert summary["source_rows"] == 1
    assert summary["kept_rows"] == 1
    assert summary["skipped_unverified"] == 0
    row = rows[0]
    assert row["_tier"] == "verified_tlaps_eval"
    assert row["_module"] == "Sample"
    assert row["_obligations_proved"] == 2
    assert row["_obligations_total"] == 2
    assert "TLAPS proof" in row["messages"][1]["content"]
    assert "```tla" in row["messages"][1]["content"]
    assert row["messages"][2]["channel"] == "final"
    assert row["messages"][2]["content"].startswith("PROOF\n<1>1.")


def test_checked_in_prover_eval_matches_builder_output() -> None:
    repo = Path(__file__).resolve().parents[1]
    out = repo / "data/processed/prover_eval.jsonl"
    rows, _summary = build_rows(repo / "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl")

    assert out.exists()
    checked_in = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert checked_in == rows
    assert len(checked_in) == 18
