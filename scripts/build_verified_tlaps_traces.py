#!/usr/bin/env python3
"""Build structured training traces from verified TLAPS proof artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

DEFAULT_ARTIFACT = (
    REPO
    / "outputs"
    / "hf_publish"
    / "chattla-tla-prover-108-108"
    / "tlaps_reproduced_final_160816.tar.gz"
)
DEFAULT_METADATA = REPO / "outputs" / "hf_publish" / "chattla-tla-prover-108-108" / "metadata"
DEFAULT_OUT = REPO / "data" / "processed" / "tla_prover" / "tlaps_verified_autoprover_traces_v1.jsonl"

_THEOREM_RE = re.compile(r"^\s*THEOREM\s+(.+?)\s*$", re.MULTILINE)
_END_RE = re.compile(r"^={4,}\s*$", re.MULTILINE)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tar_texts(artifact: Path, dirname: str, suffix: str) -> dict[str, str]:
    texts: dict[str, str] = {}
    with tarfile.open(artifact, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or f"/{dirname}/" not in member.name or not member.name.endswith(suffix):
                continue
            if "/.tlacache/" in member.name:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            texts[Path(member.name).stem] = handle.read().decode("utf-8", errors="replace")
    return texts


def _proof_text(module_text: str) -> str:
    theorem = _THEOREM_RE.search(module_text)
    if not theorem:
        return ""
    end = _END_RE.search(module_text, theorem.start())
    return module_text[theorem.start() : end.start()].rstrip() + "\n" if end else module_text[theorem.start() :].rstrip() + "\n"


def _target_theorem(module_text: str) -> str:
    theorem = _THEOREM_RE.search(module_text)
    return theorem.group(1).strip() if theorem else ""


def _is_verified(result: dict[str, Any], summary: dict[str, Any]) -> bool:
    return (
        summary.get("no_asterisk") is True
        and result.get("exit_code") == 0
        and result.get("timed_out") is not True
        and int(result.get("total") or 0) > 0
        and int(result.get("proved") or 0) == int(result.get("total") or -1)
        and int(result.get("failed") or 0) == 0
    )


def build_rows(artifact: Path, summary: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    proofs = _tar_texts(artifact, "proofs", ".tla")
    logs = _tar_texts(artifact, "raw", ".log")
    rows: list[dict[str, Any]] = []

    for result in sorted(summary.get("results", []), key=lambda item: item.get("module", "")):
        module = result.get("module")
        if not module or not _is_verified(result, summary):
            continue
        proof_module = proofs.get(module)
        if not proof_module:
            continue
        raw_log = logs.get(module, "")
        proof = _proof_text(proof_module)
        rows.append(
            {
                "schema": "tlaps_verified_autoprover_trace_v1",
                "module": module,
                "verified": True,
                "target": "Spec => []TypeOK",
                "target_theorem": _target_theorem(proof_module),
                "proof_module": proof_module,
                "proof_text": proof,
                "tlaps": {
                    "exit_code": result.get("exit_code"),
                    "proved": result.get("proved"),
                    "total": result.get("total"),
                    "failed": result.get("failed"),
                    "timed_out": result.get("timed_out", False),
                    "runtime_seconds": result.get("runtime_seconds"),
                },
                "verifier": {
                    "name": "TLAPS",
                    "tlapm": manifest.get("tlapm"),
                    "threads": manifest.get("threads"),
                    "command": manifest.get("command"),
                },
                "source": {
                    "proof_archive": str(artifact),
                    "proof_archive_sha256": manifest.get("package_sha256"),
                    "raw_log": result.get("raw_log"),
                },
                "hashes": {
                    "proof_module_sha256": _sha256_text(proof_module),
                    "proof_text_sha256": _sha256_text(proof),
                    "raw_log_sha256": _sha256_text(raw_log) if raw_log else None,
                },
                "raw_log_tail": raw_log[-2000:],
            }
        )
    return rows


def write_outputs(rows: list[dict[str, Any]], out: Path, summary_out: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    summary = {
        "schema": "tlaps_verified_autoprover_traces_v1_summary",
        "out": str(out),
        "rows": len(rows),
        "modules": [row["module"] for row in rows],
        "raw_proved": sum(int(row["tlaps"]["proved"] or 0) for row in rows),
        "raw_total": sum(int(row["tlaps"]["total"] or 0) for row in rows),
        "all_verified": all(row["verified"] for row in rows),
        "proof_archive_sha256": manifest.get("package_sha256"),
        "jsonl_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }
    summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_METADATA / "summary.json")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_METADATA / "manifest.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_OUT.with_suffix(".summary.json"))
    args = parser.parse_args()

    rows = build_rows(args.artifact, _read_json(args.summary), _read_json(args.manifest))
    summary = write_outputs(rows, args.out, args.summary_out, _read_json(args.manifest))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
