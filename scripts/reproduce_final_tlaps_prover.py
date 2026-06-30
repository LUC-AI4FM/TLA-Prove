#!/usr/bin/env python3
"""Reproduce and package the final ChatTLA TLAPS proof set.

The final 108/108 proof result is a composition of a base proof directory plus
two source-preserving repairs. This command rebuilds that proof directory,
validates each module with ``tlapm --threads 1``, writes raw logs and
``summary.json``, and can bundle the result as a tarball for durable staging.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]

_ALL_PROVED_RE = re.compile(r"All\s+(\d+)\s+obligations?\s+proved", re.IGNORECASE)
_FAILED_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s+obligations?\s+failed", re.IGNORECASE)
_HOST_SUFFIX_RE = re.compile(r"\.(?:[A-Za-z][A-Za-z0-9-]*)(?:\.[A-Za-z0-9-]+){2,}(?=/|$)")


@dataclass(frozen=True)
class ParsedTlapsOutput:
    proved: int
    total: int
    failed: int

    @property
    def proved_all(self) -> bool:
        return self.total > 0 and self.failed == 0 and self.proved == self.total


@dataclass(frozen=True)
class ModuleResult:
    module: str
    path: str
    exit_code: int | None
    runtime_seconds: float
    proved: int
    total: int
    failed: int
    timed_out: bool
    raw_log: str

    @property
    def proved_all(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and self.total > 0
            and self.failed == 0
            and self.proved == self.total
        )


def parse_tlaps_output(output: str) -> ParsedTlapsOutput:
    """Parse TLAPS 1.5.0 obligation counts from combined stdout/stderr."""
    proved_sum = sum(int(match) for match in _ALL_PROVED_RE.findall(output))

    failed_sum = 0
    total_from_failed = 0
    for failed_str, total_str in _FAILED_RE.findall(output):
        failed_sum += int(failed_str)
        total_from_failed += int(total_str)

    total = proved_sum + total_from_failed
    proved = proved_sum + max(total_from_failed - failed_sum, 0)
    return ParsedTlapsOutput(proved=proved, total=total, failed=failed_sum)


def build_proof_set(
    *,
    base_proof_dir: Path,
    replacements: Mapping[str, Path],
    proof_dir: Path,
) -> None:
    """Copy base proofs and overwrite named modules with repair files."""
    if not base_proof_dir.is_dir():
        raise FileNotFoundError(f"base proof directory not found: {base_proof_dir}")
    if proof_dir.exists():
        shutil.rmtree(proof_dir)
    shutil.copytree(base_proof_dir, proof_dir)

    for module_file, replacement in replacements.items():
        if not replacement.is_file():
            raise FileNotFoundError(f"replacement proof file not found: {replacement}")
        shutil.copy2(replacement, proof_dir / module_file)


def run_tlaps_module(
    *,
    tla_file: Path,
    tlapm: Path,
    raw_dir: Path,
    threads: int,
    timeout: int,
) -> ModuleResult:
    tla_file = tla_file.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_log = raw_dir / f"{tla_file.stem}.log"
    cmd = [str(tlapm), "--threads", str(threads), str(tla_file)]

    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=tla_file.parent,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code: int | None = proc.returncode
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        output = stdout + stderr + f"\n[TIMEOUT]: tlapm timed out after {timeout}s\n"

    elapsed = time.monotonic() - started
    raw_log.write_text(output, encoding="utf-8")
    parsed = parse_tlaps_output(output)
    return ModuleResult(
        module=tla_file.stem,
        path=str(tla_file),
        exit_code=exit_code,
        runtime_seconds=round(elapsed, 3),
        proved=parsed.proved,
        total=parsed.total,
        failed=parsed.failed,
        timed_out=timed_out,
        raw_log=str(raw_log),
    )


def summarize_results(
    results: Sequence[ModuleResult],
    *,
    require_no_asterisk: bool,
) -> dict:
    exit_0 = sum(1 for result in results if result.exit_code == 0)
    exit_nonzero = len(results) - exit_0
    raw_proved = sum(result.proved for result in results)
    raw_total = sum(result.total for result in results)
    all_proved = bool(results) and all(result.proved_all for result in results)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": len(results),
        "exit_0": exit_0,
        "exit_nonzero": exit_nonzero,
        "raw_proved": raw_proved,
        "raw_total": raw_total,
        "all_modules_exit_0": all_proved,
        "all_modules_proved": all_proved,
        "no_asterisk": require_no_asterisk,
        "results": [asdict(result) for result in sorted(results, key=lambda item: item.module)],
    }


def _default_tlapm() -> Path:
    env = os.getenv("CHATTLA_TLAPM")
    if env:
        return Path(env)
    return REPO / "src" / "shared" / "tlaps" / "bin" / "tlapm"


def _default_base_proof_dir() -> Path:
    env = os.getenv("CHATTLA_BASE_PROOF_DIR")
    if env:
        return Path(env)
    preferred = REPO / "outputs" / "autoprover" / "tlaps_mixed_targeted_t1_160785" / "proofs"
    if preferred.is_dir():
        return preferred
    matches = sorted((REPO / "outputs" / "autoprover").glob("tlaps_mixed_targeted_t1_160785*/proofs"))
    if matches:
        return matches[0]
    return preferred


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def _public_tool_ref(path: Path | str) -> str:
    text = str(path)
    return Path(text).name if text.startswith("/") else text


def _public_proof_dir_ref(path: Path | str) -> str:
    return _HOST_SUFFIX_RE.sub("", _repo_relative(Path(path)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(*, out_dir: Path, package_path: Path | None, args: argparse.Namespace) -> Path:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": "scripts/reproduce_final_tlaps_prover.py",
        "base_proof_dir": _public_proof_dir_ref(args.base_proof_dir),
        "atomic_proof": _repo_relative(Path(args.atomic_proof)),
        "idempotency_proof": _repo_relative(Path(args.idempotency_proof)),
        "out_dir": _repo_relative(out_dir),
        "tlapm": _public_tool_ref(args.tlapm),
        "threads": args.threads,
        "timeout": args.timeout,
        "package": str(package_path) if package_path else None,
    }
    if package_path and package_path.is_file():
        manifest["package_sha256"] = _sha256(package_path)
        manifest["package_bytes"] = package_path.stat().st_size
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def package_output(*, out_dir: Path, package_path: Path) -> Path:
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(package_path, "w:gz") as archive:
        archive.add(out_dir, arcname=out_dir.name)
    return package_path


def _replacement_map(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "AtomicRegister.tla": Path(args.atomic_proof),
        "IdempotencyKey.tla": Path(args.idempotency_proof),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-proof-dir",
        default=str(_default_base_proof_dir()),
    )
    parser.add_argument(
        "--atomic-proof",
        default=str(
            REPO
            / "outputs"
            / "autoprover"
            / "tlaps_final_source_preserving_repairs_161630"
            / "AtomicRegister_source_preserving_choose.tla"
        ),
    )
    parser.add_argument(
        "--idempotency-proof",
        default=str(
            REPO
            / "outputs"
            / "autoprover"
            / "tlaps_final_source_preserving_repairs_161630"
            / "IdempotencyKey_firstcall10.tla"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO / "outputs" / "autoprover" / "tlaps_reproduced_final"),
    )
    parser.add_argument("--tlapm", type=Path, default=_default_tlapm())
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--expected-modules", type=int, default=18)
    parser.add_argument("--allow-failures", action="store_true")
    parser.add_argument("--require-no-asterisk", action="store_true", default=True)
    parser.add_argument("--package", type=Path)
    args = parser.parse_args(argv)

    tlapm = Path(args.tlapm)
    if not tlapm.is_file():
        raise FileNotFoundError(f"tlapm not found: {tlapm}")

    out_dir = Path(args.out_dir)
    proof_dir = out_dir / "proofs"
    raw_dir = out_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True)

    build_proof_set(
        base_proof_dir=Path(args.base_proof_dir),
        replacements=_replacement_map(args),
        proof_dir=proof_dir,
    )

    proof_files = sorted(proof_dir.glob("*.tla"))
    results = [
        run_tlaps_module(
            tla_file=path,
            tlapm=tlapm,
            raw_dir=raw_dir,
            threads=args.threads,
            timeout=args.timeout,
        )
        for path in proof_files
    ]

    summary = summarize_results(results, require_no_asterisk=args.require_no_asterisk)
    summary.update(
        {
            "tlapm": _public_tool_ref(tlapm),
            "threads": args.threads,
            "timeout": args.timeout,
            "base_proof_dir": _public_proof_dir_ref(args.base_proof_dir),
            "replacements": {
                key: _repo_relative(value) for key, value in _replacement_map(args).items()
            },
        }
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if args.package:
        package_output(out_dir=out_dir, package_path=args.package)
    write_manifest(out_dir=out_dir, package_path=args.package, args=args)

    print(json.dumps({k: summary[k] for k in ("modules", "exit_0", "exit_nonzero", "raw_proved", "raw_total", "all_modules_exit_0")}, indent=2))

    if len(results) != args.expected_modules:
        print(f"expected {args.expected_modules} modules, found {len(results)}")
        return 2
    if not args.allow_failures and not summary["all_modules_exit_0"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
