import json
import subprocess
import sys
from pathlib import Path

from scripts.build_tla_prover_full_dataset_validated_repair_pairs import build_pairs


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build_tla_prover_full_dataset_validated_repair_pairs.py"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


class _Semantic:
    def __init__(self, partial_credit: float) -> None:
        self.partial_credit = partial_credit


class _Validation:
    def __init__(self, tier: str, partial_credit: float) -> None:
        self.tier = tier
        self.semantic = _Semantic(partial_credit)


def test_build_pairs_keeps_only_gold_improving_non_harness_rows(tmp_path: Path) -> None:
    evidence = tmp_path / "repair_evidence.jsonl"
    _write_jsonl(
        evidence,
        [
            {
                "module": "AtomicRegister",
                "module_path": "broken/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an atomic register spec.",
                "broken_spec": "---- MODULE AtomicRegister ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE AtomicRegister ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "TLAPS partial proof: 3/10 obligations failed.",
                "verify_summary": "status=tlaps_partial bucket=proof_repair priority=p1 obligations_failed=3 obligations_total=10",
                "before_score": 0.7,
                "gold_source_kind": "diamond_eval_holdout",
                "prompt_source_kind": "diamond_eval_holdout",
            },
            {
                "module": "SyncTerminationDetection",
                "module_path": "broken/SyncTerminationDetection.tla",
                "repair_bucket": "tlc_repair",
                "repair_priority": "p3",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write a synchronous termination detection spec.",
                "broken_spec": "---- MODULE SyncTerminationDetection ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE SyncTerminationDetection ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "tlc_error_no_conclusive_result",
                "verify_summary": "status=tlc_error bucket=tlc_repair priority=p3",
                "before_score": 0.15,
                "gold_source_kind": "formalllm_public_module",
                "prompt_source_kind": "formalllm_eval",
            },
            {
                "module": "AlternatingBit",
                "module_path": "broken/AlternatingBit.tla",
                "repair_bucket": "skip_harness_repair",
                "repair_priority": "p4",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an alternating bit protocol spec.",
                "broken_spec": "---- MODULE AlternatingBit ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE AlternatingBit ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "skip_missing_variable_domain",
                "verify_summary": "status=skipped bucket=skip_harness_repair priority=p4",
                "before_score": 0.05,
                "gold_source_kind": "public_seed_candidate",
                "prompt_source_kind": "formalllm_eval",
            },
            {
                "module": "NoEvidence",
                "module_path": "broken/NoEvidence.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": False,
                "evidence_status": "no_evidence",
                "nl": None,
                "broken_spec": "---- MODULE NoEvidence ----\nVARIABLES x\n====\n",
                "repaired_spec": None,
                "errors_rendered": "none",
                "verify_summary": "status=tlaps_partial bucket=proof_repair priority=p1",
                "before_score": 0.1,
                "gold_source_kind": None,
                "prompt_source_kind": None,
            },
        ],
    )

    def fake_validate(spec: str, *, module_name: str, timeout: int) -> _Validation:
        del timeout
        if module_name == "AtomicRegister":
            return _Validation("gold", 1.0)
        if module_name == "SyncTerminationDetection":
            return _Validation("silver", 0.82)
        if module_name == "AlternatingBit":
            return _Validation("gold", 1.0)
        raise AssertionError(f"unexpected module {module_name}: {spec[:40]}")

    rows, summary = build_pairs(
        evidence_path=evidence,
        validate_spec=fake_validate,
    )

    assert [row["module"] for row in rows] == ["AtomicRegister"]
    row = rows[0]
    assert row["repair_id"].startswith("full_dataset::AtomicRegister::proof_repair::")
    assert row["before_score"] == 0.7
    assert row["after_score"] == 1.0
    assert row["validated_tier"] == "gold"
    assert row["gold_source_kind"] == "diamond_eval_holdout"

    assert summary["candidate_rows"] == 3
    assert summary["rows"] == 1
    assert summary["validated_tier_counts"] == {"gold": 1, "silver": 1}
    assert summary["excluded_counts"] == {
        "excluded_not_pair_ready": 1,
        "excluded_skip_harness_repair": 1,
        "excluded_tier:silver": 1,
    }
    assert summary["kept_by_bucket"] == {"proof_repair": 1}


def test_build_pairs_can_include_harness_and_non_gold_tiers(tmp_path: Path) -> None:
    evidence = tmp_path / "repair_evidence.jsonl"
    _write_jsonl(
        evidence,
        [
            {
                "module": "AlternatingBit",
                "module_path": "broken/AlternatingBit.tla",
                "repair_bucket": "skip_harness_repair",
                "repair_priority": "p4",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an alternating bit protocol spec.",
                "broken_spec": "---- MODULE AlternatingBit ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE AlternatingBit ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "skip_missing_variable_domain",
                "verify_summary": "status=skipped bucket=skip_harness_repair priority=p4",
                "before_score": 0.05,
                "gold_source_kind": "public_seed_candidate",
                "prompt_source_kind": "formalllm_eval",
            }
        ],
    )

    rows, summary = build_pairs(
        evidence_path=evidence,
        validate_spec=lambda spec, *, module_name, timeout: _Validation("silver", 0.9),
        allowed_tiers=("gold", "silver"),
        include_harness=True,
    )

    assert len(rows) == 1
    assert rows[0]["module"] == "AlternatingBit"
    assert rows[0]["validated_tier"] == "silver"
    assert summary["rows"] == 1
    assert summary["kept_by_bucket"] == {"skip_harness_repair": 1}


def test_build_pairs_omits_empty_only_buckets_from_summary(tmp_path: Path) -> None:
    evidence = tmp_path / "repair_evidence.jsonl"
    _write_jsonl(
        evidence,
        [
            {
                "module": "AtomicRegister",
                "module_path": "broken/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an atomic register spec.",
                "broken_spec": "---- MODULE AtomicRegister ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE AtomicRegister ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "TLAPS partial proof.",
                "verify_summary": "status=tlaps_partial bucket=proof_repair priority=p1",
                "before_score": 0.7,
                "gold_source_kind": "diamond_eval_holdout",
                "prompt_source_kind": "diamond_eval_holdout",
            }
        ],
    )

    _rows, summary = build_pairs(
        evidence_path=evidence,
        validate_spec=lambda spec, *, module_name, timeout: _Validation("gold", 1.0),
        allowed_tiers=("gold",),
    )

    assert "only_buckets" not in summary


def test_build_pairs_can_filter_to_specific_bucket(tmp_path: Path) -> None:
    evidence = tmp_path / "repair_evidence.jsonl"
    _write_jsonl(
        evidence,
        [
            {
                "module": "AtomicRegister",
                "module_path": "broken/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an atomic register spec.",
                "broken_spec": "---- MODULE AtomicRegister ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE AtomicRegister ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "TLAPS partial proof.",
                "verify_summary": "status=tlaps_partial bucket=proof_repair priority=p1",
                "before_score": 0.7,
                "gold_source_kind": "diamond_eval_holdout",
                "prompt_source_kind": "diamond_eval_holdout",
            },
            {
                "module": "AlternatingBit",
                "module_path": "broken/AlternatingBit.tla",
                "repair_bucket": "skip_harness_repair",
                "repair_priority": "p4",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an alternating bit protocol spec.",
                "broken_spec": "---- MODULE AlternatingBit ----\nVARIABLES x\n====\n",
                "repaired_spec": "---- MODULE AlternatingBit ----\nEXTENDS Naturals\n====\n",
                "errors_rendered": "skip_missing_variable_domain",
                "verify_summary": "status=skipped bucket=skip_harness_repair priority=p4",
                "before_score": 0.05,
                "gold_source_kind": "diamond_eval_holdout",
                "prompt_source_kind": "diamond_eval_holdout",
            },
        ],
    )

    rows, summary = build_pairs(
        evidence_path=evidence,
        validate_spec=lambda spec, *, module_name, timeout: _Validation("gold", 1.0),
        allowed_tiers=("gold",),
        include_harness=True,
        only_buckets=("skip_harness_repair",),
    )

    assert [row["module"] for row in rows] == ["AlternatingBit"]
    assert summary["candidate_rows"] == 1
    assert summary["rows"] == 1
    assert summary["kept_by_bucket"] == {"skip_harness_repair": 1}
    assert summary["only_buckets"] == ["skip_harness_repair"]


def test_cli_writes_validated_repair_pairs(tmp_path: Path) -> None:
    evidence = tmp_path / "repair_evidence.jsonl"
    _write_jsonl(
        evidence,
        [
            {
                "module": "AtomicRegister",
                "module_path": "broken/AtomicRegister.tla",
                "repair_bucket": "proof_repair",
                "repair_priority": "p1",
                "pair_ready": True,
                "evidence_status": "pair_ready",
                "nl": "Write an atomic register spec.",
                "broken_spec": "---- MODULE AtomicRegister ----\nVARIABLES x\n====\n",
                "repaired_spec": (
                    "---- MODULE AtomicRegister ----\n"
                    "EXTENDS Naturals\n"
                    "VARIABLE x\n"
                    "Init == x = 0\n"
                    "Next == x' = x\n"
                    "Spec == Init /\\ [][Next]_<<x>>\n"
                    "TypeOK == x \\in {0}\n"
                    "====\n"
                    "SPECIFICATION Spec\n"
                    "INVARIANT TypeOK\n"
                ),
                "errors_rendered": "TLAPS partial proof: 3/10 obligations failed.",
                "verify_summary": "status=tlaps_partial bucket=proof_repair priority=p1 obligations_failed=3 obligations_total=10",
                "before_score": 0.2,
                "gold_source_kind": "diamond_eval_holdout",
                "prompt_source_kind": "diamond_eval_holdout",
            }
        ],
    )
    out = tmp_path / "validated_pairs.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
                "--evidence",
                str(evidence),
                "--out",
                str(out),
                "--allowed-tier",
                "gold",
            ],
            check=True,
            capture_output=True,
            text=True,
        cwd=tmp_path,
    )

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["module"] == "AtomicRegister"
    summary = json.loads(out.with_suffix(".summary.json").read_text(encoding="utf-8"))
    assert summary["rows"] == 1
    stdout = json.loads(result.stdout)
    assert stdout["summary"]["rows"] == 1
