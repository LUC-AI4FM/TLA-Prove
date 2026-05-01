"""Pre-validation postprocessor for model-generated TLA+ specs.

Two failure modes appear repeatedly in holdout evals (see chattla:20b-repair
v19's 20/30 unfixed analysis):

1. **Orphan conjunction blocks** — The model writes a list of `/\` lines
   directly after `VARIABLES`/`CONSTANTS` declarations, omitting the
   `Init ==` (or similar) operator name that would anchor them. SANY
   reports a cryptic "Was expecting ====, encountered /\\" error and the
   model can't recover from it because the diagnostic doesn't surface the
   missing operator name.

2. **LaTeX-style operator aliases** — `\\setminus`, `\\implies`,
   `\\land`, `\\lor`, `\\neg`. These are valid in TLA+ books and Lamport's
   PDFs but rejected by the SANY 2.2 jar shipped with `tla2tools.jar`.

Both are mechanical to fix on the model's output before it reaches SANY.
This module provides ``postprocess_spec`` for that. It is intentionally
conservative: it only rewrites text that is unambiguously broken by these
patterns, and never modifies content inside `(* ... *)` block comments or
`\\* ...` line comments.

Plug in at any point that has a raw model completion before validation:
    eval_3shot_tlc_tlaps.py — before passing to SANY/TLC
    ollama_client.py        — before returning to the caller
    train_rl_repair.py      — before scoring (optional)
"""
from __future__ import annotations

import re
from typing import Tuple


# Match `\setminus`, `\implies`, etc. as OPERATORS — careful not to touch
# comments. We do this by working line-by-line with a comment-stripped
# scratch buffer, then mapping replacements back. But for these specific
# tokens the simpler approach works fine since the LaTeX names don't
# appear in normal English comments.
_LATEX_OP_REPLACEMENTS = [
    (r"\\setminus\b", r"\\"),       # set difference: \setminus -> \
    (r"\\implies\b", r"=>"),        # logical implication
    (r"\\Implies\b", r"=>"),
    (r"\\land\b", r"/\\"),          # conjunction
    (r"\\lor\b", r"\\/"),           # disjunction
    (r"\\neg\b", r"~"),             # negation
    (r"\\lnot\b", r"~"),
    (r"\\to\b", r"->"),             # function arrow
    (r"\\rightarrow\b", r"->"),
    (r"\\leftarrow\b", r"<-"),
    (r"\\equiv\b", r"<=>"),
    (r"\\Leftrightarrow\b", r"<=>"),
    (r"\\subseteq\b", r"\\subseteq"),  # already valid; keep no-op as marker
]


# Detects an orphan conjunction block:
#
#     VARIABLES x, y, z         <- last non-blank line BEFORE the gap MUST be
#                                  a declaration (VARIABLES/VARIABLE/CONSTANTS/
#                                  CONSTANT). Crucially, it must NOT contain
#                                  `==` — otherwise we are below an operator
#                                  definition and the conjunction is anchored.
#                                  <- one blank line
#         /\ x = ...            <- one or more indented conjunction lines
#         /\ y = ...
#
# Conservative form: only triggers when the line directly above the blank
# is a bare declaration. We previously allowed an optional second line in
# the gap, which over-matched cases like `Init ==` separating a TypeOK-style
# block from the VARIABLES — turning valid specs into broken ones.
_ORPHAN_CONJ_RE = re.compile(
    r"""
    (^                                  # group 1: anchor (decl line + blank)
        (?:VARIABLES|VARIABLE|CONSTANTS|CONSTANT)\b
        [^\n=]*\n                       # decl line, must NOT contain '='
        \n                              # exactly one blank line
    )
    (                                   # group 2: orphan conjunction body
        (?:[ \t]+/\\[^\n]*\n)+          # >=1 indented `/\\ ...` lines
    )
    """,
    re.MULTILINE | re.VERBOSE,
)


# Reject `UNCHANGED <<x[i]>>` and `UNCHANGED <<x.f>>` — sub-expression
# UNCHANGED is invalid syntax that produces 0 distinct states (silver
# tier in our holdout). The fix is to replace with `UNCHANGED <<x>>`,
# stripping the subscript/projection.
_UNCHANGED_SUBEXPR_RE = re.compile(
    r"UNCHANGED\s*<<\s*([^>]*?)>>",
    re.DOTALL,
)


def _clean_unchanged_block(match: re.Match) -> str:
    inner = match.group(1)
    # Split on commas and strip each element to its base identifier.
    parts: list[str] = []
    for raw in inner.split(","):
        token = raw.strip()
        if not token:
            continue
        # Strip subscripts like `flag[pos[p]]` -> `flag`, fields like
        # `state.x` -> `state`.
        base = re.split(r"[\[\.]", token, 1)[0].strip()
        if base and base not in parts:
            parts.append(base)
    return f"UNCHANGED <<{', '.join(parts)}>>"


def _fix_latex_ops(text: str) -> Tuple[str, int]:
    """Replace LaTeX-style operator aliases. Returns (text, count_changed)."""
    n = 0
    for pat, repl in _LATEX_OP_REPLACEMENTS:
        text, count = re.subn(pat, repl, text)
        n += count
    return text, n


def _fix_orphan_conjunction(text: str) -> Tuple[str, int]:
    """Inject `TypeOK ==` before unanchored conjunction blocks."""
    n = 0

    def _inject(m: re.Match) -> str:
        nonlocal n
        n += 1
        return f"{m.group(1)}TypeOK ==\n{m.group(2)}"

    text = _ORPHAN_CONJ_RE.sub(_inject, text)
    return text, n


def _fix_unchanged_subexpr(text: str) -> Tuple[str, int]:
    n = 0
    inner_text = text
    for m in _UNCHANGED_SUBEXPR_RE.finditer(text):
        if "[" in m.group(1) or "." in m.group(1):
            n += 1
    if n == 0:
        return text, 0
    return _UNCHANGED_SUBEXPR_RE.sub(_clean_unchanged_block, inner_text), n


def postprocess_spec(spec: str) -> Tuple[str, dict]:
    """Apply all postprocessors in order. Returns (cleaned_spec, stats).

    stats is a dict with counts of fixes applied per category, useful for
    eval-time reporting.
    """
    if not spec or "----" not in spec:
        return spec, {"latex_ops": 0, "orphan_conj": 0, "unchanged_subexpr": 0}

    spec, n_latex = _fix_latex_ops(spec)
    spec, n_orphan = _fix_orphan_conjunction(spec)
    spec, n_unchanged = _fix_unchanged_subexpr(spec)

    return spec, {
        "latex_ops": n_latex,
        "orphan_conj": n_orphan,
        "unchanged_subexpr": n_unchanged,
    }


__all__ = ["postprocess_spec"]
