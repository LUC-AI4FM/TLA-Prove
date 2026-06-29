import json
import subprocess
from pathlib import Path

from scripts.inspect_ai4fm_public_dataset_surface import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_report_summarizes_formalllm_and_pipeline_surface(tmp_path: Path) -> None:
    formalllm_repo = tmp_path / "FormaLLM"
    formalllm = formalllm_repo / "data"
    family = formalllm / "FamilyOne"
    _write(
        family / "FamilyOne.json",
        json.dumps(
            {
                "data": [
                    {
                        "id": "0001",
                        "model": "Alpha",
                        "tla_original": "Alpha.tla",
                        "tla_clean": "Alpha_clean.tla",
                        "comments": "Alpha_comments.txt",
                        "comments_clean": "Alpha_comments_clean.txt",
                        "cfg": None,
                    },
                    {
                        "id": "0002",
                        "model": "MCAlpha",
                        "tla_original": "MCAlpha.tla",
                        "tla_clean": "MCAlpha_clean.tla",
                        "comments": None,
                        "comments_clean": None,
                        "cfg": "MCAlpha.cfg",
                    },
                ]
            }
        ),
    )
    _write(family / "tla" / "Alpha.tla", "---- MODULE Alpha ----\n====\n")
    _write(family / "tla" / "Alpha_clean.tla", "---- MODULE Alpha ----\n====\n")
    _write(family / "tla" / "MCAlpha.tla", "---- MODULE MCAlpha ----\n====\n")
    _write(family / "tla" / "MCAlpha_clean.tla", "---- MODULE MCAlpha ----\n====\n")
    _write(family / "txt" / "Alpha_comments.txt", "alpha prompt")
    _write(family / "txt" / "Alpha_comments_clean.txt", "alpha clean prompt")
    _write(family / "cfg" / "MCAlpha.cfg", "SPECIFICATION Spec\n")
    _write(formalllm_repo / "Input" / "train.json", json.dumps([{"id": "0001"}]))
    _write(formalllm_repo / "Input" / "val.json", json.dumps([{"id": "0002"}]))
    _write(formalllm_repo / "Input" / "test.json", json.dumps([]))
    _write(
        formalllm_repo / "doc" / "ARCHITECTURE.md",
        "├── all_models.json           # Metadata for 1800+ specifications\n",
    )

    pipeline = tmp_path / "tla-dataset-pipeline"
    _write(
        pipeline / "dvc.lock",
        "\n".join(
            [
                "schema: '2.0'",
                "stages:",
                "  pull:",
                "    outs:",
                "    - path: data/raw",
                "      size: 12034995",
                "      nfiles: 2628",
                "  parse:",
                "    deps:",
                "    - path: data/raw",
                "      size: 618486",
                "      nfiles: 227",
                "    outs:",
                "    - path: data/parsed",
                "      size: 22773073",
                "      nfiles: 3979",
                "",
            ]
        ),
    )
    _write(
        pipeline / "config" / "seeds" / "repos.yaml",
        "\n".join(
            [
                "orgs:",
                "  - OrgA",
                "  - OrgB",
                "repos:",
                "  - OrgA/RepoOne",
                "  - OrgB/RepoTwo",
                "  - OrgB/RepoThree",
                "users:",
                "  - UserA",
                "",
            ]
        ),
    )
    _write(
        pipeline / "config" / "seeds" / "queries.yaml",
        "queries:\n  - extension:tla\n  - TLAPS extension:tla\n",
    )
    _write(
        tmp_path / "ai4fm_public_tlaprove_corpora.json",
        json.dumps(
            {
                "aggregate": {
                    "total_public_jsonl_rows": 2350,
                    "tracked_public_jsonl_files": 6,
                    "all_public_jsonl_rows": 2757,
                    "all_public_jsonl_files": 19,
                }
            }
        ),
    )
    _write(
        tmp_path / "ai4fm_public_seed_file_manifest_v1.summary.json",
        json.dumps({"totals": {"tla": 2110}}),
    )
    _write(
        tmp_path / "ai4fm_public_seed_tla_modules_v1.summary.json",
        json.dumps({"kept_rows": 2108}),
    )
    _write(
        tmp_path / "ai4fm_public_seed_prover_candidates_v1.summary.json",
        json.dumps({"kept_rows": 124}),
    )
    _write(
        tmp_path / "ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        json.dumps({"kept_rows": 168, "unique_modules": 114}),
    )
    _write(
        tmp_path / "ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        json.dumps({"rows": 44}),
    )

    report = build_report(
        formalllm_root=formalllm,
        formalllm_input_root=formalllm_repo / "Input",
        formalllm_architecture_doc=formalllm_repo / "doc" / "ARCHITECTURE.md",
        pipeline_repo=pipeline,
        tlaprove_report_path=tmp_path / "ai4fm_public_tlaprove_corpora.json",
        seed_file_summary_path=tmp_path / "ai4fm_public_seed_file_manifest_v1.summary.json",
        seed_module_summary_path=tmp_path / "ai4fm_public_seed_tla_modules_v1.summary.json",
        seed_candidate_summary_path=tmp_path / "ai4fm_public_seed_prover_candidates_v1.summary.json",
        shape_ready_summary_path=tmp_path / "ai4fm_public_seed_prover_shape_ready_v1.summary.json",
        shape_ready_not_sany_summary_path=tmp_path / "ai4fm_public_seed_prover_shape_ready_not_sany_v1.summary.json",
        remote_head_resolver=lambda url: {
            "https://github.com/LUC-AI4FM/FormaLLM.git": "formalllm-head",
            "https://github.com/LUC-AI4FM/tla-dataset-pipeline.git": "pipeline-head",
        }.get(url),
    )

    assert report["formalllm"]["canonical_entries"] == 2
    assert report["formalllm"]["families"] == 1
    assert report["formalllm"]["tla_files"] == 4
    assert report["formalllm"]["clean_tla_files"] == 2
    assert report["formalllm"]["nonclean_tla_files"] == 2
    assert report["formalllm"]["repo_tla_files"] == 4
    assert report["formalllm"]["auxiliary_tla_files"] == 0
    assert report["formalllm"]["cfg_files"] == 1
    assert report["formalllm"]["repo_cfg_files"] == 1
    assert report["formalllm"]["auxiliary_cfg_files"] == 0
    assert report["formalllm"]["split_files"]["counts"] == {"train": 1, "val": 1, "test": 0}
    assert report["formalllm"]["split_files"]["total"] == 2
    assert report["formalllm"]["architecture_doc"]["metadata_specification_claim"] == "1800+"
    assert report["pipeline"]["pull"]["path"] == "data/raw"
    assert report["pipeline"]["pull"]["nfiles"] == 2628
    assert report["pipeline"]["parse_input"]["nfiles"] == 227
    assert report["pipeline"]["parse_output"]["nfiles"] == 3979
    assert report["pipeline"]["seed_config_counts"] == {"repos": 3, "orgs": 2, "users": 1, "queries": 2}
    assert report["broader_public_lanes"]["tla_prove_committed_public_jsonl"]["rows"] == 2757
    assert report["broader_public_lanes"]["seed_repo_tla_files"]["rows"] == 2110
    assert report["broader_public_lanes"]["usable_seed_modules"]["rows"] == 2108
    assert report["broader_public_lanes"]["shape_ready_not_sany_rows"]["rows"] == 44
    assert report["public_1800_plus_interpretation"]["claim"] == "1800+"
    assert report["public_1800_plus_interpretation"]["status"] == "stale_for_formalllm_canonical_layer"
    assert report["public_1800_plus_interpretation"]["closest_reproducible_public_surfaces"][0]["rows"] == 2757
    assert report["public_sources"]["live_remote_heads"] == {
        "formalllm_repo": "formalllm-head",
        "pipeline_repo": "pipeline-head",
    }
    assert report["warnings"] == [
        "FormaLLM architecture metadata claim differs from current canonical_entries."
    ]


def test_cli_writes_report_json(tmp_path: Path) -> None:
    formalllm_repo = tmp_path / "FormaLLM"
    formalllm = formalllm_repo / "data" / "FamilyOne"
    _write(formalllm / "FamilyOne.json", json.dumps({"data": []}))
    _write(formalllm_repo / "Input" / "train.json", json.dumps([]))
    _write(formalllm_repo / "Input" / "val.json", json.dumps([]))
    _write(formalllm_repo / "Input" / "test.json", json.dumps([]))
    _write(formalllm_repo / "doc" / "ARCHITECTURE.md", "No count here.\n")
    pipeline = tmp_path / "pipeline"
    _write(pipeline / "dvc.lock", "schema: '2.0'\nstages: {}\n")
    _write(tmp_path / "tlaprove.json", json.dumps({"aggregate": {"all_public_jsonl_rows": 0}}))
    _write(tmp_path / "seed_files.json", json.dumps({"totals": {"tla": 0}}))
    _write(tmp_path / "seed_modules.json", json.dumps({"kept_rows": 0}))
    _write(tmp_path / "seed_candidates.json", json.dumps({"kept_rows": 0}))
    _write(tmp_path / "shape_ready.json", json.dumps({"kept_rows": 0, "unique_modules": 0}))
    _write(tmp_path / "shape_ready_not_sany.json", json.dumps({"rows": 0}))
    out = tmp_path / "report.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspect_ai4fm_public_dataset_surface.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--formalllm-root",
            str(formalllm_repo / "data"),
            "--formalllm-input-root",
            str(formalllm_repo / "Input"),
            "--formalllm-architecture-doc",
            str(formalllm_repo / "doc" / "ARCHITECTURE.md"),
            "--pipeline-repo",
            str(pipeline),
            "--tlaprove-report",
            str(tmp_path / "tlaprove.json"),
            "--seed-file-summary",
            str(tmp_path / "seed_files.json"),
            "--seed-module-summary",
            str(tmp_path / "seed_modules.json"),
            "--seed-candidate-summary",
            str(tmp_path / "seed_candidates.json"),
            "--shape-ready-summary",
            str(tmp_path / "shape_ready.json"),
            "--shape-ready-not-sany-summary",
            str(tmp_path / "shape_ready_not_sany.json"),
            "--out",
            str(out),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = json.loads(result.stdout)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert stdout["formalllm"]["canonical_entries"] == 0
    assert stdout["formalllm"]["clean_tla_files"] == 0
    assert stdout["formalllm"]["nonclean_tla_files"] == 0
    assert stdout["formalllm"]["repo_tla_files"] == 0
    assert stdout["formalllm"]["auxiliary_tla_files"] == 0
    assert stdout["formalllm"]["split_files"]["total"] == 0
    assert stdout["public_1800_plus_interpretation"]["status"] == "aligned_with_current_canonical_layer"
    assert stdout["broader_public_lanes"]["usable_seed_modules"]["rows"] == 0
    assert saved == stdout
