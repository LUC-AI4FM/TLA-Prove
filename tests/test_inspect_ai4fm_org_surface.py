import json
import subprocess
from pathlib import Path

from scripts.inspect_ai4fm_org_surface import build_report


def _repo(
    name: str,
    *,
    pushed_at: str = "2026-06-29T00:00:00Z",
    size: int = 1,
) -> dict[str, object]:
    return {
        "name": name,
        "full_name": f"LUC-AI4FM/{name}",
        "html_url": f"https://github.com/LUC-AI4FM/{name}",
        "default_branch": "main",
        "pushed_at": pushed_at,
        "size": size,
    }


def test_build_report_summarizes_public_org_surface() -> None:
    report = build_report(
        org="LUC-AI4FM",
        repo_payloads=[
            _repo("FormaLLM", size=15137),
            _repo("TLA-Prove", size=670220),
            _repo("tla-dataset-pipeline", size=176),
            _repo("FormaLLM-Reverse", size=14963),
            _repo("webpage", size=13755),
        ],
    )

    assert report["org"] == "LUC-AI4FM"
    assert report["public_repo_count"] == 5
    assert report["summary"]["corpus_relevant_repo_count"] == 3
    assert report["summary"]["corpus_relevant_repos"] == [
        "FormaLLM",
        "TLA-Prove",
        "tla-dataset-pipeline",
    ]
    roles = {repo["name"]: repo["role"] for repo in report["repos"]}
    assert roles["FormaLLM"] == "benchmark"
    assert roles["TLA-Prove"] == "public-corpora"
    assert roles["tla-dataset-pipeline"] == "pipeline"
    assert roles["FormaLLM-Reverse"] == "adjacent"
    assert roles["webpage"] == "adjacent"
    assert report["warnings"] == []


def test_build_report_warns_when_expected_core_repo_is_missing() -> None:
    report = build_report(
        org="LUC-AI4FM",
        repo_payloads=[
            _repo("FormaLLM"),
            _repo("tla-dataset-pipeline"),
        ],
    )

    assert report["public_repo_count"] == 2
    assert report["summary"]["corpus_relevant_repos"] == ["FormaLLM", "tla-dataset-pipeline"]
    assert report["warnings"] == [
        "Missing expected public AI4FM core repos: TLA-Prove."
    ]


def test_cli_can_read_repo_payloads_from_json(tmp_path: Path) -> None:
    payload = [
        _repo("FormaLLM"),
        _repo("TLA-Prove"),
        _repo("tla-dataset-pipeline"),
        _repo("paper-parse"),
    ]
    payload_path = tmp_path / "repos.json"
    out = tmp_path / "report.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspect_ai4fm_org_surface.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--org",
            "LUC-AI4FM",
            "--repos-json",
            str(payload_path),
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = json.loads(result.stdout)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert stdout["public_repo_count"] == 4
    assert stdout["summary"]["corpus_relevant_repo_count"] == 3
    assert saved == stdout
