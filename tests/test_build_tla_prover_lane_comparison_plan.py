import json
import subprocess
from pathlib import Path

from scripts.build_tla_prover_lane_comparison_plan import build_plan


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_plan_for_local_comparison_reuses_named_lane_plans(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl")
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        (
            '{"lanes":{'
            '"default":{"rows":1330,"default_publish_lane":true,"intended_role":"current_publish_baseline","trainable":true},'
            '"expanded":{"rows":2503,"default_publish_lane":false,"intended_role":"bounded_public_comparison_train","trainable":true}'
            '}}\n'
        ),
    )

    plan = build_plan(
        repo=tmp_path,
        baseline="default",
        candidate="expanded",
        mode="local",
        extra_args=["--smoke-test"],
    )

    assert plan["mode"] == "local"
    assert plan["comparison_id"] == "default-vs-expanded-local"
    assert plan["row_delta"] == 1173
    assert plan["baseline"]["resolved_corpus"]["alias"] == "default"
    assert plan["candidate"]["resolved_corpus"]["alias"] == "expanded"
    assert plan["baseline"]["command"][:6] == [
        "python3",
        "-m",
        "src.training.train",
        "--prover",
        "--sft-corpus",
        "default",
    ]
    assert plan["candidate"]["command"][:6] == [
        "python3",
        "-m",
        "src.training.train",
        "--prover",
        "--sft-corpus",
        "expanded",
    ]
    assert plan["baseline"]["command"][-1] == "--smoke-test"
    assert plan["candidate"]["command"][-1] == "--smoke-test"
    assert plan["follow_up"]["status_command"] == "python3 scripts/choose_tla_prover_next_experiment.py"
    assert plan["post_train_eval"]["tool"] == "scripts/eval_fullspec_checkpoints.py"
    assert plan["post_train_eval"]["compare_tool"] == "scripts/compare_tla_prover_eval_results.py"
    assert plan["post_train_eval"]["baseline_out"] == (
        "outputs/eval/lane_comparison/default-vs-expanded-local/default_eval.json"
    )
    assert plan["post_train_eval"]["compare_out"] == (
        "outputs/eval/lane_comparison/default-vs-expanded-local/comparison.json"
    )
    assert "--adapter outputs/checkpoints_prover " in plan["post_train_eval"]["baseline_command"]
    assert "--adapter outputs/checkpoints_prover_expanded " in plan["post_train_eval"]["candidate_command"]
    assert "--label default " in plan["post_train_eval"]["baseline_command"]
    assert "--label expanded " in plan["post_train_eval"]["candidate_command"]
    assert plan["post_train_eval"]["compare_command"] == (
        "python3 scripts/compare_tla_prover_eval_results.py "
        "--baseline outputs/eval/lane_comparison/default-vs-expanded-local/default_eval.json "
        "--candidate outputs/eval/lane_comparison/default-vs-expanded-local/expanded_eval.json "
        "--out outputs/eval/lane_comparison/default-vs-expanded-local/comparison.json"
    )
    assert plan["post_train_eval"]["compare_note"] == (
        "Run both eval commands after training completes, then compare "
        "sany_pass, depth1_pass, tlc_pass, mean_reward, module_match, and syntax regressions."
    )


def test_build_plan_for_remote_comparison_emits_paired_handoff_commands(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl")
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_all_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        (
            '{"lanes":{'
            '"default":{"rows":1330,"default_publish_lane":true,"intended_role":"current_publish_baseline","trainable":true},'
            '"full-public":{"rows":2508,"default_publish_lane":false,"intended_role":"broadest_public_comparison_train","trainable":true}'
            '}}\n'
        ),
    )

    plan = build_plan(
        repo=tmp_path,
        baseline="default",
        candidate="full-public",
        mode="remote",
        extra_args=[],
    )

    assert plan["mode"] == "remote"
    assert plan["comparison_id"] == "default-vs-full-public-remote"
    assert plan["baseline"]["resolved_corpus"]["alias"] == "default"
    assert plan["candidate"]["resolved_corpus"]["alias"] == "full-public"
    assert plan["baseline"]["remote_command"] == (
        "scripts/sync_sophia_and_submit_known18.sh --sft-corpus default --submit-sft-preflight"
    )
    assert plan["candidate"]["remote_command"] == (
        "scripts/sync_sophia_and_submit_known18.sh --sft-corpus full-public --submit-sft-preflight"
    )
    assert plan["follow_up"]["watch_command"] == "scripts/watch_tla_prover_remote_results.sh"
    assert plan["follow_up"]["evaluate_command"] == "python3 scripts/evaluate_tla_prover_remote_results.py"
    assert plan["post_train_eval"] is None


def test_cli_can_write_lane_comparison_manifest(tmp_path: Path) -> None:
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_v1.jsonl")
    _write(tmp_path / "data/processed/tla_prover/chattla_tla_prover_sft_public_expanded_v1.jsonl")
    _write(
        tmp_path / "outputs/manifests/tla_prover_corpus_experiment_matrix.json",
        (
            '{"lanes":{'
            '"default":{"rows":1330,"default_publish_lane":true,"intended_role":"current_publish_baseline","trainable":true},'
            '"expanded":{"rows":2503,"default_publish_lane":false,"intended_role":"bounded_public_comparison_train","trainable":true}'
            '}}\n'
        ),
    )
    out = tmp_path / "outputs/manifests/tla_prover_lane_comparison_plan.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_tla_prover_lane_comparison_plan.py"

    subprocess.run(
        [
            "python3",
            str(script),
            "--repo",
            str(tmp_path),
            "--baseline",
            "default",
            "--candidate",
            "expanded",
            "--mode",
            "local",
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["comparison_id"] == "default-vs-expanded-local"
    assert payload["baseline"]["resolved_corpus"]["alias"] == "default"
    assert payload["candidate"]["resolved_corpus"]["alias"] == "expanded"
    assert str(tmp_path) not in json.dumps(payload)
