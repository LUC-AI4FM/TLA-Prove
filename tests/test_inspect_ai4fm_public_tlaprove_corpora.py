from scripts.inspect_ai4fm_public_tlaprove_corpora import build_report


def test_build_report_summarizes_public_tlaprove_corpora() -> None:
    processed_listing = [
        {
            "name": "train.jsonl",
            "path": "data/processed/train.jsonl",
            "sha": "a" * 40,
            "size": 3301469,
            "download_url": "https://example.com/train.jsonl",
            "html_url": "https://github.com/LUC-AI4FM/TLA-Prove/blob/main/data/processed/train.jsonl",
        },
        {
            "name": "eval.jsonl",
            "path": "data/processed/eval.jsonl",
            "sha": "b" * 40,
            "size": 31017,
            "download_url": "https://example.com/eval.jsonl",
            "html_url": "https://github.com/LUC-AI4FM/TLA-Prove/blob/main/data/processed/eval.jsonl",
        },
        {
            "name": "diamond_eval_holdout.jsonl",
            "path": "data/processed/diamond_eval_holdout.jsonl",
            "sha": "c" * 40,
            "size": 79917,
            "download_url": "https://example.com/diamond_eval_holdout.jsonl",
            "html_url": "https://github.com/LUC-AI4FM/TLA-Prove/blob/main/data/processed/diamond_eval_holdout.jsonl",
        },
        {
            "name": "diamond_sft_v3.jsonl",
            "path": "data/processed/diamond_sft_v3.jsonl",
            "sha": "d" * 40,
            "size": 4781486,
            "download_url": "https://example.com/diamond_sft_v3.jsonl",
            "html_url": "https://github.com/LUC-AI4FM/TLA-Prove/blob/main/data/processed/diamond_sft_v3.jsonl",
        },
    ]
    ralph_listing = [
        {
            "name": "train.jsonl",
            "path": "data/frs_tla_ralph_gen/train.jsonl",
            "sha": "e" * 40,
            "size": 1723511,
            "download_url": "https://example.com/ralph_train.jsonl",
            "html_url": "https://github.com/LUC-AI4FM/TLA-Prove/blob/main/data/frs_tla_ralph_gen/train.jsonl",
        },
        {
            "name": "dev.jsonl",
            "path": "data/frs_tla_ralph_gen/dev.jsonl",
            "sha": "f" * 40,
            "size": 152346,
            "download_url": "https://example.com/ralph_dev.jsonl",
            "html_url": "https://github.com/LUC-AI4FM/TLA-Prove/blob/main/data/frs_tla_ralph_gen/dev.jsonl",
        },
    ]
    row_counts = {
        "https://example.com/train.jsonl": 713,
        "https://example.com/eval.jsonl": 4,
        "https://example.com/diamond_eval_holdout.jsonl": 30,
        "https://example.com/diamond_sft_v3.jsonl": 1053,
        "https://example.com/ralph_train.jsonl": 500,
        "https://example.com/ralph_dev.jsonl": 50,
    }
    diamond_summary = {
        "base_kept": 713,
        "new_unique": 170,
        "oversample": 2,
        "total_records": 1053,
    }
    ralph_readme = "\n".join(
        [
            "- 168 pre-existing rows (tlaplus/examples, ChatTLA, FormaLLM) carried over",
            "- 476 new ralph-gen rows across 12 topics",
            "- Final splits: 500 train, 50 dev, stratified round-robin on (topic, difficulty)",
        ]
    )
    diamond_topics = {
        "_doc": "200 distinct TLA+ specification topics for parallel diamond generation.",
        "batches": [{"topics": [1, 2]}, {"topics": [3]}],
    }

    report = build_report(
        repo={"nameWithOwner": "LUC-AI4FM/TLA-Prove", "html_url": "https://github.com/LUC-AI4FM/TLA-Prove", "default_branch": "main", "head_sha": "z" * 40},
        processed_listing=processed_listing,
        ralph_listing=ralph_listing,
        row_counts=row_counts,
        diamond_summary=diamond_summary,
        ralph_readme=ralph_readme,
        diamond_topics=diamond_topics,
        diamond_topics_download_url="https://example.com/diamond_topics.json",
        ralph_readme_download_url="https://example.com/ralph_readme.md",
        generated_at="2026-06-28T12:00:00+00:00",
    )

    assert report["repo"]["head_sha"] == "z" * 40
    assert report["corpora"]["processed_train"]["rows"] == 713
    assert report["corpora"]["diamond_sft_v3"]["summary"]["new_unique"] == 170
    assert report["corpora"]["frs_tla_ralph_gen"]["readme_summary"]["new_rows"] == 476
    assert report["corpora"]["frs_tla_ralph_gen"]["train"]["rows"] == 500
    assert report["corpora"]["diamond_gen_topics"]["topics_total"] == 3
    assert report["aggregate"]["total_public_jsonl_rows"] == 2350
    assert report["recommended_ingest_order"][0]["path"] == "data/processed/diamond_sft_v3.jsonl"
