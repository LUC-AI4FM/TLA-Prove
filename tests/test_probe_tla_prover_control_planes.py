import json
import subprocess
from pathlib import Path

from scripts.probe_tla_prover_control_planes import Candidate, probe_candidates


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "probe_tla_prover_control_planes.py"


def test_probe_candidates_records_reachable_and_unreachable_hosts() -> None:
    def fake_runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        host = cmd[-2]
        if host == "good-host":
            return subprocess.CompletedProcess(cmd, 0, "remote-host\n", "")
        return subprocess.CompletedProcess(cmd, 255, "", "Permission denied\n")

    payload = probe_candidates(
        [
            Candidate(name="good", host="good-host", command="hostname"),
            Candidate(name="bad", host="bad-host", command="hostname"),
        ],
        runner=fake_runner,
    )

    assert payload["ok"] is True
    assert payload["candidates"][0]["reachable"] is True
    assert payload["candidates"][1]["reachable"] is False
    assert payload["best_candidate"]["name"] == "good"


def test_probe_cli_writes_json_report(tmp_path: Path) -> None:
    out = tmp_path / "probe.json"

    subprocess.run(
        ["python3", str(SCRIPT), "--candidate", "local:true:true", "--out", str(out)],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["best_candidate"]["name"] == "local"
