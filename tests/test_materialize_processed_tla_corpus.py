import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "materialize_processed_tla_corpus.py"


def test_materialize_processed_tla_corpus_filters_and_disambiguates_duplicates(tmp_path: Path) -> None:
    jsonl = tmp_path / "train.jsonl"
    rows = [
        {
            "_source": "tla_descriptions.json",
            "_tier": "description_sft",
            "_module_name": "Consensus",
            "messages": [
                {"role": "assistant", "channel": "final", "content": "---- MODULE Consensus ----\n====\n"}
            ],
        },
        {
            "_source": "tla_descriptions.json",
            "_tier": "description_sft",
            "_module_name": "Consensus",
            "messages": [
                {"role": "assistant", "channel": "final", "content": "---- MODULE Consensus ----\nEXTENDS Naturals\n====\n"}
            ],
        },
        {
            "_source": "diamond_gen/",
            "_tier": "diamond",
            "_module_name": "DiamondOnly",
            "messages": [
                {"role": "assistant", "channel": "final", "content": "---- MODULE DiamondOnly ----\n====\n"}
            ],
        },
    ]
    jsonl.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    out_dir = tmp_path / "out"
    summary = tmp_path / "summary.json"

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            str(jsonl),
            "--out-dir",
            str(out_dir),
            "--source",
            "tla_descriptions.json",
            "--summary-out",
            str(summary),
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["files_written"] == 2
    assert payload["unique_modules"] == 1
    assert payload["duplicates"] == {"Consensus": 2}
    assert payload["skipped"]["source_filtered"] == 1
    assert (out_dir / "Consensus.tla").exists()
    assert (out_dir / "Consensus__2.tla").exists()
    assert json.loads(summary.read_text())["files_written"] == 2


def test_materialize_processed_tla_corpus_can_filter_by_tier(tmp_path: Path) -> None:
    jsonl = tmp_path / "train.jsonl"
    rows = [
        {
            "_source": None,
            "_tier": "gold_cache",
            "_module_name": "Barrier",
            "messages": [
                {"role": "assistant", "channel": "final", "content": "---- MODULE Barrier ----\n====\n"}
            ],
        },
        {
            "_source": None,
            "_tier": "gold",
            "_module_name": "DiningPhilosophers",
            "messages": [
                {"role": "assistant", "channel": "final", "content": "---- MODULE DiningPhilosophers ----\n====\n"}
            ],
        },
    ]
    jsonl.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    out_dir = tmp_path / "out"

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            str(jsonl),
            "--out-dir",
            str(out_dir),
            "--tier",
            "gold_cache",
        ],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["files_written"] == 1
    assert payload["skipped"]["tier_filtered"] == 1
    assert (out_dir / "Barrier.tla").exists()
    assert not (out_dir / "DiningPhilosophers.tla").exists()
