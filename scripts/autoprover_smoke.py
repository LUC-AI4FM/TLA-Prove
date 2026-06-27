"""Run a small verifier-guided TLA+ autoprover smoke.

Phase-1 target: prove/check ``Spec => []TypeOK`` for modules that already define
``Init``, ``Next``, ``vars``, ``Spec``, and ``TypeOK``. The script uses the
existing TLC inductiveness oracle and deterministic TLAPS skeleton generator.
If ``tlapm`` is available, it validates the emitted proof module too.

This intentionally does not call a local model. Model-assisted invariant repair
belongs in a later phase once the deterministic tooling lane is proven healthy.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.prover.inductiveness import check_inductive  # noqa: E402
from src.prover.skeleton import SafetySkeletonSpec, safety_proof_skeleton  # noqa: E402
from src.validators.tlaps_validator import validate_string  # noqa: E402

_MODULE_RE = re.compile(r"-{4,}\s*MODULE\s+(\w+)", re.IGNORECASE)
_END_RE = re.compile(r"^={4,}\s*$", re.MULTILINE)
_EXTENDS_RE = re.compile(r"^(\s*EXTENDS\s+)(.+?)\s*$", re.MULTILINE)


def _defines(src: str, name: str) -> bool:
    return bool(re.search(rf"^\s*{re.escape(name)}\s*==", src, re.MULTILINE))


def _module_name(src: str) -> str | None:
    match = _MODULE_RE.search(src)
    return match.group(1) if match else None


def _default_globs() -> list[str]:
    return [
        str(REPO / "outputs" / "diamond_gen" / "*_work" / "*.tla"),
        str(REPO / "data" / "FormaLLM" / "data" / "*" / "tla" / "*.tla"),
    ]


def _discover(patterns: list[str], limit: int) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for raw in sorted(glob.glob(pattern)):
            path = Path(raw).resolve()
            if path not in seen:
                paths.append(path)
                seen.add(path)
    return paths[:limit] if limit else paths


def _discover_from_module_lists(module_lists: list[Path], limit: int) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for module_list in module_lists:
        base = module_list.resolve().parent
        for raw in module_list.read_text(encoding="utf-8").splitlines():
            item = raw.strip()
            if not item or item.startswith("#"):
                continue
            path = Path(item)
            if not path.is_absolute():
                repo_path = REPO / path
                path = repo_path if repo_path.exists() else base / path
            path = path.resolve()
            if path not in seen:
                paths.append(path)
                seen.add(path)
    return paths[:limit] if limit else paths


def _is_candidate(src: str) -> bool:
    return all(_defines(src, name) for name in ("Init", "Next", "Spec", "TypeOK")) and (
        _defines(src, "vars") or bool(re.search(r"Spec\s*==.*\[\]\[Next\]_", src, re.DOTALL))
    )


def _operator_body(src: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}\s*==", src, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_def = re.search(r"^\s*[A-Za-z_]\w*(?:\([^)]*\))?\s*==", src[start:], re.MULTILINE)
    end_match = _END_RE.search(src[start:])
    candidates = [len(src)]
    if next_def:
        candidates.append(start + next_def.start())
    if end_match:
        candidates.append(start + end_match.start())
    return src[start:min(candidates)]


def _enumerability_issue(src: str) -> str | None:
    """Return a cheap reason TypeOK is unsuitable as TLC INIT, if obvious."""
    typeok = _operator_body(src, "TypeOK")
    if not typeok:
        return "missing_typeok_body"
    if "\\subseteq" in typeok:
        return "typeok_uses_subseteq"
    if re.search(r"\bSUBSET\b", typeok):
        return "typeok_uses_subset_domain"
    helper_refs = re.findall(r"^\s*/\\\s*([A-Za-z_]\w*)\s*$", typeok, re.MULTILINE)
    if helper_refs:
        return "typeok_references_helper_" + helper_refs[0]
    return None


def _ensure_extends_tlaps(src: str) -> str:
    match = _EXTENDS_RE.search(src)
    if match:
        modules = [part.strip() for part in match.group(2).split(",")]
        if "TLAPS" in modules:
            return src
        replacement = f"{match.group(1)}{match.group(2).rstrip()}, TLAPS"
        return src[: match.start()] + replacement + src[match.end():]

    module_match = _MODULE_RE.search(src)
    if not module_match:
        return src
    insert_at = src.find("\n", module_match.end())
    if insert_at < 0:
        return src + "\nEXTENDS TLAPS\n"
    return src[: insert_at + 1] + "EXTENDS TLAPS\n" + src[insert_at + 1:]


def _inject_typeok_theorem(src: str, proof: str) -> str:
    src = _ensure_extends_tlaps(src)
    block = (
        "\n"
        "THEOREM ChatTLA_TypeOKSafety == Spec => []TypeOK\n"
        "PROOF\n"
        f"{proof.rstrip()}\n"
    )
    match = _END_RE.search(src)
    if match:
        return src[: match.start()] + block + src[match.start():]
    return src.rstrip() + block + "====\n"


def _tlapm_path() -> str | None:
    env = os.getenv("CHATTLA_TLAPM")
    if env and Path(env).exists():
        return env
    found = shutil.which("tlapm")
    if found:
        return found
    bundled = REPO / "src" / "shared" / "tlaps" / "bin" / "tlapm"
    return str(bundled) if bundled.exists() else None


def run_one(path: Path, *, tlc_timeout: int, tlapm_timeout: int, run_tlaps: bool) -> dict:
    started = time.time()
    rel = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
    src = path.read_text(encoding="utf-8", errors="replace")
    module = _module_name(src)
    row: dict = {
        "module_path": rel,
        "module": module,
        "target": "Spec => []TypeOK",
        "status": "started",
    }
    if not module:
        row.update(status="skipped", reason="no_module_name")
        return row
    if not _is_candidate(src):
        row.update(status="skipped", reason="missing_init_next_spec_typeok_vars")
        return row
    enum_issue = _enumerability_issue(src)
    if enum_issue:
        row.update(status="skipped", reason=enum_issue)
        return row

    ind = check_inductive(src, "TypeOK", timeout=tlc_timeout)
    row["tlc_inductive"] = ind.inductive
    row["tlc_error"] = ind.error
    row["cti_preview"] = (ind.cti or "")[:600]

    if ind.error:
        row.update(status="tlc_error", runtime_seconds=round(time.time() - started, 3))
        return row
    if not ind.inductive:
        row.update(status="not_inductive", runtime_seconds=round(time.time() - started, 3))
        return row

    proof = safety_proof_skeleton(
        SafetySkeletonSpec(
            invariant_name="TypeOK",
            next_action_names=["Next"],
            property_name=None,
            vars_name="vars",
        )
    )
    proof_module = _inject_typeok_theorem(src, proof)
    row["skeleton_chars"] = len(proof)
    row["proof_module_chars"] = len(proof_module)

    if not run_tlaps:
        row.update(status="skeleton_emitted", runtime_seconds=round(time.time() - started, 3))
        return row

    tlapm = _tlapm_path()
    if not tlapm:
        row.update(status="no_tlapm", runtime_seconds=round(time.time() - started, 3))
        return row

    try:
        result = validate_string(
            proof_module,
            module_name=module,
            tlapm=Path(tlapm),
            timeout=tlapm_timeout,
        )
        row["tlapm"] = {
            "path": tlapm,
            "tier": result.tier,
            "obligations_total": result.obligations_total,
            "obligations_proved": result.obligations_proved,
            "obligations_failed": result.obligations_failed,
            "timed_out": result.timed_out,
            "errors": result.errors[:5],
            "raw_tail": result.raw_output[-1200:],
        }
        row["status"] = "tlaps_" + result.tier
    except Exception as exc:
        row.update(status="tlaps_exception", tlaps_exception=repr(exc)[:500])

    row["runtime_seconds"] = round(time.time() - started, 3)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", action="append", dest="globs", help="Input glob; may be repeated.")
    parser.add_argument(
        "--module-list",
        action="append",
        type=Path,
        default=[],
        help="File containing explicit .tla paths, one per line; may be repeated.",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--tlc-timeout", type=int, default=45)
    parser.add_argument("--tlapm-timeout", type=int, default=60)
    parser.add_argument("--skip-tlaps", action="store_true")
    parser.add_argument(
        "--out",
        default=str(REPO / "outputs" / "autoprover" / "smoke.jsonl"),
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.module_list:
        paths = _discover_from_module_lists(args.module_list, args.limit)
    else:
        paths = _discover(args.globs or _default_globs(), args.limit)

    summary: dict[str, int] = {"discovered": len(paths)}
    with out_path.open("w", encoding="utf-8") as out:
        for path in paths:
            row = run_one(
                path,
                tlc_timeout=args.tlc_timeout,
                tlapm_timeout=args.tlapm_timeout,
                run_tlaps=not args.skip_tlaps,
            )
            summary[row["status"]] = summary.get(row["status"], 0) + 1
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(
                f"[autoprover] {row['status']:>16} {row.get('module') or '?'} "
                f"{row.get('module_path')}",
                flush=True,
            )

    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"[autoprover] wrote {out_path}")
    print(f"[autoprover] summary {summary}")


if __name__ == "__main__":
    main()
