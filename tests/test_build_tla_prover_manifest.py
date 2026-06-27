import json
from pathlib import Path

from scripts.build_tla_prover_manifest import build_manifest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_manifest_summarizes_present_artifacts(tmp_path: Path) -> None:
    repo = tmp_path
    _write_jsonl(repo / "data/processed/sany_tlc_pass_sft_v1.jsonl", [{"a": 1}, {"a": 2}])
    _write_jsonl(repo / "data/processed/prover_eval.jsonl", [{"messages": []}])
    _write_jsonl(repo / "data/processed/sany_tlc_pass_eval_v1.jsonl", [{"messages": []}, {"messages": []}])
    (repo / "data/processed/sany_tlc_pass_sft_v1.summary.json").write_text(
        json.dumps({"kept_rows": 2}),
        encoding="utf-8",
    )
    (repo / "outputs/manifests").mkdir(parents=True, exist_ok=True)
    (repo / "outputs/manifests/sany_tlc_pass_corpus_diagnostic.json").write_text(
        json.dumps({"ok": True, "rows": 2}),
        encoding="utf-8",
    )
    _write_jsonl(repo / "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.jsonl", [{"b": 1}])
    (repo / "data/processed/tla_prover/tlaps_verified_autoprover_traces_v1.summary.json").write_text(
        json.dumps({"raw_proved": 3, "raw_total": 3}),
        encoding="utf-8",
    )

    manifest = build_manifest(repo)

    assert manifest["schema"] == "chattla_tla_prover_artifacts_v1"
    assert manifest["artifacts"]["sany_tlc_pass_sft_v1"]["rows"] == 2
    assert manifest["artifacts"]["prover_eval_v1"]["rows"] == 1
    assert manifest["artifacts"]["prover_eval_v1"]["kind"] == "verified_tlaps_prover_eval_dataset"
    assert manifest["artifacts"]["sany_tlc_pass_eval_v1"]["rows"] == 2
    assert manifest["artifacts"]["sany_tlc_pass_eval_v1"]["kind"] == "heldout_sany_tlc_pass_eval_dataset"
    assert manifest["artifacts"]["sany_tlc_pass_corpus_diagnostic"]["exists"] is True
    assert manifest["artifacts"]["sany_tlc_pass_corpus_diagnostic"]["kind"] == (
        "sany_tlc_pass_corpus_quality_gate"
    )
    assert manifest["artifacts"]["tlaps_verified_autoprover_traces_v1"]["rows"] == 1
    assert manifest["artifacts"]["tlaps_verified_autoprover_traces_v1"]["summary"]["raw_total"] == 3
    assert manifest["remote_next_steps"]["known18_pbs"] == "scripts/qsub_autoprover_known18_corrected_smoke.pbs"
    assert manifest["remote_next_steps"]["evaluate_remote_results"] == "python3 scripts/evaluate_tla_prover_remote_results.py"
    assert manifest["remote_next_steps"]["remote_decision_report"] == "outputs/manifests/tla_prover_remote_decision.json"
    assert manifest["remote_next_steps"]["install_laptop_handoff_doctor_launchagent"] == (
        "scripts/install_handoff_doctor_launchagent.sh --interval 300"
    )
    assert manifest["remote_next_steps"]["retry_submission_report_mirror"] == (
        "scripts/wait_for_macmini_and_handoff_known18.sh --mirror-report-only"
    )
    assert manifest["remote_next_steps"]["macmini_known18_plus_launchagents_handoff"] == (
        "scripts/sync_macmini_and_submit_known18.sh --install-launchagents"
    )
    assert manifest["remote_next_steps"]["probe_control_planes"] == "python3 scripts/probe_tla_prover_control_planes.py"
    assert manifest["remote_next_steps"]["diagnose_sany_tlc_pass_corpus"] == (
        "python3 scripts/diagnose_sany_tlc_pass_corpus.py"
    )
    assert manifest["remote_next_steps"]["handoff_status_compact"] == (
        "python3 scripts/status_tla_prover_handoff.py --no-live --compact"
    )
    assert manifest["remote_next_steps"]["handoff_doctor_compact"] == (
        "python3 scripts/doctor_tla_prover_handoff.py --dry-run --no-live --compact"
    )
    assert manifest["remote_next_steps"]["pr_ready_check"] == "python3 scripts/check_tla_prover_pr_ready.py"
    assert manifest["remote_next_steps"]["build_tla_prover_eval_corpus"] == (
        "python3 scripts/build_tla_prover_eval_corpus.py"
    )
    assert manifest["remote_next_steps"]["build_sany_tlc_eval_corpus"] == (
        "python3 scripts/build_sany_tlc_eval_corpus.py"
    )
