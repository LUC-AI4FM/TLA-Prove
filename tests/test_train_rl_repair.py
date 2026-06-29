from scripts.train_rl_repair import (
    DEFAULT_BENCHMARK_REPAIR_PAIRS,
    DEFAULT_REPAIR_PAIRS,
    build_arg_parser,
    resolve_trajectory_files,
)


def test_resolve_trajectory_files_defaults_to_ralph_pairs() -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert resolve_trajectory_files(args) == [DEFAULT_REPAIR_PAIRS]


def test_resolve_trajectory_files_appends_benchmark_pairs() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        [
            "--trajectory-file",
            "custom_a.jsonl",
            "--trajectory-file",
            "custom_b.jsonl",
            "--include-benchmark-repair-pairs",
        ]
    )
    assert resolve_trajectory_files(args) == [
        "custom_a.jsonl",
        "custom_b.jsonl",
        DEFAULT_BENCHMARK_REPAIR_PAIRS,
    ]

