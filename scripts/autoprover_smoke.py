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
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.prover.inductiveness import check_inductive  # noqa: E402
from src.prover.skeleton import SafetySkeletonSpec, safety_proof_skeleton  # noqa: E402
from src.validators.sany_validator import validate_string as validate_sany_string  # noqa: E402
from src.validators.tlaps_validator import validate_string as validate_tlaps_string  # noqa: E402

_MODULE_RE = re.compile(r"-{4,}\s*MODULE\s+(\w+)", re.IGNORECASE)
_END_RE = re.compile(r"^={4,}\s*$", re.MULTILINE)
_EXTENDS_RE = re.compile(r"^(\s*EXTENDS\s+)(.+?)\s*$", re.MULTILINE)
_TLAPS_TUPLE_BINDER_RE = re.compile(r"^\s*[A-Za-z_]\w*\s*\[\s*<<", re.MULTILINE)
_MAX_INIT_STATE_SPACE = 50_000_000


def _defines(src: str, name: str) -> bool:
    return bool(re.search(rf"^\s*{re.escape(name)}\s*==", src, re.MULTILINE))


def _module_name(src: str) -> str | None:
    match = _MODULE_RE.search(src)
    return match.group(1) if match else None


def _default_globs() -> list[str]:
    return [
        str(REPO / "outputs" / "diamond_gen" / "*_work" / "*.tla"),
        str(REPO / "data" / "FormaLLM" / "data" / "*" / "tla" / "*.tla"),
        str(REPO / "outputs" / "materialized_tla" / "tla_descriptions" / "*.tla"),
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


def _declared_variables(src: str) -> list[str]:
    lines = src.splitlines()
    start = None
    payload = ""
    for idx, line in enumerate(lines):
        match = re.match(r"^\s*VARIABLES?\b(.*)$", line)
        if match:
            start = idx
            payload = match.group(1)
            break
    if start is None:
        return []
    chunks = [payload]
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped:
            break
        if re.match(r"^\s*[A-Za-z_]\w*(?:\([^)]*\))?\s*==", line):
            break
        if re.match(r"^\s*(?:----|====)", line):
            break
        chunks.append(line)
        if "," not in line:
            break
    text = "\n".join(chunks)
    text = re.sub(r"\\\*.*", "", text)
    text = re.sub(r"^\s*VARIABLES?\b", "", text, count=1)
    if not text.strip():
        return []
    names: list[str] = []
    for part in text.split(","):
        ident = part.strip()
        if ident and re.match(r"^[A-Za-z_]\w*$", ident):
            names.append(ident)
    return names


def _simple_definitions(src: str) -> dict[str, str]:
    defs: dict[str, str] = {}
    for line in src.splitlines():
        match = re.match(r"^\s*([A-Za-z_]\w*)\s*==\s*(.+?)\s*$", line)
        if not match:
            continue
        defs[match.group(1)] = re.sub(r"\s*\\\*.*$", "", match.group(2)).strip()
    return defs


def _split_top_level(expr: str, token: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    i = 0
    while i < len(expr):
        if expr.startswith(token, i) and depth_paren == depth_brace == depth_bracket == 0:
            parts.append("".join(current).strip())
            current = []
            i += len(token)
            continue
        ch = expr[i]
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren = max(0, depth_paren - 1)
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace = max(0, depth_brace - 1)
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket = max(0, depth_bracket - 1)
        current.append(ch)
        i += 1
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _strip_wrapping_parens(expr: str) -> str:
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        balanced = True
        for idx, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(expr) - 1:
                    balanced = False
                    break
        if not balanced or depth != 0:
            break
        expr = expr[1:-1].strip()
    return expr


def _int_value(expr: str, defs: dict[str, str], seen: set[str] | None = None) -> int | None:
    expr = _strip_wrapping_parens(expr)
    if re.fullmatch(r"\d+", expr):
        return int(expr)
    if seen is None:
        seen = set()
    if re.fullmatch(r"[A-Za-z_]\w*", expr):
        if expr in seen or expr not in defs:
            return None
        return _int_value(defs[expr], defs, seen | {expr})
    parts = _split_top_level(expr, "+")
    if len(parts) > 1:
        values = [_int_value(part, defs, seen) for part in parts]
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)
    parts = _split_top_level(expr, "-")
    if len(parts) > 1:
        head = _int_value(parts[0], defs, seen)
        tail = [_int_value(part, defs, seen) for part in parts[1:]]
        if head is None or any(value is None for value in tail):
            return None
        return head - sum(value for value in tail if value is not None)
    return None


def _set_cardinality(expr: str, defs: dict[str, str], seen: set[str] | None = None) -> int | None:
    expr = _strip_wrapping_parens(expr)
    if seen is None:
        seen = set()
    if expr in {"Nat", "Int"}:
        return None
    if expr == "BOOLEAN":
        return 2
    if re.fullmatch(r"[A-Za-z_]\w*", expr):
        if expr in seen or expr not in defs:
            return None
        return _set_cardinality(defs[expr], defs, seen | {expr})
    if expr.startswith("SUBSET "):
        inner = _set_cardinality(expr[len("SUBSET ") :], defs, seen)
        return None if inner is None else 2 ** inner
    if expr.startswith("[") and expr.endswith("]") and "->" in expr:
        inner = expr[1:-1]
        parts = _split_top_level(inner, "->")
        if len(parts) != 2:
            return None
        dom = _set_cardinality(parts[0], defs, seen)
        rng = _set_cardinality(parts[1], defs, seen)
        if dom is None or rng is None:
            return None
        return rng ** dom
    product_parts = _split_top_level(expr, "\\X")
    if len(product_parts) > 1:
        total = 1
        for part in product_parts:
            size = _set_cardinality(part, defs, seen)
            if size is None:
                return None
            total *= size
        return total
    union_parts = _split_top_level(expr, "\\cup")
    if len(union_parts) > 1:
        total = 0
        for part in union_parts:
            size = _set_cardinality(part, defs, seen)
            if size is None:
                return None
            total += size
        return total
    range_match = re.fullmatch(r"(.+)\.\.(.+)", expr)
    if range_match:
        start = _int_value(range_match.group(1), defs, seen)
        end = _int_value(range_match.group(2), defs, seen)
        if start is None or end is None or end < start:
            return None
        return end - start + 1
    if expr.startswith("{") and expr.endswith("}"):
        inner = expr[1:-1].strip()
        if not inner:
            return 0
        return len(_split_top_level(inner, ","))
    return None


def _split_top_level_conjuncts(body: str) -> list[str]:
    clauses: list[str] = []
    current: list[str] = []
    for raw_line in body.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.lstrip().startswith("/\\"):
            if current:
                clauses.append("\n".join(current))
            current = [raw_line]
        elif current:
            current.append(raw_line)
        elif raw_line.strip():
            current = [raw_line]
    if current:
        clauses.append("\n".join(current))
    return clauses


def _normalize_expr(expr: str) -> str:
    return " ".join(line.strip() for line in expr.splitlines() if line.strip())


def _normalize_noncomment_expr(expr: str) -> str:
    return " ".join(
        line.strip()
        for line in expr.splitlines()
        if line.strip() and not line.strip().startswith("\\*")
    )


def _seq_domain_expr(typeok: str, variable: str) -> str | None:
    match = re.search(
        rf"^\s*/\\\s*{re.escape(variable)}\s*\\in\s*Seq\s*\(([^\\n]+)\)\s*$",
        typeok,
        re.MULTILINE,
    )
    if not match:
        return None
    return _normalize_expr(re.sub(r"\s*\\\*.*$", "", match.group(1), flags=re.MULTILINE))


def _domain_cardinality_bound_expr(domain: str, defs: dict[str, str]) -> str | None:
    normalized = _normalize_expr(domain)
    range_match = re.fullmatch(r"(.+)\.\.(.+)", normalized)
    if range_match:
        start_expr = _strip_wrapping_parens(range_match.group(1))
        end_expr = _strip_wrapping_parens(range_match.group(2))
        if start_expr == "1":
            return end_expr
    domain_size = _set_cardinality(normalized, defs)
    return None if domain_size is None else str(domain_size)


def _helper_conjunct_name(clause: str) -> str | None:
    match = re.match(r"^\s*(?:/\\\s*)?([A-Za-z_]\w*)\s*$", clause)
    return match.group(1) if match else None


def _seq_len_upper_bound(
    src: str,
    clauses: list[str],
    variable: str,
    seen_helpers: set[str] | None = None,
) -> str | None:
    if seen_helpers is None:
        seen_helpers = set()
    patterns = (
        rf"^\s*(?:/\\\s*)?Len\(\s*{re.escape(variable)}\s*\)\s*<=\s*(.+)$",
        rf"^\s*(?:/\\\s*)?Len\(\s*{re.escape(variable)}\s*\)\s*\\in\s*0\s*\.\.\s*(.+)$",
    )
    for clause in clauses:
        stripped = clause.strip()
        for pattern in patterns:
            match = re.match(pattern, stripped, re.DOTALL)
            if match:
                return _normalize_expr(re.sub(r"\s*\\\*.*$", "", match.group(1), flags=re.MULTILINE))
        helper = _helper_conjunct_name(stripped)
        if helper and helper not in seen_helpers:
            body = _operator_body(src, helper)
            if body:
                bound = _seq_len_upper_bound(
                    src,
                    _split_top_level_conjuncts(body),
                    variable,
                    seen_helpers | {helper},
                )
                if bound is not None:
                    return bound
    return None


def _is_strictly_increasing_sequence(
    src: str,
    clauses: list[str],
    variable: str,
    seen_helpers: set[str] | None = None,
) -> bool:
    if seen_helpers is None:
        seen_helpers = set()
    pattern = (
        rf"^\s*(?:/\\\s*)?\\A\s+([A-Za-z_]\w*)\s+\\in\s+1\.\.\(Len\(\s*{re.escape(variable)}\s*\)\s*-\s*1\)\s*:\s*"
        rf"{re.escape(variable)}\[\1\]\s*<\s*{re.escape(variable)}\[\1\+1\]\s*$"
    )
    for clause in clauses:
        stripped = _normalize_noncomment_expr(clause)
        if re.match(pattern, stripped):
            return True
        helper = _helper_conjunct_name(stripped)
        if helper and helper not in seen_helpers:
            body = _operator_body(src, helper)
            if body and _is_strictly_increasing_sequence(
                src,
                _split_top_level_conjuncts(body),
                variable,
                seen_helpers | {helper},
            ):
                return True
    return False


def _length_sum_relation(clause: str) -> tuple[str, str, str] | None:
    patterns = (
        r"^\s*(?:/\\\s*)?Len\(\s*([A-Za-z_]\w*)\s*\)\s*\+\s*Len\(\s*([A-Za-z_]\w*)\s*\)\s*=\s*Len\(\s*([A-Za-z_]\w*)\s*\)\s*$",
        r"^\s*(?:/\\\s*)?Len\(\s*([A-Za-z_]\w*)\s*\)\s*=\s*Len\(\s*([A-Za-z_]\w*)\s*\)\s*\+\s*Len\(\s*([A-Za-z_]\w*)\s*\)\s*$",
    )
    for pattern in patterns:
        match = re.match(pattern, clause)
        if match:
            groups = match.groups()
            return (groups[0], groups[1], groups[2]) if "+" in clause.split("=", 1)[0] else (groups[1], groups[2], groups[0])
    return None


def _seq_len_upper_bounds(src: str, clauses: list[str]) -> dict[str, str]:
    variables = _declared_variables(src)
    typeok = _operator_body(src, "TypeOK")
    defs = _simple_definitions(src)
    bounds = {
        variable: bound
        for variable in variables
        if (bound := _seq_len_upper_bound(src, clauses, variable)) is not None
    }
    changed = True
    while changed:
        changed = False
        for clause in clauses:
            relation = _length_sum_relation(clause.strip())
            if relation is None:
                continue
            left, right, total = relation
            total_bound = bounds.get(total)
            if total_bound is None:
                continue
            for variable in (left, right):
                if variable not in bounds:
                    bounds[variable] = total_bound
                    changed = True
        for variable in variables:
            if variable in bounds:
                continue
            domain = _seq_domain_expr(typeok, variable)
            if not domain or not _is_strictly_increasing_sequence(src, clauses, variable):
                continue
            domain_bound = _domain_cardinality_bound_expr(domain, defs)
            if domain_bound is None:
                continue
            bounds[variable] = domain_bound
            changed = True
    return bounds


def _has_unbounded_seq_domain(typeok: str, variable: str, seq_len_bounds: dict[str, str]) -> bool:
    match = re.search(
        rf"^\s*/\\\s*{re.escape(variable)}\s*\\in\s*Seq\s*\((.+)\)\s*$",
        typeok,
        re.MULTILINE | re.DOTALL,
    )
    return bool(match) and variable not in seq_len_bounds


def _typeok_init_state_space_too_large(src: str) -> bool:
    typeok = _operator_body(src, "TypeOK")
    if not typeok:
        return False
    clauses = _split_top_level_conjuncts(typeok)
    direct_domains: dict[str, tuple[str, str]] = {}
    for clause in clauses:
        stripped = clause.strip()
        for variable in _declared_variables(src):
            match = re.search(rf"^\s*/\\\s*{re.escape(variable)}\s*(\\in|=|\\subseteq)\s*(.+)$", stripped, re.DOTALL)
            if match:
                rhs = re.sub(r"\s*\\\*.*$", "", match.group(2), flags=re.MULTILINE)
                direct_domains[variable] = (match.group(1), " ".join(line.strip() for line in rhs.splitlines() if line.strip()))
                break
    defs = _simple_definitions(src)
    estimate = 1
    for variable in _declared_variables(src):
        if variable not in direct_domains:
            return False
        operator, domain = direct_domains[variable]
        if operator == "=":
            domain_size = 1
        elif operator == "\\subseteq":
            inner = _set_cardinality(domain, defs)
            domain_size = None if inner is None else 2 ** inner
        else:
            domain_size = _set_cardinality(domain, defs)
        if domain_size is None:
            return False
        estimate *= domain_size
        if estimate > _MAX_INIT_STATE_SPACE:
            return True
    return False


def _enumerability_issue(src: str) -> str | None:
    """Return a cheap reason TypeOK is unsuitable as TLC INIT, if obvious."""
    typeok = _operator_body(src, "TypeOK")
    if not typeok:
        return "missing_typeok_body"
    if re.search(r"^\s*ASSUME\b.*\\in\s*\[", src, re.MULTILINE | re.DOTALL):
        return "assume_requires_function_constant_cfg"
    if re.search(r"^\s*ASSUME\b.*\\subseteq\s*\(?\s*SUBSET\b", src, re.MULTILINE | re.DOTALL):
        return "assume_requires_powerset_constant_cfg"
    if re.search(r"\b(Array|ArrayOfAnyLength)\s*\(", typeok):
        return "typeok_uses_sequence_backed_array_domain"
    clauses = _split_top_level_conjuncts(typeok)
    seq_len_bounds = _seq_len_upper_bounds(src, clauses)
    for variable in _declared_variables(src):
        if _has_unbounded_seq_domain(typeok, variable, seq_len_bounds):
            return "typeok_uses_unbounded_seq"
    if re.search(r"\\in\s*\[.*->\s*(Nat|Int)\b", typeok, re.DOTALL):
        return "typeok_function_range_uses_infinite_builtin"
    for variable in _declared_variables(src):
        match = re.search(rf"(\b{re.escape(variable)}\b\s*(\\in|=|\\subseteq).*)", typeok)
        if not match:
            return f"typeok_missing_variable_domain_{variable}"
        clause = match.group(1)
        if re.search(rf"\b{re.escape(variable)}\b\s*\\in\s*(Nat|Int)\b", clause):
            return f"typeok_infinite_builtin_domain_{variable}"
    if _typeok_init_state_space_too_large(src):
        return "typeok_init_state_space_too_large"
    return None


def _tlaps_parser_incompatibility(src: str) -> str | None:
    if _TLAPS_TUPLE_BINDER_RE.search(src):
        return "tlaps_tuple_binder_parse_incompatible"
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


def progress_summary(
    rows: list[dict],
    *,
    job_id: str | None = None,
    discovered_paths: list[Path] | None = None,
) -> dict:
    statuses = Counter(row.get("status", "unknown") for row in rows)
    last_row = rows[-1] if rows else {}
    next_module_path = None
    if discovered_paths is not None and len(rows) < len(discovered_paths):
        next_module_path = str(discovered_paths[len(rows)])
    return {
        "job_id": job_id,
        "rows_so_far": len(rows),
        "modules_seen": len({row.get("module") for row in rows if row.get("module")}),
        "statuses": dict(sorted(statuses.items())),
        "last_completed_module_path": last_row.get("module_path"),
        "last_completed_status": last_row.get("status"),
        "next_module_path": next_module_path,
    }


def write_progress_summary(
    path: Path,
    rows: list[dict],
    *,
    job_id: str | None = None,
    discovered_paths: list[Path] | None = None,
) -> None:
    payload = progress_summary(rows, job_id=job_id, discovered_paths=discovered_paths)
    payload["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["source"] = "scripts/autoprover_smoke.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    sany = validate_sany_string(src, module_name=module)
    if not sany.valid:
        row["sany_errors"] = sany.errors[:5]
        row.update(
            status="skipped",
            reason="sany_parse_or_semantic_invalid",
            runtime_seconds=round(time.time() - started, 3),
        )
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

    tlaps_parse_issue = _tlaps_parser_incompatibility(src)
    if tlaps_parse_issue:
        row.update(status="skipped", reason=tlaps_parse_issue, runtime_seconds=round(time.time() - started, 3))
        return row

    tlapm = _tlapm_path()
    if not tlapm:
        row.update(status="no_tlapm", runtime_seconds=round(time.time() - started, 3))
        return row

    try:
        result = validate_tlaps_string(
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
    parser.add_argument("--progress-out", type=Path)
    parser.add_argument("--progress-job-id")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.module_list:
        paths = _discover_from_module_lists(args.module_list, args.limit)
    else:
        paths = _discover(args.globs or _default_globs(), args.limit)

    summary: dict[str, int] = {"discovered": len(paths)}
    progress_rows: list[dict] = []
    with out_path.open("w", encoding="utf-8") as out:
        for path in paths:
            row = run_one(
                path,
                tlc_timeout=args.tlc_timeout,
                tlapm_timeout=args.tlapm_timeout,
                run_tlaps=not args.skip_tlaps,
            )
            summary[row["status"]] = summary.get(row["status"], 0) + 1
            progress_rows.append(row)
            out.write(json.dumps(row) + "\n")
            out.flush()
            if args.progress_out:
                write_progress_summary(
                    args.progress_out,
                    progress_rows,
                    job_id=args.progress_job_id,
                    discovered_paths=paths,
                )
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
