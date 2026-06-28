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
    next_def = re.search(r"^\s*[A-Za-z_]\w*(?:\([^)]*\))?\s*==", module_src[start:], re.MULTILINE)
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


def _helper_conjunct_name(clause: str) -> str | None:
    match = re.match(r"^\s*(?:/\\\s*)?([A-Za-z_]\w*)\s*$", clause)
    return match.group(1) if match else None


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


def _enumerable_type_bound_expr(module_src: str) -> str | None:
    if not _defines_operator(module_src, _TYPE_BOUND_NAME):
        return None
    typeok = _operator_body(module_src, _TYPE_BOUND_NAME)
    if not typeok:
        return None
    clauses = _split_top_level_conjuncts(typeok)
    seq_len_bounds = {
        variable: _seq_len_upper_bound(module_src, clauses, variable)
        for variable in _declared_variables(module_src)
    }
    seen_direct_domains: set[str] = set()
    rewritten: list[str] = []
    declared = _declared_variables(module_src)
    for clause in clauses:
        stripped = clause.strip()
        rewritten.append(stripped)
        for variable in declared:
            if re.search(rf"\b{re.escape(variable)}\b\s*(\\in|=|\\subseteq)", stripped):
                seen_direct_domains.add(variable)
                rewritten[-1] = _rewrite_enumerable_clause(variable, stripped, seq_len_bounds.get(variable))
                if rewritten[-1] is None:
                    return None
                break
    if any(variable not in seen_direct_domains for variable in declared):
        return None
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
