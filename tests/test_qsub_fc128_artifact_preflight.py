from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ARTIFACT_PBS = REPO / "scripts" / "qsub_sophia_fc128_artifact_preflight.pbs"
BEST_PBS = REPO / "scripts" / "qsub_sophia_fc128_best_artifact_preflight.pbs"


def test_fc128_artifact_preflight_handles_blocked_publish_dry_run_without_shell_abort() -> None:
    text = ARTIFACT_PBS.read_text(encoding="utf-8")

    assert 'echo "===== Publish dry-run ====="' in text
    assert 'set +e' in text
    assert 'PUBLISH_RC=$?' in text
    assert 'publish dry-run reported blockers' in text
    assert '===== artifact preflight done =====' in text


def test_fc128_best_artifact_preflight_handles_blocked_publish_dry_run_without_shell_abort() -> None:
    text = BEST_PBS.read_text(encoding="utf-8")

    assert 'echo "===== Publish dry-run ====="' in text
    assert 'set +e' in text
    assert 'PUBLISH_RC=$?' in text
    assert 'publish dry-run reported blockers' in text
    assert '===== best artifact preflight done =====' in text
