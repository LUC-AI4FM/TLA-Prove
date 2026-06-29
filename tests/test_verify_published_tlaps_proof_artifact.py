import json
import subprocess
import tarfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_published_tlaps_proof_artifact.py"


def test_verify_published_tlaps_proof_artifact_runs_on_synthetic_tarball(tmp_path: Path) -> None:
    artifact_root = tmp_path / "tlaps_reproduced_final_test"
    proofs_dir = artifact_root / "proofs"
    proofs_dir.mkdir(parents=True)
    (proofs_dir / "Example.tla").write_text("---- MODULE Example ----\nTHEOREM TRUE\n====\n", encoding="utf-8")

    tarball = tmp_path / "artifact.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(artifact_root, arcname=artifact_root.name)

    expected_summary = tmp_path / "expected_summary.json"
    expected_summary.write_text(
        json.dumps(
            {
                "modules": 1,
                "exit_0": 1,
                "exit_nonzero": 0,
                "raw_proved": 1,
                "raw_total": 1,
                "all_modules_exit_0": True,
                "all_modules_proved": True,
                "no_asterisk": True,
            }
        ),
        encoding="utf-8",
    )

    tlapm = tmp_path / "tlapm"
    tlapm.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'All 1 obligation proved\\n'\n",
        encoding="utf-8",
    )
    tlapm.chmod(0o755)

    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--tarball",
            str(tarball),
            "--expected-summary",
            str(expected_summary),
            "--out-dir",
            str(out_dir),
            "--tlapm",
            str(tlapm),
            "--expected-modules",
            "1",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert summary["modules"] == 1
    assert summary["raw_proved"] == 1
    assert summary["raw_total"] == 1
    assert summary["matches_expected_summary"] is True
    assert summary["results"][0]["path"] == "proofs/Example.tla"
    assert manifest["expected_matches"] is True
    assert manifest["tarball"] == str(tarball)
    assert manifest["tlapm"] == "tlapm"
