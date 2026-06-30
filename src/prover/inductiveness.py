"""inductiveness.py — TLC-based inductive-invariant checker (the CEGIS oracle).

This is the core decision procedure of the ChatTLA v2 TLAPS proof-search loop.
Given a TLA+ module and the name of a candidate invariant, it decides whether
that invariant is *inductive* for the spec's ``Next`` action, i.e.

    Inv /\\ [Next]_vars => Inv'

If the invariant is not inductive, TLC produces a counterexample-to-induction
(CTI): a pair of states ``s -> s'`` where ``Inv(s)`` holds but ``Inv(s')`` does
not.  CEGIS uses this trace to strengthen the proposed invariant and retry.

Encoding (the standard TLC inductive-invariant trick)
-----------------------------------------------------
We do NOT use ``Init`` as the initial predicate.  Conceptually the .cfg is::

    INIT  <inv_name>
    NEXT  Next
    INVARIANT <inv_name>

``INIT <inv_name>`` tells TLC to start from *every* state satisfying the
candidate invariant, ``NEXT Next`` takes a single step, and
``INVARIANT <inv_name>`` checks the invariant still holds in the successor.  A
clean run proves the inductive step; an invariant violation is exactly a CTI.

Enumerability caveat / why we generate a helper INIT operator
-------------------------------------------------------------
TLC can only use a predicate as an INIT if it can *enumerate* the states that
satisfy it — i.e. the predicate must pin every variable to a finite domain
(e.g. ``x \\in 0..3``).  A candidate invariant like ``Bad == x < 3`` *constrains*
``x`` but never gives TLC a domain to enumerate, so ``INIT Bad`` fails with
"the identifier x is either undefined or not an operator".

To stay enumerable we synthesise a helper operator appended to the module::

    <INIT_OP> == TypeOK /\\ <inv_name>

and point ``INIT`` at it, while ``INVARIANT`` still names the candidate
invariant.  ``TypeOK`` (when the module defines it) supplies the finite domain;
the conjunction restricts to Inv-states.  If no ``TypeOK`` exists we fall back to
``INIT <inv_name>`` directly and rely on the invariant itself being enumerable.

We mirror ``src/validators/tlc_validator.py``: same jar discovery
(``_TLA_TOOLS_JAR``), same ``java -cp <jar> tlc2.TLC -config <cfg> <tla>``
invocation, same temp-dir + stdout-parsing strategy (TLC exit codes are not
reliable across versions).
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Reuse the repo's jar discovery rather than reinventing it.
from src.validators.sany_validator import _TLA_TOOLS_JAR
from src.validators.tlc_validator import _extract_constant_names, _infer_constant_type

_DEFAULT_JAR = _TLA_TOOLS_JAR
_MODULE_RE = re.compile(r"-{4,}\s*MODULE\s+(\w+)", re.IGNORECASE)
_MODULE_END_RE = re.compile(r"^={4,}\s*$", re.MULTILINE)
# Name of the synthesised enumerable INIT operator. Underscore-suffixed to
# avoid colliding with anything a user-authored module is likely to define.
_IND_INIT_OP = "IndInit_ChatTLA"
# A finite type-bound operator we conjoin into INIT so TLC can enumerate.
_TYPE_BOUND_NAME = "TypeOK"


@dataclass
class InductivenessResult:
    inductive: bool
    cti: str | None = None     # the TLC counterexample trace text, when not inductive
    error: str | None = None   # tooling/parse error, if the check could not run


def check_inductive(
    module_src: str,
    inv_name: str,
    *,
    timeout: int = 90,
) -> InductivenessResult:
    """Decide whether ``inv_name`` is inductive for ``module_src``'s ``Next``.

    Parameters
    ----------
    module_src : str   Full TLA+ module source text.
    inv_name   : str   Name of the candidate invariant operator in the module.
    timeout    : int   Seconds before TLC is killed (reported as an error).

    Returns
    -------
    InductivenessResult
        ``inductive=True``  — TLC ran clean: the invariant is preserved by Next.
        ``inductive=False`` with ``cti`` — TLC found a counterexample-to-induction.
        ``inductive=False`` with ``error`` — the check could not run (parse error,
        TLC failure, timeout, missing jar, ...).
    """
    if not _DEFAULT_JAR.exists():
        return InductivenessResult(
            inductive=False,
            error=f"tla2tools.jar not found at {_DEFAULT_JAR}",
        )

    mod_match = _MODULE_RE.search(module_src)
    if not mod_match:
        return InductivenessResult(
            inductive=False,
            error="Could not parse MODULE name from source.",
        )
    module_name = mod_match.group(1)

    # Decide on an enumerable INIT predicate. If the module defines a TypeOK
    # type bound, synthesize a helper from its direct variable-domain clauses
    # so TLC can enumerate states even when TypeOK also references helper
    # predicates. When checking a non-TypeOK invariant, conjoin that invariant
    # with the enumerable type bound in the helper.
    enum_type_bound = _enumerable_type_bound_expr(module_src)
    if enum_type_bound is not None:
        init_predicate = _IND_INIT_OP
        helper_expr = enum_type_bound if inv_name == _TYPE_BOUND_NAME else f"({enum_type_bound}) /\\ {inv_name}"
        tla_text = _inject_ind_init(module_src, helper_expr)
    else:
        init_predicate = inv_name
        tla_text = module_src

    cfg_text = _build_cfg(init_predicate, inv_name, module_src)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tla_path = tmp / f"{module_name}.tla"
        cfg_path = tmp / f"{module_name}.cfg"
        tla_path.write_text(tla_text, encoding="utf-8")
        cfg_path.write_text(cfg_text, encoding="utf-8")

        cmd = [
            "java", "-cp", str(_DEFAULT_JAR),
            "tlc2.TLC",
            "-depth", "1",
            "-config", str(cfg_path),
            str(tla_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,  # TLC resolves EXTENDS / writes states relative to cwd
            )
        except subprocess.TimeoutExpired:
            return InductivenessResult(
                inductive=False,
                error=f"TLC timed out after {timeout}s "
                      "(INIT-as-predicate state space too large to enumerate).",
            )
        except Exception as exc:  # pragma: no cover - defensive
            return InductivenessResult(
                inductive=False,
                error=f"TLC invocation failed: {exc!r}",
            )

        stdout = result.stdout + result.stderr

        # Tooling failure (SANY parse error, bad cfg, non-enumerable INIT, etc.)
        # must be distinguished from a genuine invariant violation.
        if _is_tooling_error(stdout):
            return InductivenessResult(
                inductive=False,
                error=_extract_tooling_error(stdout),
            )

        if _invariant_violated(stdout):
            # Not inductive: capture the printed counterexample-to-induction.
            return InductivenessResult(
                inductive=False,
                cti=_extract_cti(stdout) or stdout.strip(),
            )

        if _completed_clean(stdout):
            return InductivenessResult(inductive=True)

        # TLC neither violated the invariant nor reported clean success and we
        # could not classify the output as a tooling error — surface the raw
        # output so the caller can diagnose rather than silently trusting it.
        return InductivenessResult(
            inductive=False,
            error="TLC produced no conclusive result:\n" + stdout.strip(),
        )


# ---------------------------------------------------------------------------
# cfg generation
# ---------------------------------------------------------------------------

def _build_cfg(init_predicate: str, inv_name: str, module_src: str = "") -> str:
    """Build the inductive-step .cfg: start from all Inv-states, step once, recheck.

    ``init_predicate`` is the (possibly synthesised, enumerable) operator used as
    INIT; ``inv_name`` is the candidate invariant checked after one Next step.
    This is the standard TLC encoding of the inductive step
    Inv /\\ [Next]_vars => Inv'.
    """
    lines = [
        f"INIT {init_predicate}",
        "NEXT Next",
        "CHECK_DEADLOCK FALSE",
        f"INVARIANT {inv_name}",
    ]
    for name in _extract_constant_names(module_src):
        lines.append(_infer_constant_type(name, module_src))
    return "\n".join(lines) + "\n"


def _defines_operator(module_src: str, name: str) -> bool:
    """True if the module defines a top-level operator ``name == ...``."""
    return bool(re.search(rf"^\s*{re.escape(name)}\s*==", module_src, re.MULTILINE))


def _operator_body(module_src: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}\s*==", module_src, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_def = re.search(r"^[ \t]*[A-Za-z_]\w*(?:\([^)]*\))?[ \t]*==", module_src[start:], re.MULTILINE)
    end_match = _MODULE_END_RE.search(module_src[start:])
    candidates = [len(module_src)]
    if next_def:
        candidates.append(start + next_def.start())
    if end_match:
        candidates.append(start + end_match.start())
    return module_src[start:min(candidates)]


def _declared_variables(module_src: str) -> list[str]:
    lines = module_src.splitlines()
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


def _split_top_level_conjuncts(body: str) -> list[str]:
    filtered_lines = [
        line for line in body.splitlines() if line.strip() and not line.strip().startswith("\\*")
    ]
    if not filtered_lines:
        return []
    chunks: list[str] = []
    current: list[str] = []
    previous = ""
    for line in filtered_lines:
        stripped = line.strip()
        if current and stripped.startswith("/\\") and not previous.rstrip().endswith(":"):
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
        previous = stripped
    if current:
        chunks.append("\n".join(current).strip())
    clauses: list[str] = []
    for chunk in chunks:
        for part in _split_top_level(chunk, "/\\"):
            stripped = part.strip()
            if not stripped:
                continue
            if not stripped.startswith("/\\"):
                stripped = f"/\\ {stripped}"
            clauses.append(stripped)
    return clauses


def _normalize_expr(expr: str) -> str:
    return " ".join(line.strip() for line in expr.splitlines() if line.strip())


def _normalize_noncomment_expr(expr: str) -> str:
    return " ".join(
        line.strip()
        for line in expr.splitlines()
        if line.strip() and not line.strip().startswith("\\*")
    )


def _split_top_level(expr: str, token: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    quantifier_depths: list[tuple[int, int, int]] = []
    pending_quantifier = False
    i = 0
    while i < len(expr):
        if (
            expr.startswith(token, i)
            and depth_paren == depth_brace == depth_bracket == 0
            and not quantifier_depths
        ):
            parts.append("".join(current).strip())
            current = []
            i += len(token)
            continue
        if expr.startswith("\\A", i) or expr.startswith("\\E", i):
            prev = expr[i - 1] if i > 0 else ""
            next_ch = expr[i + 2] if i + 2 < len(expr) else ""
            if (not prev or not (prev.isalnum() or prev == "_")) and (
                not next_ch or not (next_ch.isalnum() or next_ch == "_")
            ):
                pending_quantifier = True
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
        elif ch == ":" and pending_quantifier:
            quantifier_depths.append((depth_paren, depth_brace, depth_bracket))
            pending_quantifier = False
        current.append(ch)
        while quantifier_depths:
            quant_paren, quant_brace, quant_bracket = quantifier_depths[-1]
            if (
                depth_paren < quant_paren
                or depth_brace < quant_brace
                or depth_bracket < quant_bracket
            ):
                quantifier_depths.pop()
                continue
            break
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


def _simple_definitions(module_src: str) -> dict[str, str]:
    defs: dict[str, str] = {}
    for line in module_src.splitlines():
        match = re.match(r"^\s*([A-Za-z_]\w*)\s*==\s*(.+?)\s*$", line)
        if not match:
            continue
        defs[match.group(1)] = re.sub(r"\s*\\\*.*$", "", match.group(2)).strip()
    return defs


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


def _expand_helper_conjuncts(
    module_src: str,
    clauses: list[str],
    seen_helpers: set[str] | None = None,
) -> list[str]:
    if seen_helpers is None:
        seen_helpers = set()
    expanded: list[str] = []
    for clause in clauses:
        stripped = clause.strip()
        helper = _helper_conjunct_name(stripped)
        if helper and helper not in seen_helpers:
            body = _operator_body(module_src, helper)
            if body:
                expanded.extend(
                    _expand_helper_conjuncts(
                        module_src,
                        _split_top_level_conjuncts(body),
                        seen_helpers | {helper},
                    )
                )
                continue
        expanded.append(stripped)
    return expanded


def _simple_function_definition(expr: str) -> tuple[str, str, str] | None:
    match = re.fullmatch(r"\[\s*([A-Za-z_]\w*)\s+\\in\s+(.+?)\s+\|->\s+(.+)\s*\]", _normalize_expr(expr))
    if not match:
        return None
    return (
        match.group(1),
        _normalize_expr(match.group(2)),
        _normalize_expr(match.group(3)),
    )


def _simplify_binder_indexed_expr(
    expr: str, binder_domains: dict[str, str], defs: dict[str, str]
) -> str:
    simplified = _normalize_expr(expr)
    changed = True
    while changed:
        changed = False
        for name, definition in defs.items():
            parsed = _simple_function_definition(definition)
            if parsed is None:
                continue
            formal, domain, body = parsed
            pattern = rf"\b{re.escape(name)}\[\s*([A-Za-z_]\w*)\s*\]"

            def replace_named(match: re.Match[str]) -> str:
                nonlocal changed
                actual = match.group(1)
                if binder_domains.get(actual) != domain:
                    return match.group(0)
                changed = True
                return f"({body})"

            simplified = re.sub(pattern, replace_named, simplified)

        literal_match = re.search(
            r"\(\[\s*([A-Za-z_]\w*)\s+\\in\s+(.+?)\s+\|->\s+(.+?)\s*\]\)\[\s*([A-Za-z_]\w*)\s*\]",
            simplified,
        )
        if literal_match:
            formal = literal_match.group(1)
            domain = _normalize_expr(literal_match.group(2))
            body = _normalize_expr(literal_match.group(3))
            actual = literal_match.group(4)
            if binder_domains.get(actual) == domain:
                simplified = (
                    simplified[: literal_match.start()]
                    + f"({body})"
                    + simplified[literal_match.end() :]
                )
                changed = True
    return _normalize_expr(simplified)


def _pointwise_function_domain_clauses(
    clause: str, variables: list[str], defs: dict[str, str]
) -> list[str]:
    normalized = clause.strip()
    match = re.match(
        rf"^\s*/\\\s*\\A\s+(.+?)\s*:\s*(.+)$",
        normalized,
        re.DOTALL,
    )
    if not match:
        return []
    binders: list[str] = []
    binder_domains: dict[str, str] = {}
    for part in _split_top_level(match.group(1), ","):
        binder_match = re.match(r"^\s*([A-Za-z_]\w*)\s+\\in\s+(.+?)\s*$", part)
        if not binder_match:
            return []
        binder = binder_match.group(1)
        binders.append(binder)
        binder_domains[binder] = _normalize_expr(binder_match.group(2))
    body = match.group(2)
    conjuncts = [part.strip() for part in _split_top_level(body, "/\\") if part.strip()]
    results: list[str] = []
    access_suffix = "".join(rf"\[\s*{re.escape(binder)}\s*\]" for binder in binders)
    for variable in variables:
        for conjunct in conjuncts:
            body_match = re.match(
                rf"^{re.escape(variable)}{access_suffix}\s*\\in\s*(.+)$",
                conjunct,
                re.DOTALL,
            )
            if body_match:
                rng = _simplify_binder_indexed_expr(body_match.group(1), binder_domains, defs)
                nested = rng
                for binder in reversed(binders):
                    nested = f"[{binder_domains[binder]} -> {nested}]"
                results.append(f"/\\ {variable} \\in {nested}")
                break
    return results


def _augment_with_pointwise_function_domains(module_src: str, clauses: list[str]) -> list[str]:
    declared = _declared_variables(module_src)
    defs = _simple_definitions(module_src)
    augmented = list(clauses)
    seen = set(augmented)
    for clause in clauses:
        for rewritten in _pointwise_function_domain_clauses(clause, declared, defs):
            if rewritten not in seen:
                augmented.append(rewritten)
                seen.add(rewritten)
    return augmented


def _direct_in_domains(clauses: list[str], variables: list[str]) -> dict[str, str]:
    direct: dict[str, str] = {}
    for clause in clauses:
        stripped = clause.strip()
        for variable in variables:
            match = re.search(
                rf"^\s*/\\\s*{re.escape(variable)}\s*\\in\s*(.+)$",
                stripped,
                re.DOTALL,
            )
            if match:
                direct[variable] = _normalize_expr(
                    re.sub(r"\s*\\\*.*$", "", match.group(1), flags=re.MULTILINE)
                )
                break
    return direct


def _has_direct_domain_clause(variable: str, clauses: list[str]) -> bool:
    pattern = rf"^\s*/\\\s*{re.escape(variable)}\s*(\\in|=|\\subseteq)\s*(.+)$"
    return any(re.search(pattern, clause, re.DOTALL) for clause in clauses)


def _range_upper_bound_expr(domain: str) -> str | None:
    match = re.fullmatch(r"(.+)\.\.(.+)", _normalize_expr(domain))
    if not match:
        return None
    start_expr = _strip_wrapping_parens(match.group(1))
    if start_expr != "0":
        return None
    return _normalize_expr(match.group(2))


def _quantifier_domain_map(module_src: str) -> dict[str, str]:
    candidates: dict[str, list[str]] = {}
    for line in module_src.splitlines():
        for quantifier in ("\\A", "\\E"):
            start = line.find(quantifier)
            if start < 0:
                continue
            tail = line[start + len(quantifier) :]
            colon = tail.find(":")
            if colon < 0:
                continue
            prefix = tail[:colon]
            for part in _split_top_level(prefix, ","):
                match = re.match(r"^\s*([A-Za-z_]\w*)\s+\\in\s+(.+?)\s*$", part)
                if match:
                    candidates.setdefault(match.group(1), []).append(_normalize_expr(match.group(2)))
    domains: dict[str, str] = {}
    candidate_names = set(candidates)
    for name, values in candidates.items():
        ranked = sorted(
            dict.fromkeys(values),
            key=lambda domain: (
                any(token in candidate_names for token in re.findall(r"[A-Za-z_]\w*", domain)),
                len(domain),
            ),
        )
        domains[name] = ranked[0]
    return domains


def _singleton_set_elements(expr: str) -> list[str]:
    elements: list[str] = []
    for match in re.finditer(r"\{([^{}]+)\}", expr):
        inner = match.group(1).strip()
        if inner:
            elements.append(inner)
    return elements


def _free_quantified_identifiers(expr: str, quantifier_domains: dict[str, str]) -> list[str]:
    field_names = set(re.findall(r"([A-Za-z_]\w*)\s*\|->", expr))
    ordered: list[str] = []
    for token in re.findall(r"[A-Za-z_]\w*", expr):
        if token in field_names or token not in quantifier_domains or token in ordered:
            continue
        ordered.append(token)
    return ordered


def _set_builder_expr(expr: str, quantifier_domains: dict[str, str]) -> str:
    vars_in_expr = _free_quantified_identifiers(expr, quantifier_domains)
    if not vars_in_expr:
        return f"{{{expr}}}"
    built = f"{{{expr} : {vars_in_expr[-1]} \\in {quantifier_domains[vars_in_expr[-1]]}}}"
    for name in reversed(vars_in_expr[:-1]):
        built = f"(UNION {{ {built} : {name} \\in {quantifier_domains[name]} }})"
    return built


def _shifted_range_expr(domain: str, delta: int) -> str | None:
    match = re.fullmatch(r"(.+)\.\.(.+)", _normalize_expr(domain))
    if not match:
        return None
    start = _strip_wrapping_parens(match.group(1))
    end = _strip_wrapping_parens(match.group(2))
    if delta == 0:
        return f"{start}..{end}"
    if re.fullmatch(r"\d+", start):
        shifted_start = str(int(start) + delta)
    else:
        shifted_start = f"({start} + {delta})"
    if re.fullmatch(r"\d+", end):
        shifted_end = str(int(end) + delta)
    else:
        shifted_end = f"({end} + {delta})"
    return f"{shifted_start}..{shifted_end}"


def _append_element_domain_expr(
    expr: str,
    scalar_domains: dict[str, str],
    sequence_elem_domains: dict[str, str],
) -> str | None:
    normalized = _normalize_expr(expr)
    if re.fullmatch(r"\d+", normalized):
        return f"{normalized}..{normalized}"
    if normalized in scalar_domains:
        return scalar_domains[normalized]
    if head_match := re.fullmatch(r"Head\(\s*([A-Za-z_]\w*)\s*\)", normalized):
        return sequence_elem_domains.get(head_match.group(1))
    shift_match = re.fullmatch(r"([A-Za-z_]\w*)\s*([+-])\s*(\d+)", normalized)
    if not shift_match:
        return None
    base_name, sign, amount_text = shift_match.groups()
    base_domain = scalar_domains.get(base_name)
    if base_domain is None:
        return None
    amount = int(amount_text)
    return _shifted_range_expr(base_domain, amount if sign == "+" else -amount)


def _union_domain_expr(domains: list[str]) -> str:
    unique: list[str] = []
    for domain in domains:
        normalized = _normalize_expr(domain)
        if normalized not in unique:
            unique.append(normalized)
    if len(unique) == 1:
        return unique[0]
    return " \\cup ".join(f"({domain})" for domain in unique)


def _case_result_domain_expr(
    expr: str,
    scalar_domains: dict[str, str],
    quantifier_domains: dict[str, str],
) -> str | None:
    normalized = _normalize_expr(expr)
    if not normalized.startswith("CASE "):
        return None
    domains: list[str] = []
    for part in _split_top_level(normalized[len("CASE ") :], "[]"):
        if "->" not in part:
            continue
        _, rhs = part.split("->", 1)
        domain = _value_domain_expr(rhs.strip(), scalar_domains, quantifier_domains)
        if domain is not None:
            domains.append(domain)
    return _union_domain_expr(domains) if domains else None


def _value_domain_expr(
    expr: str,
    scalar_domains: dict[str, str],
    quantifier_domains: dict[str, str],
) -> str | None:
    normalized = _normalize_expr(expr)
    if not normalized:
        return None
    case_domain = _case_result_domain_expr(normalized, scalar_domains, quantifier_domains)
    if case_domain is not None:
        return case_domain
    if re.fullmatch(r'"[^"]+"', normalized):
        return f"{{{normalized}}}"
    if normalized in {"TRUE", "FALSE"}:
        return f"{{{normalized}}}"
    if re.fullmatch(r"\d+", normalized):
        return f"{normalized}..{normalized}"
    if normalized in scalar_domains:
        return scalar_domains[normalized]
    if normalized in quantifier_domains:
        return quantifier_domains[normalized]
    if re.fullmatch(r"[A-Za-z_]\w*", normalized):
        return f"{{{normalized}}}"
    return None


def _init_assignment_expr(module_src: str, variable: str) -> str | None:
    for clause in _split_top_level_conjuncts(_operator_body(module_src, "Init")):
        match = re.match(rf"^\s*/\\\s*{re.escape(variable)}\s*=\s*(.+)$", clause, re.DOTALL)
        if match:
            return _normalize_expr(match.group(1))
    return None


def _function_update_range_domains(
    module_src: str,
    variable: str,
    scalar_domains: dict[str, str],
    quantifier_domains: dict[str, str],
) -> list[str]:
    domains: list[str] = []
    pattern = rf"\b{re.escape(variable)}'\s*=\s*\[{re.escape(variable)}\s+EXCEPT\s+!\[[^\]]+\]\s*=\s*([^\]\n]+)"
    for match in re.finditer(pattern, module_src, re.MULTILINE):
        domain = _value_domain_expr(match.group(1), scalar_domains, quantifier_domains)
        if domain is not None:
            domains.append(domain)
    return domains


def _inferred_function_domain_clause(
    module_src: str,
    variable: str,
    scalar_domains: dict[str, str],
    quantifier_domains: dict[str, str],
) -> str | None:
    init_expr = _init_assignment_expr(module_src, variable)
    if init_expr is None:
        return None
    parsed = _simple_function_definition(init_expr)
    if parsed is None:
        return None
    _formal, domain, body = parsed
    range_domains: list[str] = []
    init_range_domain = _value_domain_expr(body, scalar_domains, quantifier_domains)
    if init_range_domain is not None:
        range_domains.append(init_range_domain)
    range_domains.extend(_function_update_range_domains(module_src, variable, scalar_domains, quantifier_domains))
    if not range_domains:
        return None
    return f"/\\ {variable} \\in [{_normalize_expr(domain)} -> {_union_domain_expr(range_domains)}]"


def _operational_domain_clauses(module_src: str, clauses: list[str]) -> list[str]:
    declared = _declared_variables(module_src)
    direct_domains = _direct_in_domains(clauses, declared)
    direct_variables = {
        variable for variable in declared if _has_direct_domain_clause(variable, clauses)
    }
    quantifier_domains = _quantifier_domain_map(module_src)
    inferred: list[str] = []
    seen = set(clauses)

    for variable in declared:
        if variable in direct_variables:
            continue
        clause = _inferred_function_domain_clause(module_src, variable, direct_domains, quantifier_domains)
        if clause and clause not in seen:
            inferred.append(clause)
            seen.add(clause)

    for variable in declared:
        if variable in direct_variables:
            continue
        if re.search(rf"\b{re.escape(variable)}\s*=\s*\{{\s*\}}", _operator_body(module_src, "Init")):
            builders: list[str] = []
            for update_match in re.finditer(
                rf"\b{re.escape(variable)}'\s*=\s*(.+)$",
                module_src,
                re.MULTILINE,
            ):
                for element in _singleton_set_elements(update_match.group(1)):
                    builders.append(_set_builder_expr(element, quantifier_domains))
            if builders:
                clause = f"/\\ {variable} \\subseteq ({_union_domain_expr(builders)})"
                if clause not in seen:
                    inferred.append(clause)
                    seen.add(clause)

    scalar_domains = _direct_in_domains(clauses + inferred, declared)
    sequence_elem_domains: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for variable in declared:
            if variable in direct_variables or variable in sequence_elem_domains:
                continue
            if not re.search(
                rf"\b{re.escape(variable)}\s*=\s*<<\s*>>", _operator_body(module_src, "Init")
            ):
                continue
            domains: list[str] = []
            for update_match in re.finditer(
                rf"\b{re.escape(variable)}'\s*=\s*Append\(\s*{re.escape(variable)}\s*,\s*(.+?)\s*\)\s*$",
                module_src,
                re.MULTILINE,
            ):
                domain = _append_element_domain_expr(
                    update_match.group(1), scalar_domains, sequence_elem_domains
                )
                if domain is not None:
                    domains.append(domain)
            if domains:
                elem_domain = _union_domain_expr(domains)
                clause = f"/\\ {variable} \\in Seq({elem_domain})"
                if clause not in seen:
                    inferred.append(clause)
                    seen.add(clause)
                    changed = True
                sequence_elem_domains[variable] = elem_domain
    return inferred


def _augment_with_inferred_domains(module_src: str, clauses: list[str]) -> list[str]:
    augmented = _augment_with_pointwise_function_domains(module_src, clauses)
    inferred = _operational_domain_clauses(module_src, augmented)
    return augmented + [clause for clause in inferred if clause not in augmented]


def _seq_len_upper_bound(
    module_src: str,
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
            body = _operator_body(module_src, helper)
            if body:
                bound = _seq_len_upper_bound(
                    module_src,
                    _split_top_level_conjuncts(body),
                    variable,
                    seen_helpers | {helper},
                )
                if bound is not None:
                    return bound
    return None


def _is_strictly_increasing_sequence(
    module_src: str,
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
            body = _operator_body(module_src, helper)
            if body and _is_strictly_increasing_sequence(
                module_src,
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


def _seq_len_upper_bounds(module_src: str, clauses: list[str]) -> dict[str, str]:
    variables = _declared_variables(module_src)
    typeok = _operator_body(module_src, _TYPE_BOUND_NAME)
    defs = _simple_definitions(module_src)
    scalar_domains = _direct_in_domains(clauses, variables)
    bounds = {
        variable: bound
        for variable in variables
        if (bound := _seq_len_upper_bound(module_src, clauses, variable)) is not None
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
        for clause in clauses:
            for variable in variables:
                if variable in bounds:
                    continue
                patterns = (
                    rf"^\s*(?:/\\\s*)?Len\(\s*{re.escape(variable)}\s*\)\s*=\s*([A-Za-z_]\w*)\s*$",
                    rf"^\s*(?:/\\\s*)?([A-Za-z_]\w*)\s*=\s*Len\(\s*{re.escape(variable)}\s*\)\s*$",
                )
                for pattern in patterns:
                    match = re.match(pattern, clause.strip())
                    if not match:
                        continue
                    upper = _range_upper_bound_expr(scalar_domains.get(match.group(1), ""))
                    if upper is not None:
                        bounds[variable] = upper
                        changed = True
                        break
        for variable in variables:
            if variable in bounds:
                continue
            domain = _seq_domain_expr(typeok, variable)
            if not domain or not _is_strictly_increasing_sequence(module_src, clauses, variable):
                continue
            domain_bound = _domain_cardinality_bound_expr(domain, defs)
            if domain_bound is None:
                continue
            bounds[variable] = domain_bound
            changed = True
    return bounds


def _enumerable_type_bound_expr(module_src: str) -> str | None:
    if not _defines_operator(module_src, _TYPE_BOUND_NAME):
        return None
    typeok = _operator_body(module_src, _TYPE_BOUND_NAME)
    if not typeok:
        return None
    clauses = _augment_with_inferred_domains(
        module_src, _expand_helper_conjuncts(module_src, _split_top_level_conjuncts(typeok))
    )
    seq_len_bounds = _seq_len_upper_bounds(module_src, clauses)
    seen_direct_domains: set[str] = set()
    rewritten: list[str] = []
    declared = _declared_variables(module_src)
    for clause in clauses:
        stripped = clause.strip()
        rewritten_clause = stripped
        for variable in declared:
            if re.search(rf"\b{re.escape(variable)}\b\s*(\\in|=|\\subseteq)", stripped):
                seen_direct_domains.add(variable)
                rewritten_clause = _rewrite_enumerable_clause(
                    variable, stripped, seq_len_bounds.get(variable)
                )
                if rewritten_clause is None:
                    return None
                break
        rewritten.append(rewritten_clause)
    if any(variable not in seen_direct_domains for variable in declared):
        return None
    direct_clauses = [clause for clause in rewritten if _is_direct_variable_domain_clause(clause, declared)]
    other_clauses = [clause for clause in rewritten if not _is_direct_variable_domain_clause(clause, declared)]
    rewritten = direct_clauses + other_clauses
    return "\n".join(rewritten)


def _rewrite_enumerable_clause(variable: str, clause: str, seq_len_upper_bound: str | None) -> str | None:
    subseteq = re.search(rf"^\s*/\\\s*{re.escape(variable)}\s*\\subseteq\s*(.+)$", clause, re.MULTILINE)
    if subseteq:
        rhs = " ".join(part.strip() for part in subseteq.group(1).splitlines() if part.strip())
        return f"/\\ {variable} \\in (SUBSET ({rhs}))"
    seq = re.search(rf"^\s*/\\\s*{re.escape(variable)}\s*\\in\s*Seq\s*\((.+)\)\s*$", clause, re.MULTILINE | re.DOTALL)
    if seq:
        if seq_len_upper_bound is None:
            return None
        rhs = _normalize_expr(re.sub(r"\s*\\\*.*$", "", seq.group(1), flags=re.MULTILINE))
        return (
            f"/\\ {variable} \\in "
            f"(UNION {{ [1..n -> ({rhs})] : n \\in 0..{seq_len_upper_bound} }})"
        )
    return clause


def _is_direct_variable_domain_clause(clause: str, declared: list[str]) -> bool:
    for variable in declared:
        if re.search(rf"^\s*/\\\s*{re.escape(variable)}\s*(\\in|=|\\subseteq)\s*(.+)$", clause, re.DOTALL):
            return True
    return False


def _inject_ind_init(module_src: str, init_expr: str) -> str:
    """Append ``<INIT_OP> == <init_expr>`` just before the module's ====.

    The helper makes INIT enumerable while still restricting the start states
    to the intended candidate-invariant region.
    """
    lines = [line.rstrip() for line in init_expr.splitlines() if line.strip()]
    if not lines:
        helper = f"{_IND_INIT_OP} == {init_expr}\n"
    else:
        helper = f"{_IND_INIT_OP} ==\n" + "".join(f"    {line}\n" for line in lines)
    m = _MODULE_END_RE.search(module_src)
    if not m:
        # No closing ==== found; append helper then a terminator.
        return module_src.rstrip() + "\n" + helper + "================================\n"
    return module_src[:m.start()] + helper + module_src[m.start():]


# ---------------------------------------------------------------------------
# Output classification (TLC exit codes are unreliable; we parse stdout)
# ---------------------------------------------------------------------------

def _invariant_violated(output: str) -> bool:
    """TLC prints 'Invariant <name> is violated.' on a CTI."""
    return bool(re.search(r"Invariant\s+\S+\s+is violated", output, re.IGNORECASE))


def _completed_clean(output: str) -> bool:
    """TLC prints 'Model checking completed. No error has been found.' on success."""
    return bool(re.search(r"no error has been found", output, re.IGNORECASE))


def _is_tooling_error(output: str) -> bool:
    """Detect parse / semantic / setup errors as opposed to invariant violations.

    An invariant violation is the *expected* not-inductive signal and must NOT
    be classified here.  Everything else that prevents a meaningful check
    (SANY parse errors, unknown operators, non-enumerable INIT predicates,
    config errors) is a tooling error.
    """
    if _invariant_violated(output):
        return False
    if _completed_clean(output):
        return False

    error_markers = (
        r"Parsing or semantic analysis failed",
        r"was not (?:successfully )?parsed",
        r"Semantic errors",
        r"\bSyntax error\b",
        r"\*\*\* Errors:",                 # SANY error block header
        r"is not a (?:valid )?TLA",
        r"Unknown operator",
        r"Error:.*could not be parsed",
        r"TLC threw an unexpected exception",
        r"could not be (?:read|found|evaluated)",
        r"In evaluation, the identifier .* is either undefined",
        r"the configuration file",
        r"Attempted to .* but .* is not enumerable",
        r"is not enumerable",
    )
    if any(re.search(m, output, re.IGNORECASE) for m in error_markers):
        return True

    # If TLC never reached the "Starting..." / "Computing initial states" phase,
    # something went wrong before model checking even began.
    started = re.search(r"(Computing initial states|Starting\.\.\.|Finished computing)", output)
    has_error_word = re.search(r"^Error:", output, re.MULTILINE)
    return bool(has_error_word and not started)


def _extract_tooling_error(output: str) -> str:
    """Pull the salient error lines from TLC/SANY output for the error field."""
    lines: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(r"(error|fail|exception|not parsed|not enumerable|undefined)",
                     stripped, re.IGNORECASE):
            # Skip the benign success summary and JVM GC warnings.
            if re.search(r"no error has been found", stripped, re.IGNORECASE):
                continue
            if re.search(r"garbage collector|UseParallelGC", stripped, re.IGNORECASE):
                continue
            lines.append(stripped)
    if lines:
        return "\n".join(lines)
    # Fall back to the whole (trimmed) output so the caller has something.
    return output.strip() or "TLC failed without producing output."


def _extract_cti(output: str) -> str | None:
    """Extract the counterexample-to-induction trace text from TLC output.

    TLC prints, after 'Invariant <name> is violated.':
        The behavior up to this point is:
        State 1: <Initial predicate>
        /\\ x = 2
        State 2: <Next ...>
        /\\ x = 3
    We return from the 'Invariant ... is violated' line through the trace.
    """
    m = re.search(r"Invariant\s+\S+\s+is violated", output, re.IGNORECASE)
    if not m:
        return None
    tail = output[m.start():]

    # Trim trailing TLC bookkeeping (state counts, fingerprint stats, timing)
    # so the CTI is the readable error trace.
    cut_markers = [
        r"\n\d+ states generated",
        r"\nThe number of states",
        r"\nProgress\(",
        r"\nFinished in ",
    ]
    end = len(tail)
    for marker in cut_markers:
        cm = re.search(marker, tail)
        if cm:
            end = min(end, cm.start())
    trace = tail[:end].strip()
    return trace or None
