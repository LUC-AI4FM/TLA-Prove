import json
import tarfile
from pathlib import Path

from scripts.build_verified_tlaps_traces import build_rows


def _add_text(archive: tarfile.TarFile, name: str, text: str) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, fileobj=__import__("io").BytesIO(data))


def test_build_rows_extracts_verified_trace_fields(tmp_path: Path) -> None:
    artifact = tmp_path / "proofs.tar.gz"
    module_text = """---- MODULE Mini ----
EXTENDS Naturals, TLAPS
THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK
PROOF
  OBVIOUS
====
"""
    with tarfile.open(artifact, "w:gz") as archive:
        _add_text(archive, "run/proofs/Mini.tla", module_text)
        _add_text(archive, "run/raw/Mini.log", "[INFO]: All 1 obligation proved.\n")

    summary = {
        "no_asterisk": True,
        "results": [
            {
                "module": "Mini",
                "exit_code": 0,
                "runtime_seconds": 0.1,
                "proved": 1,
                "total": 1,
                "failed": 0,
                "timed_out": False,
                "raw_log": "run/raw/Mini.log",
            }
        ],
    }
    manifest = {
        "tlapm": "/tool/tlapm",
        "threads": 1,
        "package_sha256": "abc123",
        "command": "scripts/reproduce_final_tlaps_prover.py",
    }

    rows = build_rows(artifact, summary, manifest)

    assert len(rows) == 1
    row = rows[0]
    assert row["module"] == "Mini"
    assert row["verified"] is True
    assert row["target_theorem"] == "ChatTLA_TypeOKSafety == Spec => []TypeOK"
    assert row["proof_text"].startswith("THEOREM ChatTLA_TypeOKSafety")
    assert row["proof_module"] == module_text
    assert row["tlaps"]["proved"] == 1
    assert row["verifier"]["threads"] == 1
    assert row["source"]["proof_archive_sha256"] == "abc123"
    assert row["raw_log_tail"] == "[INFO]: All 1 obligation proved.\n"


def test_build_rows_rejects_unverified_summary_entries(tmp_path: Path) -> None:
    artifact = tmp_path / "proofs.tar.gz"
    with tarfile.open(artifact, "w:gz") as archive:
        _add_text(archive, "run/proofs/Mini.tla", "---- MODULE Mini ----\n====\n")

    summary = {
        "no_asterisk": True,
        "results": [{"module": "Mini", "exit_code": 0, "proved": 0, "total": 1, "failed": 1}],
    }

    rows = build_rows(artifact, summary, {})

    assert rows == []
