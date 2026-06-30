import json
from pathlib import Path

from scripts.replay_tla_prover_full_dataset_subset import replay_subset


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_replay_subset_replaces_selected_rows(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "full_dataset_smoke.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "ReplayA",
                "module_path": "specs/ReplayA.tla",
                "status": "skipped",
                "reason": "typeok_uses_unbounded_seq",
            },
            {
                "module": "KeepB",
                "module_path": "specs/KeepB.tla",
                "status": "tlaps_partial",
            },
        ],
    )

    def fake_run_one(path: Path, *, tlc_timeout: int, tlapm_timeout: int, run_tlaps: bool) -> dict:
        assert path == tmp_path / "specs" / "ReplayA.tla"
        assert tlc_timeout == 45
        assert tlapm_timeout == 60
        assert run_tlaps is False
        return {
            "module": "ReplayA",
            "module_path": "specs/ReplayA.tla",
            "status": "no_tlapm",
            "target": "Spec => []TypeOK",
        }

    monkeypatch.setattr(
        "scripts.replay_tla_prover_full_dataset_subset.run_one",
        fake_run_one,
    )
    monkeypatch.setattr("scripts.replay_tla_prover_full_dataset_subset.REPO", tmp_path)

    merged_rows, replay_rows, report = replay_subset(
        source_jsonl=source,
        module_paths=["specs/ReplayA.tla"],
        tlc_timeout=45,
        tlapm_timeout=60,
        run_tlaps=False,
    )

    assert [row["status"] for row in merged_rows] == ["no_tlapm", "tlaps_partial"]
    assert replay_rows[0]["replay_source_status"] == "skipped"
    assert replay_rows[0]["replay_source_reason"] == "typeok_uses_unbounded_seq"
    assert report["replayed_rows"] == 1
    assert report["replay_statuses"] == {"no_tlapm": 1}


def test_replay_subset_sanitizes_carried_forward_source_rows(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "full_dataset_smoke.jsonl"
    _write_jsonl(
        source,
        [
            {
                "module": "ReplayA",
                "module_path": "specs/ReplayA.tla",
                "status": "skipped",
                "reason": "typeok_uses_unbounded_seq",
            },
            {
                "module": "KeepB",
                "module_path": "specs/KeepB.tla",
                "status": "tlaps_partial",
                "tlapm": {
                    "path": "/workspace/tools/tlaps/bin/tlapm",
                    "raw_tail": 'File "/var/tmp/pbs.161031.cluster.example.invalid/tmp/KeepB.tla"',
                },
            },
        ],
    )

    def fake_run_one(path: Path, *, tlc_timeout: int, tlapm_timeout: int, run_tlaps: bool) -> dict:
        return {
            "module": "ReplayA",
            "module_path": "specs/ReplayA.tla",
            "status": "no_tlapm",
            "target": "Spec => []TypeOK",
        }

    monkeypatch.setattr("scripts.replay_tla_prover_full_dataset_subset.run_one", fake_run_one)
    monkeypatch.setattr("scripts.replay_tla_prover_full_dataset_subset.REPO", tmp_path)

    merged_rows, _replay_rows, report = replay_subset(
        source_jsonl=source,
        module_paths=["specs/ReplayA.tla"],
        tlc_timeout=45,
        tlapm_timeout=60,
        run_tlaps=False,
    )

    keep_row = merged_rows[1]
    assert keep_row["tlapm"]["path"] == "<ABS_PATH>"
    assert "/var/tmp/pbs" not in keep_row["tlapm"]["raw_tail"]
    assert keep_row["tlapm"]["raw_tail"] == 'File "<ABS_PATH>"'
    assert report["source_jsonl"] == "full_dataset_smoke.jsonl"
