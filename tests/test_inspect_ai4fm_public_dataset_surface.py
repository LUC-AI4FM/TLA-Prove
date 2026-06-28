import json
import subprocess
from pathlib import Path

from scripts.inspect_ai4fm_public_dataset_surface import build_report


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_report_summarizes_formalllm_and_pipeline_surface(tmp_path: Path) -> None:
    formalllm = tmp_path / "FormaLLM" / "data"
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

    report = build_report(formalllm_root=formalllm, pipeline_repo=pipeline)

    assert report["formalllm"]["canonical_entries"] == 2
    assert report["formalllm"]["families"] == 1
    assert report["formalllm"]["tla_files"] == 4
    assert report["pipeline"]["pull"]["path"] == "data/raw"
    assert report["pipeline"]["pull"]["nfiles"] == 2628
    assert report["pipeline"]["parse_input"]["nfiles"] == 227
    assert report["pipeline"]["parse_output"]["nfiles"] == 3979


def test_cli_writes_report_json(tmp_path: Path) -> None:
    formalllm = tmp_path / "FormaLLM" / "data" / "FamilyOne"
    _write(formalllm / "FamilyOne.json", json.dumps({"data": []}))
    pipeline = tmp_path / "pipeline"
    _write(pipeline / "dvc.lock", "schema: '2.0'\nstages: {}\n")
    out = tmp_path / "report.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / "inspect_ai4fm_public_dataset_surface.py"

    result = subprocess.run(
        [
            "python3",
            str(script),
            "--formalllm-root",
            str(tmp_path / "FormaLLM" / "data"),
            "--pipeline-repo",
            str(pipeline),
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
    assert saved == stdout
