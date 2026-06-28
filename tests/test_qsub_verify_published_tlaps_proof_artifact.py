from pathlib import Path


PBS = Path(__file__).resolve().parents[1] / "scripts" / "qsub_verify_published_tlaps_proof_artifact.pbs"


def test_verify_published_qsub_writes_job_specific_log_and_stages_outputs() -> None:
    text = PBS.read_text(encoding="utf-8")

    assert "#PBS -N tlaps_verify_pub" in text
    assert "tlaps_verify_published_pbs.log" in text
    assert 'JOBLOG="outputs/logs/tlaps_verify_published_${PBS_JOBID}.log"' in text
    assert 'exec > >(tee "$JOBLOG") 2>&1' in text
    assert "scripts/verify_published_tlaps_proof_artifact.py" in text
    assert "outputs/autoprover/tlaps_verify_published_${JOBNUM}" in text
    assert "summary.json" in text
    assert "manifest.json" in text
    assert "SHA256SUMS" in text
