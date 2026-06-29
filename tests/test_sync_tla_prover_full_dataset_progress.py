import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sync_tla_prover_full_dataset_progress.py"


def test_sync_full_dataset_progress_writes_manifest(tmp_path: Path) -> None:
    first = tmp_path / "First.tla"
    second = tmp_path / "Second.tla"
    third = tmp_path / "Third.tla"
    for path, name in [(first, "First"), (second, "Second"), (third, "Third")]:
        path.write_text(f"---- MODULE {name} ----\n====\n", encoding="utf-8")

    module_list = tmp_path / "modules.txt"
    module_list.write_text("\n".join(str(p) for p in [first, second, third]) + "\n", encoding="utf-8")

    jsonl = tmp_path / "full_dataset_smoke_170004.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps({"module": "First", "module_path": str(first), "status": "skipped"}),
                json.dumps({"module": "Second", "module_path": str(second), "status": "tlaps_partial"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "progress.json"

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            str(jsonl),
            "--job-id",
            "170004.sophia-pbs-01",
            "--module-list",
            str(module_list),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["job_id"] == "170004.sophia-pbs-01"
    assert payload["rows_so_far"] == 2
    assert payload["modules_seen"] == 2
    assert payload["statuses"] == {
        "skipped": 1,
        "tlaps_partial": 1,
    }
    assert payload["last_completed_module_path"] == str(second)
    assert payload["last_completed_status"] == "tlaps_partial"
    assert payload["next_module_path"] == str(third)
    assert payload["source"] == str(jsonl)


def test_sync_full_dataset_progress_sanitizes_repo_relative_paths(tmp_path: Path) -> None:
    repo_like = tmp_path / "repo"
    first = repo_like / "specs" / "First.tla"
    second = repo_like / "specs" / "Second.tla"
    third = repo_like / "specs" / "Third.tla"
    for path, name in [(first, "First"), (second, "Second"), (third, "Third")]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---- MODULE {name} ----\n====\n", encoding="utf-8")

    module_list = repo_like / "modules.txt"
    module_list.write_text(
        "\n".join(path.relative_to(repo_like).as_posix() for path in [first, second, third]) + "\n",
        encoding="utf-8",
    )

    jsonl = repo_like / "outputs" / "autoprover" / "full_dataset_smoke_170004.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    jsonl.write_text(
        "\n".join(
            [
                json.dumps({"module": "First", "module_path": str(first), "status": "skipped"}),
                json.dumps({"module": "Second", "module_path": str(second), "status": "tlaps_partial"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = repo_like / "progress.json"

    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--repo",
            str(repo_like),
            str(jsonl.relative_to(repo_like)),
            "--job-id",
            "170004.sophia-pbs-01",
            "--module-list",
            str(module_list.relative_to(repo_like)),
            "--out",
            str(out.relative_to(repo_like)),
        ],
        cwd=repo_like,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["last_completed_module_path"] == "specs/Second.tla"
    assert payload["next_module_path"] == "specs/Third.tla"
    assert payload["source"] == "outputs/autoprover/full_dataset_smoke_170004.jsonl"
