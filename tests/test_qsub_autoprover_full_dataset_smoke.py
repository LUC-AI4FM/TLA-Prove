from pathlib import Path


PBS = Path(__file__).resolve().parents[1] / "scripts" / "qsub_autoprover_full_dataset_smoke.pbs"


def test_full_dataset_smoke_qsub_writes_job_specific_log_and_summary() -> None:
    text = PBS.read_text(encoding="utf-8")

    assert "#PBS -N tla_full_smoke" in text
    assert "#PBS -V" in text
    assert "autoprover_full_dataset_smoke_pbs.log" in text
    assert 'JOBLOG="outputs/logs/autoprover_full_dataset_smoke_${PBS_JOBID}.log"' in text
    assert 'exec > >(tee "$JOBLOG") 2>&1' in text
    assert 'OUT="outputs/autoprover/full_dataset_smoke_${JOBNUM}.jsonl"' in text
    assert 'SUMMARY="${OUT%.jsonl}.summary.json"' in text
    assert "python3 -u scripts/autoprover_smoke.py" in text
    assert '--progress-out "outputs/manifests/tla_prover_full_dataset_progress.json"' in text
    assert '--progress-job-id "$PBS_JOBID"' in text
    assert '"statuses": dict(sorted(statuses.items()))' in text
