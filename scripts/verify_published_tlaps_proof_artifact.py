#!/usr/bin/env python3
"""Verify the published final TLAPS proof artifact by re-running tlapm."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.reproduce_final_tlaps_prover import run_tlaps_module, summarize_results

DEFAULT_TARBALL = (
    REPO / "outputs" / "hf_publish" / "chattla-tla-prover-108-108" / "tlaps_reproduced_final_160816.tar.gz"
)
DEFAULT_EXPECTED_SUMMARY = (
    REPO / "outputs" / "hf_publish" / "chattla-tla-prover-108-108" / "metadata" / "summary.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discover_proofs(extracted_root: Path) -> list[Path]:
    proof_dir = extracted_root / "proofs"
    if not proof_dir.is_dir():
        raise FileNotFoundError(f"proof directory not found under extracted artifact: {proof_dir}")
    return sorted(path for path in proof_dir.glob("*.tla") if path.is_file())


def _load_expected(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def _display_tool_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return path.name


def _sanitize_result_paths(results: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for item in results:
        row = dict(item)
        raw_path = row.get("path")
        if isinstance(raw_path, str):
            row["path"] = f"proofs/{Path(raw_path).name}"
        raw_log = row.get("raw_log")
        if isinstance(raw_log, str):
            row["raw_log"] = _display_path(Path(raw_log)) or raw_log
        sanitized.append(row)
    return sanitized


def _expected_matches(actual: dict, expected: dict | None) -> bool | None:
    if expected is None:
        return None
    keys = ("modules", "exit_0", "exit_nonzero", "raw_proved", "raw_total", "all_modules_exit_0", "all_modules_proved", "no_asterisk")
    return all(actual.get(key) == expected.get(key) for key in keys)


def write_manifest(
    *,
    out_dir: Path,
    tarball: Path,
    expected_summary_path: Path | None,
    expected_matches: bool | None,
    args: argparse.Namespace,
) -> Path:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": "scripts/verify_published_tlaps_proof_artifact.py",
        "tarball": _display_path(tarball),
        "tarball_sha256": _sha256(tarball),
        "expected_summary": _display_path(expected_summary_path),
        "expected_matches": expected_matches,
        "out_dir": _display_path(out_dir),
        "tlapm": _display_tool_path(args.tlapm),
        "threads": args.threads,
        "timeout": args.timeout,
        "expected_modules": args.expected_modules,
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tarball", type=Path, default=DEFAULT_TARBALL)
    parser.add_argument("--expected-summary", type=Path, default=DEFAULT_EXPECTED_SUMMARY)
    parser.add_argument("--out-dir", type=Path, default=REPO / "outputs" / "autoprover" / "tlaps_verify_published")
    parser.add_argument("--tlapm", type=Path, default=Path(REPO / "src" / "shared" / "tlaps" / "bin" / "tlapm"))
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--expected-modules", type=int, default=18)
    parser.add_argument("--allow-failures", action="store_true")
    args = parser.parse_args(argv)

    tarball = Path(args.tarball)
    if not tarball.is_file():
        raise FileNotFoundError(f"published proof tarball not found: {tarball}")
    tlapm = Path(args.tlapm)
    if not tlapm.is_file():
        raise FileNotFoundError(f"tlapm not found: {tlapm}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"

    with tempfile.TemporaryDirectory(dir=out_dir.parent) as tmp:
        extract_root = Path(tmp)
        with tarfile.open(tarball, "r:gz") as archive:
            archive.extractall(extract_root)
        roots = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise RuntimeError(f"expected exactly one top-level directory in {tarball}, found {len(roots)}")
        proofs = _discover_proofs(roots[0])
        if len(proofs) != args.expected_modules:
            raise RuntimeError(
                f"expected {args.expected_modules} proof modules in published artifact, found {len(proofs)}"
            )
        results = [
            run_tlaps_module(
                tla_file=proof,
                tlapm=tlapm,
                raw_dir=raw_dir,
                threads=args.threads,
                timeout=args.timeout,
            )
            for proof in proofs
        ]

    summary = summarize_results(results, require_no_asterisk=True)
    summary["results"] = _sanitize_result_paths(summary["results"])
    summary["source_tarball"] = _display_path(tarball)
    summary["source_tarball_sha256"] = _sha256(tarball)
    summary["expected_summary_path"] = _display_path(args.expected_summary)
    expected = _load_expected(args.expected_summary)
    summary["matches_expected_summary"] = _expected_matches(summary, expected)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_manifest(
        out_dir=out_dir,
        tarball=tarball,
        expected_summary_path=args.expected_summary,
        expected_matches=summary["matches_expected_summary"],
        args=args,
    )
    print(json.dumps(summary, indent=2))

    ok = (
        summary["all_modules_exit_0"]
        and summary["all_modules_proved"]
        and summary["raw_proved"] == summary["raw_total"]
        and len(summary["results"]) == args.expected_modules
        and summary["matches_expected_summary"] is not False
    )
    return 0 if (ok or args.allow_failures) else 1


if __name__ == "__main__":
    raise SystemExit(main())
