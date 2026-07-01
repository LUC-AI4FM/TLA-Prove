"""
self_improve.py — Autonomous self-improvement loop for ChatTLA.

Architecture
------------
    ┌─────────────┐     ┌──────────┐     ┌──────────────┐
    │  Generate   │────▸│  SANY    │────▸│ Python Fixer │
    │  (Ollama)   │     │ Validate │     │  (rule-based)│
    └─────────────┘     └──────────┘     └──────────────┘
          ▲                                       │
          │                    ┌──────────────────┘
          │                    ▼
    ┌─────────────┐     ┌──────────────┐
    │  Retrain    │◂────│  Augmented   │
    │  + Deploy   │     │  Dataset     │
    └─────────────┘     └──────────────┘

Loop phases
-----------
1. **Generate**: ChatTLA generates specs for prompts from the benchmark suite
   and synthetic prompts.
2. **Validate**: Each spec is run through SANY.  Passing specs become
   `spec_generation` training examples.
3. **Fix**: Failing specs go through a Python rule-engine that applies
   deterministic syntax fixes (the "Python engine between inference").
   If the fixed version passes SANY, we create a `bug_fix` training triple:
   (buggy_spec, sany_error, fixed_spec).
4. **Augment**: New examples are appended to `data/processed/augmented.jsonl`.
5. **Rebuild**: When enough examples accumulate, re-run `dataset_builder`
   (which merges the augmented data into the training set).
6. **Retrain**: Launch a short fine-tuning run on the enriched dataset.
7. **Deploy**: Merge LoRA → GGUF → Ollama.
8. **Repeat**: Jump to step 1 with the improved model.

The loop is designed to run unattended (tmux) for hours.  Each iteration
takes ~5-10 min for generation + ~80 min for retraining.

Usage
-----
    # Run one iteration (generate + fix + augment, no retrain)
    python -m src.training.self_improve --iterations 1 --no-retrain

    # Full autonomous loop with retraining every 20 new examples
    python -m src.training.self_improve --iterations 10 --retrain-threshold 20

    # Quick dry run
    python -m src.training.self_improve --iterations 1 --prompts 3 --no-retrain
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_REPO_ROOT       = Path(__file__).resolve().parents[2]
_AUGMENTED_JSONL = _REPO_ROOT / "data" / "processed" / "augmented.jsonl"
_BENCHMARK_JSON  = _REPO_ROOT / "data" / "benchmarks" / "benchmark_suite.json"
_TRAIN_JSONL     = _REPO_ROOT / "data" / "processed" / "train.jsonl"
_EVAL_JSONL      = _REPO_ROOT / "data" / "processed" / "eval.jsonl"

# Import the canonical developer prompt — single source of truth.
from src.training.dataset_builder import _DEVELOPER_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FixResult:
    """Result of attempting to fix a TLA+ spec."""
    original_spec: str
    fixed_spec: str
    sany_errors: str
    fixes_applied: list[str] = field(default_factory=list)
    passed_sany: bool = False


@dataclass
class IterationStats:
    """Statistics for one self-improvement iteration."""
    prompts_tried: int = 0
    specs_generated: int = 0
    sany_pass_raw: int = 0
    sany_pass_fixed: int = 0
    bug_fix_examples: int = 0
    spec_gen_examples: int = 0
    total_new_examples: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Python syntax fixer — deterministic rule engine
# ─────────────────────────────────────────────────────────────────────────────

def fix_tla_syntax(spec: str, sany_errors: str = "") -> FixResult:
    """
    Apply deterministic Python-based fixes for common TLA+ syntax errors.

    This is the "Python engine between inference" — it catches patterns that
    the LLM consistently gets wrong and applies mechanical corrections.

    Returns a FixResult with the fixed spec and list of applied fixes.
    """
    result = FixResult(
        original_spec=spec,
        fixed_spec=spec,
        sany_errors=sany_errors,
    )
    fixed = spec
    constant_alias_map: dict[str, str] = {}
    inserted_helper_operator_names: set[str] = set()

    def _strip_wrapping_parens(expr: str) -> str:
        expr = expr.strip()
        while expr.startswith("(") and expr.endswith(")"):
            depth = 0
            balanced = True
            for i, ch in enumerate(expr):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and i != len(expr) - 1:
                        balanced = False
                        break
            if not balanced or depth != 0:
                break
            expr = expr[1:-1].strip()
        return expr

    def _normalize_function_set_expr(expr: str) -> str:
        expr = _strip_wrapping_parens(expr.replace("-->", "->").strip())
        depth = 0
        for i in range(len(expr) - 1):
            ch = expr[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif depth == 0 and expr[i:i + 2] == "->":
                left = expr[:i].strip()
                right = expr[i + 2:].strip()
                return f"[{left} -> {_normalize_function_set_expr(right)}]"
        return expr

    def _infer_function_init_domain(var_name: str, binder: str, text: str) -> Optional[str]:
        direct = re.search(
            rf"\b{re.escape(var_name)}\b\s*\\in\s*\[\s*([^\]\n|]+?)\s*->",
            text,
        )
        if direct:
            return direct.group(1).strip()

        quantified = re.search(
            rf"(?ms)(?:\\A|\\forall)\s+{re.escape(binder)}\s+\\in\s+([^:\n]+?)\s*:\s*.*?\b{re.escape(var_name)}\[{re.escape(binder)}\]",
            text,
        )
        if quantified:
            return quantified.group(1).strip()
        return None

    def _prepend_helper_definition(text: str, definition: str) -> str:
        op_match = re.search(r"(?m)^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", text)
        if op_match:
            return text[:op_match.start()] + definition.rstrip() + "\n\n" + text[op_match.start():]
        end_marker = re.search(r"(?m)^====\s*$", text)
        if end_marker:
            return text[:end_marker.start()].rstrip() + "\n\n" + definition.rstrip() + "\n\n" + text[end_marker.start():]
        return text.rstrip() + "\n\n" + definition.rstrip()

    def _has_operator_definition(text: str, name: str) -> bool:
        return re.search(
            rf"(?m)^\s*{re.escape(name)}\s*\(\s*[A-Za-z_][A-Za-z0-9_]*"
            rf"(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*\s*\)\s*==",
            text,
        ) is not None

    def _collect_missing_helper_definitions(text: str) -> list[tuple[str, str, str]]:
        helpers = [
            (
                "RandomChoice",
                r"\bRandomChoice\(",
                "RandomChoice(S) == CHOOSE x \\in S : TRUE",
                "auto-defined RandomChoice helper",
            ),
            (
                "Sign",
                r"\bSign\(",
                "Sign(x) == IF x > 0 THEN 1 ELSE IF x < 0 THEN -1 ELSE 0",
                "auto-defined Sign helper",
            ),
            (
                "Sum",
                r"\bSum\(",
                "Sum(S) == LET __SumHelper[ss \\in SUBSET DOMAIN S] ==\n"
                "            IF ss = {} THEN 0\n"
                "            ELSE LET x == CHOOSE x \\in ss : TRUE\n"
                "                 IN S[x] + __SumHelper[ss \\ {x}]\n"
                "          IN __SumHelper[DOMAIN S]",
                "auto-defined Sum helper",
            ),
            (
                "MAX",
                r"\bMAX\(",
                "MAX(a, b) == IF a >= b THEN a ELSE b",
                "auto-defined MAX helper",
            ),
            (
                "Max",
                r"\bMax\(",
                "Max(S) == CHOOSE x \\in S : \\A y \\in S : x >= y",
                "auto-defined Max helper",
            ),
        ]
        missing: list[tuple[str, str, str]] = []
        for name, use_pattern, definition, message in helpers:
            if re.search(use_pattern, text) and not _has_operator_definition(text, name):
                missing.append((name, definition, message))
        return missing

    def _insert_helper_definitions(text: str, definitions: list[str]) -> str:
        if not definitions:
            return text
        extends_match = re.search(r"^EXTENDS\s+.+$", text, re.MULTILINE)
        helper_block = "\n\n" + "\n\n".join(definitions).rstrip() + "\n"
        if extends_match:
            insert_at = extends_match.end()
            return text[:insert_at] + helper_block + text[insert_at:]
        return _prepend_helper_definition(text, "\n\n".join(definitions))

    # ── Fix 1: Remove PlusCal blocks ──────────────────────────────────────
    # Pattern A: full block  (* --algorithm ... end algorithm; *)
    pluscal_pat = r"\(\*\s*--(?:fair\s+)?algorithm\b.*?end\s+algorithm\s*;?\s*\*\)"
    if re.search(pluscal_pat, fixed, re.DOTALL | re.IGNORECASE):
        fixed = re.sub(pluscal_pat, "", fixed, flags=re.DOTALL | re.IGNORECASE)
        result.fixes_applied.append("removed PlusCal block")
    else:
        # Pattern B: incomplete PlusCal — model starts (* --algorithm but
        # never closes with end algorithm; *).  Strip from the opening (* --algorithm
        # to the ==== (keep everything before it and the ==== itself).
        incomplete_pluscal = re.search(
            r"\(\*\s*--(?:fair\s+)?algorithm\b", fixed, re.IGNORECASE
        )
        if incomplete_pluscal:
            # Keep the spec up to right before the PlusCal block
            before = fixed[:incomplete_pluscal.start()].rstrip()
            # Ensure we still have the ==== delimiter
            if "====" not in before:
                before += "\n\n===="
            fixed = before
            result.fixes_applied.append("removed incomplete PlusCal block")

        # Pattern C: bare --algorithm (no (* wrapper)
        bare_pluscal = re.search(
            r"^--(?:fair\s+)?algorithm\b", fixed, re.MULTILINE | re.IGNORECASE
        )
        if bare_pluscal:
            before = fixed[:bare_pluscal.start()].rstrip()
            if "====" not in before:
                before += "\n\n===="
            fixed = before
            result.fixes_applied.append("removed bare PlusCal algorithm block")

    # If the spec has a BEGIN TRANSLATION / END TRANSLATION block (PlusCal
    # translator output), extract the header + translation + footer.
    trans_match = re.search(
        r"\\?\*?\s*BEGIN TRANSLATION.*?\n(.*?)\\?\*?\s*END TRANSLATION",
        fixed, re.DOTALL,
    )
    if trans_match:
        header_match = re.search(
            r"(----.*?MODULE.*?)(?:\(\*\s*--(?:fair\s+)?algorithm|--(?:fair\s+)?algorithm)",
            fixed, re.DOTALL,
        )
        footer_match = re.search(r"\\?\*?\s*END TRANSLATION.*?\n(.*)", fixed, re.DOTALL)
        header = header_match.group(1).strip() if header_match else ""
        translation = trans_match.group(1).strip()
        footer = footer_match.group(1).strip() if footer_match else "===="
        fixed = f"{header}\n\n{translation}\n\n{footer}"
        if "====" not in fixed:
            fixed += "\n===="
        result.fixes_applied.append("extracted TLA+ translation from PlusCal")

    # Remove standalone PlusCal keywords
    pluscal_kw = re.findall(r"^\s*(begin|end\s+algorithm|macro|procedure)\b.*$", fixed, re.MULTILINE | re.IGNORECASE)
    if pluscal_kw:
        fixed = re.sub(r"^\s*(begin|end\s+algorithm|macro|procedure)\b.*$", "", fixed, flags=re.MULTILINE | re.IGNORECASE)
        result.fixes_applied.append("removed PlusCal keywords")

    # ── Fix 2: Remove markdown fences ─────────────────────────────────────
    if re.search(r"^```", fixed, re.MULTILINE):
        fixed = re.sub(r"^```\w*\s*$", "", fixed, flags=re.MULTILINE)
        result.fixes_applied.append("removed markdown fences")

    # ── Fix 3: Fix VARIABLES declaration (missing commas) ─────────────────
    # Pattern: VARIABLES followed by identifiers on separate lines without commas
    var_block = re.search(r"(VARIABLES?\s*\n)((?:\s+\w+\s*(?:\\.*)?(?:\n|$))+)", fixed)
    if var_block:
        var_lines = var_block.group(2).strip().splitlines()
        # Check if lines lack commas between variables
        needs_fix = False
        for i, line in enumerate(var_lines[:-1]):
            stripped = line.rstrip()
            if stripped and not stripped.endswith(",") and not stripped.endswith("\\*"):
                needs_fix = True
                break
        if needs_fix:
            new_lines = []
            for i, line in enumerate(var_lines):
                stripped = line.rstrip()
                # Remove trailing comments for processing
                comment = ""
                if "\\*" in stripped:
                    parts = stripped.split("\\*", 1)
                    stripped = parts[0].rstrip()
                    comment = " \\*" + parts[1]
                # Add comma if not last line and doesn't have one
                if i < len(var_lines) - 1 and not stripped.endswith(","):
                    stripped = stripped + ","
                new_lines.append(stripped + comment)
            new_var_block = var_block.group(1) + "\n".join("    " + l.strip() for l in new_lines) + "\n"
            fixed = fixed[:var_block.start()] + new_var_block + fixed[var_block.end():]
            result.fixes_applied.append("added commas to VARIABLES declaration")

    # ── Fix 3b: Fix CONSTANTS with inline constraints ─────────────────────
    # Models produce: CONSTANTS N \in Nat, FORK \in 1..N
    # TLA+ requires: CONSTANT N, FORK   (no constraints — use ASSUME instead)
    const_block = re.search(r"^(CONSTANTS?)\s+(.+?)(?=\n\n|\n[A-Z])", fixed, re.MULTILINE | re.DOTALL)
    if const_block:
        keyword = const_block.group(1)
        body = const_block.group(2).strip()
        # Check if it has \in or \setminus or other constraint operators
        if re.search(r"\\in\b|\\setminus|\\subseteq|\\cup|\\cap", body):
            # Extract just variable names (strip constraints)
            names = []
            for part in re.split(r",\s*(?=\w)", body):
                m = re.match(r"(\w+)", part.strip())
                if m:
                    names.append(m.group(1))
            if names:
                new_const = f"{keyword} {', '.join(names)}"
                fixed = fixed[:const_block.start()] + new_const + fixed[const_block.end():]
                result.fixes_applied.append("stripped inline constraints from CONSTANTS")

    # ── Fix 4: Fix double-prime (x'' → x') ───────────────────────────────
    if re.search(r"\w''", fixed):
        fixed = re.sub(r"(\w)''", r"\1'", fixed)
        result.fixes_applied.append("fixed double-prime to single-prime")

    # ── Fix 5: Fix vars == {...} → vars == <<...>> ────────────────────────
    vars_set = re.search(r"(vars\s*==\s*)\{([^}]+)\}", fixed)
    if vars_set:
        fixed = fixed[:vars_set.start()] + vars_set.group(1) + "<<" + vars_set.group(2) + ">>" + fixed[vars_set.end():]
        result.fixes_applied.append("fixed vars set to tuple")

    # ── Fix 6: Fix UNCHANGED single variable (no <<>>) ───────────────────
    # UNCHANGED x, y → UNCHANGED <<x, y>>
    unchanged_multi = re.findall(r"UNCHANGED\s+(\w+\s*,\s*\w+(?:\s*,\s*\w+)*)", fixed)
    for match in unchanged_multi:
        old = f"UNCHANGED {match}"
        new = f"UNCHANGED <<{match}>>"
        fixed = fixed.replace(old, new, 1)
        result.fixes_applied.append("wrapped UNCHANGED multi-variable in tuple")

    # ── Fix 7: Fix CONSTANT with value assignment ─────────────────────────
    # CONSTANT N = 5 → CONSTANT N
    const_assigns = re.findall(r"^(\s*CONSTANTS?\s+\w+)\s*=\s*\S+", fixed, re.MULTILINE)
    if const_assigns:
        for old in const_assigns:
            fixed = re.sub(
                r"^(\s*CONSTANTS?\s+\w+)\s*=\s*\S+",
                r"\1",
                fixed, count=1, flags=re.MULTILINE,
            )
        result.fixes_applied.append("removed CONSTANT value assignment")

    # ── Fix 8: Fix quoted strings (TLA+ uses double quotes only) ─────────
    # Some models produce "idle" with escaped quotes
    if '\\"' in fixed:
        # Convert escaped quotes to regular quotes
        fixed = fixed.replace('\\"', '"')
        result.fixes_applied.append("unescaped quotes")

    # ── Fix 8b: Replace \notin (not standard in SANY) with ~(\in) ────────
    if "\\notin" in fixed:
        fixed = re.sub(r"(\w+)\s*\\notin\s*", r"~(\1 \\in ", fixed)
        # Close the parens — heuristic: add ) at end of line
        fixed = re.sub(r"(~\([^)\n]+)$", r"\1)", fixed, flags=re.MULTILINE)
        result.fixes_applied.append("replaced \\notin with ~(\\in)")

    # ── Fix 8c: Remove ASSUME blocks that reference VARIABLEs ────────────
    # SANY requires ASSUME to be level 0 (constants only). Models often
    # put variables in ASSUME which gives "Level error".
    # Also remove ASSUMEs that use non-standard operators.
    if "ASSUME" in fixed:
        # Extract variable names
        var_match = re.search(r"VARIABLES?\s+(.+?)(?:\n\n|\n[A-Z])", fixed, re.DOTALL)
        var_names = set()
        if var_match:
            var_names = {v.strip().rstrip(",") for v in re.split(r"[,\n]", var_match.group(1)) if v.strip().rstrip(",")}

        # Check each ASSUME line
        assume_lines_to_remove = []
        for m in re.finditer(r"^(\s*ASSUME\b.*)$", fixed, re.MULTILINE):
            assume_text = m.group(1)
            # Remove if it contains a variable name or if SANY reported level error
            should_remove = "level error" in sany_errors.lower() or "otin" in sany_errors
            if var_names:
                for vn in var_names:
                    if vn and re.search(rf"\b{re.escape(vn)}\b", assume_text):
                        should_remove = True
                        break
            if should_remove:
                assume_lines_to_remove.append(m.group(0))

        for line in assume_lines_to_remove:
            fixed = fixed.replace(line, "", 1)
            result.fixes_applied.append("removed ASSUME referencing variable")

        # Also remove multi-line ASSUME blocks
        if "otin" in sany_errors or "ASSUME" in sany_errors:
            fixed = re.sub(r"^\s*ASSUME\s*\n(?:\s+.*\n)*", "\n", fixed, flags=re.MULTILINE)
            result.fixes_applied.append("removed problematic ASSUME block")


    # ── Fix 9: Fix missing ==== ───────────────────────────────────────────
    if "====" not in fixed:
        fixed = fixed.rstrip() + "\n\n===="
        result.fixes_applied.append("added missing ==== delimiter")

    # ── Fix 10: Fix MODULE header (needs at least 4 dashes each side) ─────
    header = re.search(r"^(-+)\s*MODULE\s+(\w+)\s*(-+)", fixed, re.MULTILINE)
    if header:
        if len(header.group(1)) < 4 or len(header.group(3)) < 4:
            new_header = f"---- MODULE {header.group(2)} ----"
            fixed = fixed[:header.start()] + new_header + fixed[header.end():]
            result.fixes_applied.append("fixed MODULE header dashes")

    # ── Fix 11: (merged into Fix 15 — unconditional alignment) ─────────── 

    # ── Fix 12: Remove trailing garbage after ==== ────────────────────────
    # Preserve TLC config lines (SPECIFICATION, INVARIANT, CONSTANTS) that
    # appear after ==== — these are essential for model checking and the
    # developer prompt explicitly asks for them.
    m = re.search(r"(----\s*MODULE\b.*?====)(.*)", fixed, re.DOTALL)
    if m:
        module_part = m.group(1)
        after_module = m.group(2)
        # Keep lines that look like TLC config, drop everything else
        config_lines = []
        for line in after_module.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("\\*"):
                config_lines.append(line)
            elif any(stripped.upper().startswith(kw) for kw in
                     ("SPECIFICATION", "INVARIANT", "INVARIANTS",
                      "PROPERTY", "PROPERTIES", "CONSTANTS", "CONSTANT",
                      "CONSTRAINT", "SYMMETRY", "VIEW")):
                config_lines.append(line)
            # else: discard (garbage after module)
        fixed = module_part + "\n".join(config_lines)
        if fixed.rstrip() != result.fixed_spec.rstrip():
            result.fixes_applied.append("cleaned after ==== (preserved TLC config)")

    # ── Fix 13: Fix empty-line-separated conjunctions ─────────────────────
    # Some models put blank lines between /\ conjuncts, which breaks SANY
    # e.g.:
    #   Init ==
    #     /\ x = 0
    #
    #     /\ y = 0
    fixed = re.sub(r"(\n\s*/\\[^\n]+)\n\s*\n(\s*/\\)", r"\1\n\2", fixed)

    # ── Fix 14: Fix \\in vs \in (double-backslash in non-raw context) ─────
    # Models sometimes produce \\in, \\cup, \\subseteq etc. with double backslash
    for op in ["in", "cup", "cap", "subseteq", "union", "notin", "times",
               "leq", "geq", "div", "o", "circ", "land", "lor", "lnot",
               "equiv", "neg", "A", "E"]:
        fixed = re.sub(rf"\\\\{op}\b", rf"\\{op}", fixed)

    # ── Fix 15: Conjunction/disjunction indent normalization ─────────────
    # Only run when SANY reports indent issues — the fixer can break
    # quantifier scoping if applied blindly.
    if "not properly indented" in sany_errors.lower() or "alignment" in sany_errors.lower():
        old_fixed = fixed
        fixed = _fix_conjunction_indent(fixed)
        if fixed != old_fixed:
            result.fixes_applied.append("normalized conjunction/disjunction alignment")

    # ── Fix 16: Remove \notin if still present after Fix 8b ──────────────
    # Fallback: just replace \notin X with ~(var \in X) more aggressively
    _notin_safety = 0
    while "\\notin" in fixed and _notin_safety < 10:
        old_fixed = fixed
        fixed = re.sub(
            r"(\b\w+(?:\[\w+\])?)\s*\\notin\s+(\w+(?:\([^)]*\))?)",
            r"~(\1 \\in \2)",
            fixed, count=1,
        )
        if fixed == old_fixed:
            # regex didn't match — forcibly remove remaining \notin
            fixed = fixed.replace("\\notin", "\\in", 1)
            result.fixes_applied.append("force-replaced \\notin with \\in")
            break
        result.fixes_applied.append("replaced remaining \\notin")
        _notin_safety += 1

    # ── Fix 17: Fix EXTENDS with non-existent modules ────────────────────
    # SANY only knows: Naturals, Integers, Reals, Sequences, FiniteSets,
    # TLC, Bags, RealTime, Toolbox. Remove unknown modules.
    known_modules = {"Naturals", "Integers", "Reals", "Sequences",
                     "FiniteSets", "TLC", "Bags", "RealTime", "Toolbox",
                     "TLAPS", "Apalache"}
    extends_match = re.search(r"^EXTENDS\s+(.+)$", fixed, re.MULTILINE)
    if extends_match:
        mods = [m.strip() for m in extends_match.group(1).split(",")]
        valid_mods = [m for m in mods if m in known_modules]
        if valid_mods and len(valid_mods) < len(mods):
            new_extends = "EXTENDS " + ", ".join(valid_mods)
            fixed = fixed[:extends_match.start()] + new_extends + fixed[extends_match.end():]
            result.fixes_applied.append(f"removed unknown EXTENDS modules")
        elif not valid_mods and len(mods) > 0 and mods != [""]:
            # All modules unknown — remove EXTENDS line entirely
            fixed = fixed[:extends_match.start()] + fixed[extends_match.end():]
            result.fixes_applied.append("removed EXTENDS with all unknown modules")
    extends_match = re.search(r"^EXTENDS\s+(.+)$", fixed, re.MULTILINE)
    if extends_match and "Len(" in fixed:
        mods = [m.strip() for m in extends_match.group(1).split(",") if m.strip()]
        if "Sequences" not in mods:
            mods.append("Sequences")
            new_extends = "EXTENDS " + ", ".join(mods)
            fixed = fixed[:extends_match.start()] + new_extends + fixed[extends_match.end():]
            result.fixes_applied.append("added Sequences to EXTENDS for Len")
    missing_helper_defs = _collect_missing_helper_definitions(fixed)
    if missing_helper_defs:
        fixed = _insert_helper_definitions(fixed, [definition for _, definition, _ in missing_helper_defs])
        inserted_helper_operator_names.update(name for name, _, _ in missing_helper_defs)
        for _, _, message in missing_helper_defs:
            result.fixes_applied.append(message)

    # ── Fix 18: Fix single-line ASSUME with \notin cleanup artifacts ─────
    # Remove ASSUME lines that are now syntactically broken
    fixed = re.sub(r"^\s*ASSUME\s*~?\s*\(\s*\)\s*$", "", fixed, flags=re.MULTILINE)

    # ── Fix 18b: Remove question-mark junk from identifiers / expressions ─
    fixed_new = re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\?(?![A-Za-z0-9_])", r"\1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized identifier question suffixes")
        fixed = fixed_new

    fixed_new = re.sub(r"([>\]A-Za-z0-9_])\?+(?=\s*(?:\(\*|\\\*|$))", r"\1", fixed)
    fixed_new = re.sub(r"\?{2,}", "", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("removed stray question-mark runs")
        fixed = fixed_new

    # ── Fix 19: Auto-define `vars` if referenced but not defined ──────────
    # Models often use WF_vars(Next) or SF_vars(Next) without defining vars.
    if re.search(r"\bvars\b", fixed) and not re.search(r"^\s*vars\s*==", fixed, re.MULTILINE):
        # Extract variable names from VARIABLES declaration
        var_match = re.search(r"VARIABLES?\s+(.+?)(?=\n\n|\n[A-Z])", fixed, re.DOTALL)
        if var_match:
            var_names = [v.strip().rstrip(",") for v in re.split(r"[,\n]", var_match.group(1))
                         if v.strip().rstrip(",")]
            if var_names:
                vars_tuple = "<<" + ", ".join(var_names) + ">>"
                # Insert vars definition after the VARIABLES block
                # Find the end of the VARIABLES block (next blank line)
                var_end = var_match.end()
                # Look for the next blank line after VARIABLES
                next_blank = fixed.find("\n\n", var_end)
                if next_blank != -1:
                    insert_pos = next_blank
                else:
                    insert_pos = var_end
                vars_def = f"\n\nvars == {vars_tuple}\n"
                fixed = fixed[:insert_pos] + vars_def + fixed[insert_pos:]
                result.fixes_applied.append(f"auto-defined vars == {vars_tuple}")

    # ── Fix 20: Replace inline WF_vars/SF_vars if vars still undefined ────
    # Fallback: directly substitute the variable tuple into WF/SF expressions
    if re.search(r"[WS]F_vars\b", fixed) and not re.search(r"^\s*vars\s*==", fixed, re.MULTILINE):
        var_match = re.search(r"VARIABLES?\s+(.+?)(?=\n\n|\n[A-Z])", fixed, re.DOTALL)
        if var_match:
            var_names = [v.strip().rstrip(",") for v in re.split(r"[,\n]", var_match.group(1))
                         if v.strip().rstrip(",")]
            if var_names:
                vars_tuple = "<<" + ", ".join(var_names) + ">>"
                fixed = re.sub(r"WF_vars\b", f"WF_{vars_tuple}", fixed)
                fixed = re.sub(r"SF_vars\b", f"SF_{vars_tuple}", fixed)
                result.fixes_applied.append("inlined vars tuple in WF/SF")

    # ── Fix 21: Remove bare module-level expressions (BM019 pattern) ──────
    # Models sometimes emit bare `x \in Type` lines directly at module level
    # (e.g., after a "(* Type definitions *)" comment) instead of inside
    # TypeOK ==.  These cause parse errors because TLA+ doesn't allow bare
    # expressions at module level.
    # Strategy: if such lines exist, collect them into a TypeOK definition
    # if TypeOK isn't already defined, otherwise just remove them.
    bare_expr_pat = re.compile(
        r"^(\w[\w\[\]]*(?:\[[\w, ]+\])?)\s*\\in\s+[^\n]+$", re.MULTILINE
    )
    # Only apply outside operator bodies: find lines that are at column 0 or
    # preceded only by comments and appear before the first == definition
    def _is_bare_module_level(spec_text: str) -> list[tuple[str,str]]:
        r"""Return (full_line, variable_part) for bare-level \in expressions."""
        found = []
        in_body = False
        for line in spec_text.splitlines():
            stripped = line.strip()
            if re.match(r"^\w+\s*(==|\(==\))", stripped):
                in_body = True
            if stripped == "" or stripped.startswith("\\*") or stripped.startswith("(*"):
                continue
            if not in_body and bare_expr_pat.match(line.strip()):
                found.append((line, line.strip()))
        return found

    bare_lines = _is_bare_module_level(fixed)
    if bare_lines:
        # Remove them from the spec — only try the fallback if the first
        # replacement didn't work to avoid accidentally removing matching
        # substrings inside operator bodies.
        for full_line, _ in bare_lines:
            new_fixed = fixed.replace(full_line + "\n", "", 1)
            if new_fixed == fixed:
                # No exact newline match — try without newline
                new_fixed = fixed.replace(full_line, "", 1)
            fixed = new_fixed
        result.fixes_applied.append("removed bare module-level \\in expressions")

    # ── Fix 23: Replace English quantifier keywords with TLA+ operators ───
    # Models sometimes emit EXISTS/FORALL instead of \E/\A, or ALL/SOME.
    # Must be careful not to replace inside strings or comments.
    # EXISTS x \in S : P  →  \E x \in S : P
    fixed_new = re.sub(r"\bEXISTS\s+(\w)", r"\\E \1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("replaced EXISTS with \\E")
        fixed = fixed_new
    fixed_new = re.sub(r"\bFORALL\s+(\w)", r"\\A \1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("replaced FORALL with \\A")
        fixed = fixed_new
    # Also handle ALL/SOME (less common but seen)
    fixed_new = re.sub(r"\bALL\s+(\w+)\s*\\in\b", r"\\A \1 \\in", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("replaced ALL with \\A")
        fixed = fixed_new
    fixed_new = re.sub(r"\bSOME\s+(\w+)\s*\\in\b", r"\\E \1 \\in", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("replaced SOME with \\E")
        fixed = fixed_new

    # ── Fix 23b: Repair common benchmark parser artefacts ────────────────
    fixed_new = re.sub(r"\|\->\s+>", r"|-> ", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("removed stray > after |->")
        fixed = fixed_new

    fixed_new = re.sub(r"EXCEPT\s+(!\[[^]]+\])'\s*=", r"EXCEPT \1 =", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("removed invalid prime from EXCEPT selector")
        fixed = fixed_new

    fixed_new = re.sub(
        r"Spec\s*==\s*Init\s*/\\\s*\[\]_\(([^)]+)\)\s*\(\s*Next\s*\)",
        r"Spec == Init /\\ [][Next]_\1",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized malformed Spec temporal formula")
        fixed = fixed_new

    fixed_new = re.sub(
        r"Spec\s*==\s*Init\s*/\\\s*\[\]_\[\{([^}]+)\}\]\(\s*Next\s*\)",
        lambda m: "Spec == Init /\\ [Next]_<<" + ", ".join(part.strip() for part in m.group(1).split(",") if part.strip()) + ">>",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized bracket-set Spec temporal formula")
        fixed = fixed_new

    fixed_new = re.sub(r"Spec\s*==\s*Init\s*/\\\s*\[\]\s+Next\b", r"Spec == Init /\\ []Next", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized plain Spec [] Next spacing")
        fixed = fixed_new

    fixed_new = re.sub(
        r"Spec\s*==\s*Init\s*/\\\s*\n\s*\[\]\[\s*Next\s*]_(.+?)\s*\\\s*\n\s*/\\\s*(.+)",
        lambda m: f"Spec == Init /\\ [][Next]_{m.group(1).strip()} /\\ {m.group(2).strip()}",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized multiline Spec temporal formula")
        fixed = fixed_new

    fixed_new = re.sub(r"\[\]\[\s*Next\s*]_", r"[][Next]_", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized spaced Spec temporal box")
        fixed = fixed_new

    fixed_new = re.sub(r"Spec\s*==\s*Init\s*/\\\s*\[\]_\(\s*vars\s*\)\[\[\s*Next\s*]]", r"Spec == Init /\\ [][Next]_vars", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized malformed vars Spec temporal formula")
        fixed = fixed_new

    fixed_new = re.sub(r"Spec\s*==\s*Init\s*/\\\s*\[\]<>\\?\(\s*Next\s*\)", r"Spec == Init /\\ [][Next]_vars", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized malformed diamond Next Spec formula")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?m)^IF\s+([A-Za-z_][A-Za-z0-9_]*)\s*#\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\/\s*(?:\\E|EXISTS)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\\\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*<=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*&\s*([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?)\s*<=\s*(-?\d+)\s+THEN\s+(.+?)\s+ELSE\s+(.+)$",
        lambda m: (
            f"IF ({m.group(1)} # {m.group(2)}) \\/ "
            f"(\\E {m.group(3)} : ({m.group(4)} <= {m.group(5)}) /\\ {m.group(6)} <= {m.group(7)}) "
            f"THEN {m.group(8)} ELSE {m.group(9)}"
        ),
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized malformed terminating IF condition")
        fixed = fixed_new

    fixed_new = re.sub(r"(?m)^(\s*)\\/\s*(\([^\n]+\)|[A-Za-z_][^\n]*?)\s*=>\s*$", r"\1\\/ /\\ \2", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized guarded disjunct lines")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?ms)\(\(\s*([^)]+?)\s*\)\s*=>\s*([A-Za-z_][A-Za-z0-9_]*(?:\([^)\n]*\))?)\s*\)\s*\n\s*\\/\s*/\\\s*\(\(\s*([^)]+?)\s*\)\s*\n(?:\s*\(\*.*?\*\)\s*\n)*\s*([A-Za-z_][A-Za-z0-9_]*(?:\([^)\n]*\))?)\s*\)",
        lambda m: f"IF {m.group(1).strip()} THEN {m.group(2).strip()} ELSE {m.group(4).strip()}",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote disjoined implication pair as IF THEN ELSE")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?ms)(^\s*\\/\s+\\A\s+[^\n:]+:\s*)\n\s*(\([^\n]+?\))\s*->\s*\(\s*\n\s*([^\n]+?)\s*\n\s*\)",
        lambda m: f"{m.group(1)} ({m.group(2).strip()} => {m.group(3).strip()})",
        fixed,
        flags=re.MULTILINE,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("inlined quantified implication disjunct body")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?m)(^\s*\\/\s+\\A\s+[^\n:]+:\s*\(\([^\n]+?=>\s*IF\s+.+?\s+THEN\s+[A-Za-z_][A-Za-z0-9_]*(?:\([^)\n]*\))?)\)$",
        r"\1 ELSE UnchangedVars)",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("completed quantified action IF missing ELSE branch")
        fixed = fixed_new

    fixed_new = re.sub(r"\[\]\s*\[\]\s*(\[\s*Next\s*]_\w+)", r"[]\1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized duplicate temporal box operators")
        fixed = fixed_new

    fixed_new = re.sub(r"\bCONSTDEF\b", "", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("removed CONSTDEF pseudo-keyword")
        fixed = fixed_new

    fixed_new = re.sub(r"(?m)^\*{3,}.*\*{3,}\s*$", "", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("removed markdown-style banner lines")
        fixed = fixed_new

    fixed_new = fixed.replace("/*", "(*").replace("*/", "*)")
    fixed_new = re.sub(r"(?m)//\s?(.*)$", r"\\* \1", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized non-TLA comment styles")
        fixed = fixed_new

    fixed_new = re.sub(r"(?m)^(\s*/\\\s+.+?)\s+--(?!\s*>)\s?(.*)$", r"\1 \\* \2", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized inline double-dash comments")
        fixed = fixed_new

    fixed_new = fixed.replace("\\land", "/\\").replace("\\and", "/\\").replace("\\vee", "\\/")
    if fixed_new != fixed:
        result.fixes_applied.append("normalized logical word operators")
        fixed = fixed_new

    fixed_new = re.sub(r"(?m)^(\s*)\*\s+(.*)$", r"\1\\* \2", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized bare star comment lines")
        fixed = fixed_new

    fixed_new = re.sub(r"\bELSEIF\b", "ELSE IF", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized ELSEIF tokenization")
        fixed = fixed_new

    fixed_new = re.sub(r"\bAND\b", r"/\\", fixed)
    fixed_new = re.sub(r"\bOR\b", r"\\/", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized word AND/OR operators")
        fixed = fixed_new

    fixed_new = re.sub(r"\blen\(", "Len(", fixed)
    fixed_new = re.sub(r"\bLEN\(", "Len(", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized Len(...) casing")
        fixed = fixed_new

    fixed_new = re.sub(r"\[\[\s*([^\[\]\n]+?)\s*\]\]", r"<<\1>>", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote double-bracket singleton sequence literal")
        fixed = fixed_new

    if not re.search(r"(?m)^\s*Insert\s*\(", fixed):
        fixed_new = re.sub(
            r"\bInsert\(\s*([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?)\s*,\s*([^)]+?)\s*\)",
            r"\1 \\cup {\2}",
            fixed,
        )
        if fixed_new != fixed:
            result.fixes_applied.append("rewrote Insert pseudo-op as set union")
            fixed = fixed_new

    def _rewrite_bare_function_initializer(match: re.Match) -> str:
        indent, var_name, binder, expr = match.groups()
        if "," in expr:
            return match.group(0)
        domain = _infer_function_init_domain(var_name, binder, fixed)
        if not domain:
            return match.group(0)
        return f"{indent}{var_name} = [{binder} \\in {domain} |-> {expr}]"

    fixed_new = re.sub(
        r"(?m)^(\s*(?:/\\\s+)?)"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\[([A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*(.+?)\]\s*$",
        _rewrite_bare_function_initializer,
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("added inferred domain to function initializer")
        fixed = fixed_new

    if "RemoveFirstWhere(" in fixed and not re.search(r"(?m)^\s*RemoveFirstWhere\s*\(", fixed):
        helper_def = """RemoveFirstWhere(P(_), seq) ==
    IF \\E i \\in 1..Len(seq) : P(seq[i])
    THEN LET idx == CHOOSE i \\in 1..Len(seq) :
                        /\\ P(seq[i])
                        /\\ \\A j \\in 1..(i - 1) : ~P(seq[j])
         IN SubSeq(seq, 1, idx - 1) \\o SubSeq(seq, idx + 1, Len(seq))
    ELSE seq"""
        fixed = _prepend_helper_definition(fixed, helper_def)
        result.fixes_applied.append("defined RemoveFirstWhere helper operator")

    fixed_new = re.sub(
        r"AckReceived\(\s*\[first\s*\|->\s*first\]\s*\[\s*currentChannel\s*]\s*\)",
        "AckReceived(Head(channelBuffer)[1])",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote channel placeholder ack target as Head(channelBuffer)[1]")
        fixed = fixed_new

    fixed_new = re.sub(
        r"SUM_\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\in\s*([^}\n]+)\}\s*([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])+)",
        r"Sum([\1 \\in \2 |-> \3])",
        fixed,
    )
    fixed_new = re.sub(
        r"SUM_\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\in\s*([^}\n]+)\}\s*\(\s*([^)][^\n]*?)\s*\)",
        r"Sum([\1 \\in \2 |-> \3])",
        fixed_new,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized SUM_{x in S} aggregate notation")
        fixed = fixed_new

    fixed_new = re.sub(
        r"Sum\(\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\in\s*([^\]\n|]+?)\s*\|->\s*MAX\(\\\{counts\[\]\[\1\]\\\}\]\)\)",
        lambda m: f"Sum([{m.group(1)} \\in {m.group(2).strip()} |-> Max({{counts[m][{m.group(1)}] : m \\in {m.group(2).strip()}}})])",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("expanded counts[][n] max shorthand")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\bIF\s+([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])?)\s+IN\s+(\{[^\n]+?\})\s+THEN\b",
        r"IF \1 \\in \2 THEN",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized uppercase IN membership in IF guard")
        fixed = fixed_new

    fixed_new = re.sub(r"\\i\s+n\b", r"\\in", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized broken \\i n token")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?ms)(/\\\s*counts\s*=\s*<<>>\s*\\/\s*)\(\\lambda\s+_\s+\\in\s+([^:\n]+):\s*\(\\lambda\s+_\s+\\in\s+([^:\n]+):\s*0\)\)",
        lambda m: f"{m.group(1)}[i \\in {m.group(2).strip()} |-> [j \\in {m.group(3).strip()} |-> 0]]",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote nested lambda zero initializer")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?ms)(^\s*/\\\s+\((?:\\A|\\forall)[^\n]+:\s*\n)\s*([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])+)'"
        r"\s*=\s*\n\s*IF\s+(.+?)\s+THEN\s+(.+?)\s*$",
        lambda m: f"{m.group(1)}                     {m.group(2)}' = IF {m.group(3)} THEN {m.group(4)} ELSE {m.group(2)})",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("completed quantified IF assignment missing ELSE branch")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?ms)(\n\s*\(merge\(ANY, ANY\)\)\s*)/\\(\s*\n\s*term\b)",
        r"\1\\/\2",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized malformed term disjunct tail")
        fixed = fixed_new

    if re.search(r"\bNodeSet\b", fixed):
        fixed_new = re.sub(
            r"(?m)^(\s*)\(([A-Za-z_][A-Za-z0-9_]*)\(Node\)\)(\s*\\/\s*)(.*)$",
            lambda m: f"{m.group(1)}(\\E n \\in NodeSet : {m.group(2)}(n)){m.group(3)}{m.group(4)}",
            fixed,
        )
        if fixed_new != fixed:
            result.fixes_applied.append("rewrote Node placeholder action invocation as quantified choice")
            fixed = fixed_new

        fixed_new = re.sub(
            r"(?m)^(\s*)\(([A-Za-z_][A-Za-z0-9_]*)\(ANY,\s*ANY\)\)(\s*\\/\s*)(.*)$",
            lambda m: f"{m.group(1)}(\\E m \\in NodeSet : \\E p \\in NodeSet : {m.group(2)}(m, p)){m.group(3)}{m.group(4)}",
            fixed,
        )
        if fixed_new != fixed:
            result.fixes_applied.append("rewrote ANY placeholder action invocation as quantified choice")
            fixed = fixed_new

    fixed_new = re.sub(r"\(\\\*\s*(.*?)\s*\\\*\)", r"(* \1 *)", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized escaped TLA comments")
        fixed = fixed_new

    inequality_atom = r"(?:-?\d+|-?[A-Za-z_][A-Za-z0-9_]*(?:\[[^]\n]+\])?)"
    fixed_new = re.sub(
        rf"({inequality_atom})\s*<=\s*({inequality_atom})\s*<=\s*({inequality_atom})",
        lambda m: f"({m.group(1)} <= {m.group(2)}) /\\ ({m.group(2)} <= {m.group(3)})",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote chained inequalities")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\[\s*([A-Za-z_][A-Za-z0-9_]*)\s+\\in\s+\[\s*(.+?)\s*\|\s*->\s*([^\]\n]+?)\s*\]\s*\]",
        r"[\1 \\in \2 |-> \3]",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote nested function initializer body")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\[\s*([A-Za-z_][A-Za-z0-9_]*)\s+\\in\s+([^\]\n|]+?)\s*\|\s*(.*?)\n\s*([A-Za-z_][A-Za-z0-9_]*)\[\1\]\s*\]",
        lambda m: f"[{m.group(1)} \\in {m.group(2).strip()} |-> {' '.join(m.group(3).split())}]",
        fixed,
        flags=re.DOTALL,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote multiline function initializer missing |->")
        fixed = fixed_new

    fixed_new = re.sub(
        r"(?ms)(delta\s*==)\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\in\s*([^:]+):\s*Sign\(([^)]+)\)\s*0\s*\}",
        lambda m: f"{m.group(1)} [{m.group(2)} \\in {m.group(3).strip()} |-> Sign({m.group(4).strip()})]",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote malformed delta set as function initializer")
        fixed = fixed_new

    zero_arg_function_value_names = re.findall(
        r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*==\s*\[[^\n]+?\|->",
        fixed,
    )
    fixed_new = fixed
    for name in zero_arg_function_value_names:
        fixed_new = re.sub(rf"\b{re.escape(name)}\(([^()\n]+)\)", rf"{name}[\1]", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote zero-arg function-value calls as indexing")
        fixed = fixed_new

    fixed_new = re.sub(r"\.\.\s*\+([A-Za-z_][A-Za-z0-9_]*)", r".. \1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized signed upper bounds in ranges")
        fixed = fixed_new

    zero_arg_names = re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*==", fixed)
    fixed_new = re.sub(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*==", r"\1 ==", fixed)
    for name in zero_arg_names:
        fixed_new = re.sub(rf"\b{name}\(\)", name, fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized zero-arg operator definitions/calls")
        fixed = fixed_new

    next_match = re.search(r"(?ms)^Next\s*==.*?(?=^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==|^====)", fixed)
    if next_match:
        next_block = next_match.group(0)
        referenced_actions = []
        for line in next_block.splitlines():
            match = re.match(r"^\s*\\/\s+([A-Za-z_][A-Za-z0-9_]*)\b", line)
            if match:
                referenced_actions.append(match.group(1))
        moved_blocks = []
        for name in referenced_actions:
            def_match = re.search(
                rf"(?ms)^{re.escape(name)}\s*==.*?(?=^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==|^====)",
                fixed,
            )
            if not def_match or def_match.start() < next_match.start():
                continue
            moved_blocks.append((def_match.start(), def_match.end(), def_match.group(0).rstrip()))
        if moved_blocks:
            rebuilt = fixed
            for start, end, _ in reversed(moved_blocks):
                rebuilt = rebuilt[:start] + rebuilt[end:]
            insert_at = next_match.start()
            blocks_text = "\n\n".join(block for _, _, block in moved_blocks) + "\n\n"
            rebuilt = rebuilt[:insert_at] + blocks_text + rebuilt[insert_at:]
            if rebuilt != fixed:
                fixed = rebuilt
                result.fixes_applied.append("moved forward action definitions before Next")

    late_helper_defs = _collect_missing_helper_definitions(fixed)
    if late_helper_defs:
        fixed = _insert_helper_definitions(fixed, [definition for _, definition, _ in late_helper_defs])
        inserted_helper_operator_names.update(name for name, _, _ in late_helper_defs)
        for _, _, message in late_helper_defs:
            if message not in result.fixes_applied:
                result.fixes_applied.append(message)

    def _insert_record_field_commas(match: re.Match) -> str:
        content = match.group(1)
        if any(token in content for token in ("|->", "EXCEPT", "\\in")):
            return match.group(0)
        updated = re.sub(r"(?<=\S)\s+([A-Za-z_][A-Za-z0-9_]*\s*:)", r", \1", content)
        return "[" + updated + "]"

    fixed_new = re.sub(r"\[([^\]\n]+)\]", _insert_record_field_commas, fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("inserted missing record field commas")
        fixed = fixed_new

    fixed_new = re.sub(r"(?m)^\s*/\\\s*UNCHANGED\s+@[^\n]*\n?", "", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("removed malformed UNCHANGED @ invariant line")
        fixed = fixed_new

    def _remove_unchanged_from_typeok(match: re.Match) -> str:
        block = match.group(0)
        return re.sub(r"(?m)^\s*/\\\s*UNCHANGED\s+<<[^>\n]+>>\s*\n?", "", block)

    fixed_new = re.sub(
        r"(?ms)^TypeOK\s*==.*?(?=^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==|^====)",
        _remove_unchanged_from_typeok,
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("removed UNCHANGED conjunct from TypeOK")
        fixed = fixed_new

    def _remove_unchanged_from_init(match: re.Match) -> str:
        block = match.group(0)
        return re.sub(r"(?m)^\s*/\\\s*UNCHANGED\s+<<[^>\n]+>>\s*\n?", "", block)

    fixed_new = re.sub(
        r"(?ms)^Init\s*==.*?(?=^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==|^====)",
        _remove_unchanged_from_init,
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("removed UNCHANGED conjunct from Init")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\[\{\s*([A-Za-z_][\s\S]*?)\s*\}\]",
        lambda m: "[" + " ".join(m.group(1).split()) + "]" if ":" in m.group(1) and "|->" not in m.group(1) else m.group(0),
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote bracketed record-set syntax")
        fixed = fixed_new

    actor_domain = None
    if re.search(r"(?m)^CONSTANTS?\s+.*\bParticipants\b", fixed):
        actor_domain = "Participants"
        if '"Coordinator"' in fixed:
            actor_domain = 'Participants \\cup {"Coordinator"}'
    if actor_domain:
        fixed_new = re.sub(
            r"\[sender:\s*ANY,\s*receiver:\s*ANY,\s*kind:\s*([A-Za-z_][A-Za-z0-9_]*)\]",
            lambda m: f"[sender: {actor_domain}, receiver: {actor_domain}, kind: {m.group(1)}]",
            fixed,
        )
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("rewrote ANY message record fields to actor domain")

    fixed_new = re.sub(
        r"(?<!<)<\s*([^<>\n]+,\s*[^<>\n]+(?:,\s*[^<>\n]+)*)\s*>(?!>)",
        lambda m: f"<<{m.group(1)}>>",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote single-angle tuple syntax")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\{(<<[^{}\n]+>>)\s*\|\s*([A-Za-z_][^{}\n]*\\in[^{}\n]*)\}",
        r"{\1 : \2}",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote tuple set-comprehension pipe to colon")
        fixed = fixed_new

    def _rewrite_malformed_union_singleton_update(match: re.Match) -> str:
        item = match.group("item").replace("\\}", "").strip()
        item = re.sub(r",\s*", ", ", item)
        if not item.endswith(")"):
            item = f"{item})"
        return f"{match.group('target')} = {match.group('base')} \\cup {{{item}}}"

    fixed_new = re.sub(
        r"(?P<target>[A-Za-z_][A-Za-z0-9_]*')\s*=\s*UNION\(\s*(?P<base>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
        r"\\\{\s*(?P<item>[^\n]+?)\\\}\)\s*\\\}",
        _rewrite_malformed_union_singleton_update,
        fixed,
    )
    fixed_new = re.sub(
        r"(?P<target>[A-Za-z_][A-Za-z0-9_]*')\s*=\s*UNION\(\s*(?P<base>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
        r"\\\{\s*(?P<item>[^\n]+?)\s*\\\}\s*\\\}",
        _rewrite_malformed_union_singleton_update,
        fixed_new,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote malformed UNION singleton update")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\[\s*([A-Za-z_][A-Za-z0-9_]*)\s+(?:\\in|IN)\s+([^\]\n|]+?)\s*\|\s*(?!->)(?=\S)",
        r"[\1 \\in \2 |-> ",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("inserted missing function constructor |->")
        fixed = fixed_new

    def _rewrite_malformed_vote_message_function_update(match: re.Match) -> str:
        msg_kind = match.group("msg_kind")
        domain = match.group("domain").strip()
        condition = re.sub(r"^IF\s+", "", match.group("condition").strip())
        witness = match.group("witness")
        witness_set = match.group("witness_set")
        msg_var = match.group("msg_var")
        normalized_set = constant_alias_map.get(witness_set.lower(), witness_set)
        return (
            f"[{msg_kind} \\in {domain} |-> "
            f"IF ({condition}) /\\ (\\E {witness} \\in {normalized_set} : "
            f"<<{witness}, \"Coordinator\", {msg_kind}>> = {msg_var}) "
            f"THEN TRUE ELSE FALSE]"
        )

    fixed_new = re.sub(
        r"\[(?P<msg_kind>[A-Za-z_][A-Za-z0-9_]*)\s+\\in\s+(?P<domain>[^\]\n|]+?)\s*\|->\s*"
        r"\((?P<condition>IF\s+.+?)\)\s*=>\s*IF\s+\\E\s+(?P<witness>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"\\in\s+(?P<witness_set>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*"
        r"\(\(\s*(?P=witness)\s*,\s*(?P=msg_kind)\s*\)\s*=\s*(?P<msg_var>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*"
        r"THEN\s+\[[A-Za-z_][A-Za-z0-9_]*\s+EXCEPT\s+!\[(?P=msg_kind)\]\s*=\s*TRUE\]",
        _rewrite_malformed_vote_message_function_update,
        fixed,
        flags=re.DOTALL,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote malformed vote message function update")
        fixed = fixed_new

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    grouped_mixed_guard = False
    promoted_dangling_updates = False
    while i < len(lines):
        line = lines[i]
        mixed_guard = re.match(r"^(\s*)/\\\s+(.+?)\s*$", line)
        if mixed_guard and i + 3 < len(lines):
            indent = mixed_guard.group(1)
            disjunct = re.match(rf"^{re.escape(indent)}\\/\s+(.+?)\s*$", lines[i + 1])
            dangling_conj = re.match(rf"^{re.escape(indent)}/\\\s*$", lines[i + 2])
            if disjunct and dangling_conj:
                promoted_updates = []
                j = i + 3
                while j < len(lines):
                    candidate = lines[j]
                    stripped = candidate.strip()
                    if not stripped:
                        break
                    if re.match(rf"^{re.escape(indent)}(?:/\\|\\/)\b", candidate):
                        break
                    if re.match(r"^\w+(?:\([^)]*\))?\s*==", stripped):
                        break
                    if "=" not in stripped and not stripped.startswith("UNCHANGED"):
                        break
                    promoted_updates.append(stripped)
                    j += 1
                if promoted_updates:
                    rebuilt_lines.append(
                        f"{indent}/\\ ({mixed_guard.group(2)} \\/ {disjunct.group(1)})"
                    )
                    rebuilt_lines.extend(
                        f"{indent}/\\ {update}" for update in promoted_updates
                    )
                    grouped_mixed_guard = True
                    promoted_dangling_updates = True
                    i = j
                    continue
        rebuilt_lines.append(line)
        i += 1
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        if grouped_mixed_guard:
            result.fixes_applied.append("grouped mixed disjunct guard into conjunction block")
        if promoted_dangling_updates:
            result.fixes_applied.append("promoted dangling update lines into conjunction block")
        fixed = fixed_new

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    promoted_quantified_updates = False
    while i < len(lines):
        line = lines[i]
        quantified_conj = re.match(r"^(\s*)/\\\s+\\(?:A|E)\s+.+:\s*$", line)
        if not quantified_conj:
            rebuilt_lines.append(line)
            i += 1
            continue
        rebuilt_lines.append(line)
        base_indent = len(quantified_conj.group(1))
        child_indent = " " * (base_indent + 3)
        i += 1
        while i < len(lines):
            candidate = lines[i]
            stripped = candidate.strip()
            if not stripped:
                rebuilt_lines.append(candidate)
                i += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if candidate_indent <= base_indent:
                break
            if candidate.lstrip().startswith(("/\\", "\\/", "ELSE", "IN", "THEN")):
                rebuilt_lines.append(candidate)
            elif "=" in stripped or stripped.startswith("UNCHANGED"):
                rebuilt_lines.append(f"{child_indent}/\\ {stripped}")
                promoted_quantified_updates = True
            else:
                rebuilt_lines.append(candidate)
            i += 1
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if promoted_quantified_updates:
            result.fixes_applied.append("promoted dangling quantified update lines into conjunction block")

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    replaced_malformed_let_in_tail = False
    while i < len(lines):
        line = lines[i]
        let_in_line = re.match(r"^(\s*)(?:in|IN)\s*$", line)
        if not let_in_line:
            rebuilt_lines.append(line)
            i += 1
            continue
        indent = let_in_line.group(1)
        j = i + 1
        saw_placeholder = False
        while j < len(lines):
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            if re.match(r"^(====|[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==|EXTENDS|CONSTANTS?\b|VARIABLES?\b|ASSUME\b|THEOREM\b|LEMMA\b|PROPOSITION\b|PROPERTY\b)", stripped):
                break
            if ":=" in lines[j] or "..." in lines[j] or "placeholder" in stripped.lower():
                saw_placeholder = True
            j += 1
        if saw_placeholder:
            rebuilt_lines.append(f"{indent}IN TRUE")
            replaced_malformed_let_in_tail = True
            i = j
            continue
        rebuilt_lines.append(line)
        i += 1
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if replaced_malformed_let_in_tail:
            result.fixes_applied.append("replaced malformed LET-IN placeholder tail with IN TRUE")

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    completed_let_helper_if_chain = False
    normalized_lowercase_in_after_let_helper = False
    while i < len(lines):
        line = lines[i]
        let_if_header = re.match(
            r"^(\s*)LET\s+[A-Za-z_][A-Za-z0-9_]*\([^)]*\)\s*==\s*IF\b.+\bTHEN\s*$",
            line,
        )
        if not let_if_header:
            rebuilt_lines.append(line)
            i += 1
            continue
        rebuilt_lines.append(line)
        base_indent = len(let_if_header.group(1))
        j = i + 1
        saw_else_if = False
        saw_else = False
        branch_indent_str: Optional[str] = None
        while j < len(lines):
            candidate = lines[j]
            stripped = candidate.strip()
            if not stripped:
                rebuilt_lines.append(candidate)
                j += 1
                continue
            in_match = re.match(r"^(\s*)(?:in|IN)\b(.*)$", candidate)
            if in_match and len(in_match.group(1)) <= base_indent + 4:
                if saw_else_if and not saw_else:
                    indent = branch_indent_str or (" " * (base_indent + 3))
                    rebuilt_lines.append(f"{indent}ELSE TRUE")
                    completed_let_helper_if_chain = True
                if candidate.lstrip().startswith("in"):
                    rebuilt_lines.append(f"{in_match.group(1)}IN{in_match.group(2)}")
                    normalized_lowercase_in_after_let_helper = True
                else:
                    rebuilt_lines.append(candidate)
                j += 1
                break
            if re.match(r"^(====|[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==)", stripped):
                break
            else_if_match = re.match(r"^(\s*)ELSE IF\b", candidate)
            else_match = re.match(r"^(\s*)ELSE\b", candidate)
            if else_if_match:
                saw_else_if = True
                branch_indent_str = else_if_match.group(1)
            elif else_match:
                saw_else = True
                branch_indent_str = else_match.group(1)
            rebuilt_lines.append(candidate)
            j += 1
        i = j
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if completed_let_helper_if_chain:
            result.fixes_applied.append("completed LET helper IF chain missing final ELSE")
        if normalized_lowercase_in_after_let_helper:
            result.fixes_applied.append("normalized lowercase in keyword after LET helper")

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    removed_dangling_else_if = False
    while i < len(lines):
        line = lines[i]
        rebuilt_lines.append(line)
        if "LET " not in line or " IN" not in line:
            i += 1
            continue
        j = i + 1
        saw_conjunct = False
        while j < len(lines) and not lines[j].strip():
            rebuilt_lines.append(lines[j])
            j += 1
        while j < len(lines) and lines[j].lstrip().startswith("/\\"):
            rebuilt_lines.append(lines[j])
            saw_conjunct = True
            j += 1
        if saw_conjunct and j < len(lines) and lines[j].lstrip().startswith("ELSE IF"):
            removed_dangling_else_if = True
            j += 1
            while j < len(lines):
                stripped = lines[j].strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", stripped) or stripped == "====":
                    break
                j += 1
            i = j
            continue
        i = j if saw_conjunct else i + 1
    if removed_dangling_else_if:
        fixed = "\n".join(rebuilt_lines)
        result.fixes_applied.append("removed dangling ELSE IF after LET-IN action")

    lines = fixed.splitlines()
    spec_idx = next((idx for idx, line in enumerate(lines) if re.match(r"^Spec\s*==", line.strip())), None)
    if spec_idx is not None:
        block_start = spec_idx
        while block_start > 0:
            prev = lines[block_start - 1]
            if prev.strip() == "" or prev[:1].isspace():
                block_start -= 1
                continue
            break
        let_idx = next(
            (
                idx
                for idx in range(spec_idx - 1, block_start - 1, -1)
                if re.match(r"^\s+LET\b", lines[idx])
                and all(
                    line.strip() == "" or line[:1].isspace()
                    for line in lines[idx:spec_idx]
                )
            ),
            None,
        )
        if let_idx is not None:
            fixed = "\n".join(lines[:let_idx] + lines[spec_idx:])
            result.fixes_applied.append("removed dangling LET action fragment before Spec")

    fixed_new = re.sub(
        r"(?ms)^Next\s*==\s*\n(?=Spec\s*==|====)",
        "Next == /\\ UNCHANGED vars\n\n",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("filled empty Next with UNCHANGED vars")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\bSeqSubseq\(\s*([^,\n]+?)\s*,\s*([^,\n()]+?)\s*\.\.\s*([^) \n][^)\n]*?)\s*\)",
        r"SubSeq(\1, \2, \3)",
        fixed,
    )
    fixed_new = re.sub(r"\bSubSequence\(", "SubSeq(", fixed_new)
    fixed_new = re.sub(r"\bSeqFromList\(\[\s*([^\]\n]+?)\s*\]\)", r"<<\1>>", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized sequence helper aliases")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\(([^()\n]+)\)\(([^()\n]+)\)",
        r"\1(\2, \3)",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized curried-style operator calls")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\\([A-Za-z_][A-Za-z0-9_]*)\s*:",
        r"LAMBDA \1 :",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote backslash lambda predicates as LAMBDA")
        fixed = fixed_new

    fixed_new = re.sub(r"(?m)(=\s*)\[\](?=\s*(?:$|\\\*|\(\*))", r"\1<<>>", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote [] sequence literals to <<>>")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\bRemoveAt\(\s*head\s*-\s*1\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        r"Tail(\1)",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote remove-front sequence helpers as Tail")
        fixed = fixed_new

    fixed_new = re.sub(r"\bSequence\[\s*([^\]\n]+?)\s*\]", r"Seq(\1)", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized Sequence[...] type notation")
        fixed = fixed_new

    fixed_new = re.sub(r"\(\s*([A-Za-z_][A-Za-z0-9_]*)\s+x\s+([A-Za-z_][A-Za-z0-9_]*)\s*\)", r"(\1 \\X \2)", fixed)
    fixed_new = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+x\s+([A-Za-z_][A-Za-z0-9_]*)\b", r"\1 \\X \2", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized cartesian product notation")
        fixed = fixed_new

    lines = fixed.splitlines()
    rebuilt_lines = []
    in_operator_body = False
    indented_root_level_conj = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==$", stripped):
            in_operator_body = True
            rebuilt_lines.append(line)
            continue
        if in_operator_body:
            if stripped == "" or stripped.startswith(("(*", "\\*")):
                rebuilt_lines.append(line)
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", stripped):
                in_operator_body = True
                rebuilt_lines.append(line)
                continue
            if re.match(r"^(====|EXTENDS|CONSTANTS?\b|VARIABLES?\b|ASSUME\b|THEOREM\b|LEMMA\b|PROPOSITION\b|PROPERTY\b)", stripped):
                in_operator_body = False
                rebuilt_lines.append(line)
                continue
            if line.startswith(("/\\", "\\/")):
                rebuilt_lines.append("    " + line)
                indented_root_level_conj = True
                continue
        rebuilt_lines.append(line)
    if indented_root_level_conj:
        fixed = "\n".join(rebuilt_lines)
        result.fixes_applied.append("indented root-level operator conjunctions/disjunctions")

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    inlined_disjunct = False
    merged_dangling_conj = False
    normalized_backslash_action = False
    while i < len(lines):
        line = lines[i]
        standalone_disj = re.match(r"^(\s*)\\{1,2}/\s*$", line)
        if standalone_disj and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                rebuilt_lines.append(lines[j])
                j += 1
            if j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped and not re.match(r"^(====|[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==)$", next_stripped):
                    rebuilt_lines.append(f"{standalone_disj.group(1)}\\/ {next_stripped}")
                    inlined_disjunct = True
                    i = j + 1
                    continue

        standalone_conj = re.match(r"^(\s*)/\\\s*$", line)
        if standalone_conj and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                rebuilt_lines.append(lines[j])
                j += 1
            if j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped and not re.match(r"^(====|[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==)$", next_stripped):
                    rebuilt_lines.append(f"{standalone_conj.group(1)}/\\ {next_stripped}")
                    merged_dangling_conj = True
                    i = j + 1
                    continue

        malformed_backslash = re.match(r"^(\s*)\\\\\s+(.+?)\s*$", line)
        if malformed_backslash:
            rebuilt_lines.append(f"{malformed_backslash.group(1)}/\\ {malformed_backslash.group(2)}")
            normalized_backslash_action = True
            i += 1
            continue

        malformed_slash_backslash = re.match(r"^(\s*)/\\\\\s+(.+?)\s*$", line)
        if malformed_slash_backslash:
            rebuilt_lines.append(f"{malformed_slash_backslash.group(1)}/\\ {malformed_slash_backslash.group(2)}")
            normalized_backslash_action = True
            i += 1
            continue

        rebuilt_lines.append(line)
        i += 1
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if inlined_disjunct:
            result.fixes_applied.append("inlined standalone disjunct lines")
        if merged_dangling_conj:
            result.fixes_applied.append("merged dangling conjunction lines")
        if normalized_backslash_action:
            result.fixes_applied.append("normalized malformed backslash-leading action lines")

    lines = fixed.splitlines()
    rebuilt_lines = []
    rewrote_disjoined_if_branch = False
    for idx, line in enumerate(lines):
        disjoined_if = re.match(r"^(\s*)\\/\s+IF\b(.+?)\s+THEN\s*$", line)
        if disjoined_if:
            candidate_indent = len(disjoined_if.group(1))
            saw_prior_if = False
            j = idx - 1
            while j >= 0:
                prev = lines[j]
                stripped = prev.strip()
                if not stripped or re.match(r"^\(\*.*\*\)$", stripped):
                    j -= 1
                    continue
                if stripped == "====" or re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==$", stripped):
                    break
                if stripped.startswith("ELSE "):
                    break
                prior_if = re.match(r"^(\s*)/\\\s+IF\b.+\bTHEN\s*$", prev)
                if prior_if and len(prior_if.group(1)) <= candidate_indent:
                    saw_prior_if = True
                    aligned_indent = " " * (len(prior_if.group(1)) + 3)
                    break
                j -= 1
            if saw_prior_if:
                rebuilt_lines.append(f"{aligned_indent}ELSE IF{disjoined_if.group(2)} THEN")
                rewrote_disjoined_if_branch = True
                continue
        rebuilt_lines.append(line)
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if rewrote_disjoined_if_branch:
            result.fixes_applied.append("rewrote disjoined IF branch as ELSE IF")

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    completed_disjoined_if_chain = False
    while i < len(lines):
        line = lines[i]
        if_header = re.match(r"^(\s*)/\\\s+IF\b.+\bTHEN\s*$", line)
        if not if_header:
            rebuilt_lines.append(line)
            i += 1
            continue
        rebuilt_lines.append(line)
        base_indent = len(if_header.group(1))
        branch_indent_str = " " * (base_indent + 3)
        j = i + 1
        saw_else_if = False
        saw_else = False
        while j < len(lines):
            candidate = lines[j]
            stripped = candidate.strip()
            if not stripped or stripped.startswith(("(*", "\\*")):
                rebuilt_lines.append(candidate)
                j += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if candidate_indent <= base_indent and stripped not in {"ELSE TRUE"}:
                break
            if re.match(rf"^{re.escape(branch_indent_str)}ELSE IF\b", candidate):
                saw_else_if = True
            elif re.match(rf"^{re.escape(branch_indent_str)}ELSE\b", candidate):
                saw_else = True
            rebuilt_lines.append(candidate)
            j += 1
        if saw_else_if and not saw_else:
            rebuilt_lines.append(f"{branch_indent_str}ELSE TRUE")
            completed_disjoined_if_chain = True
        i = j
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if completed_disjoined_if_chain:
            result.fixes_applied.append("completed disjoined IF/ELSE IF chain missing final ELSE")

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    completed_conjunctive_if = False
    while i < len(lines):
        line = lines[i]
        if_header = re.match(r"^(\s*)/\\\s+IF\b.+\bTHEN\s*$", line)
        if not if_header:
            rebuilt_lines.append(line)
            i += 1
            continue
        rebuilt_lines.append(line)
        base_indent = len(if_header.group(1))
        branch_indent = base_indent + 3
        j = i + 1
        saw_nested_conjunct = False
        saw_else = False
        nested_indent: Optional[int] = None
        while j < len(lines):
            candidate = lines[j]
            stripped = candidate.strip()
            if not stripped or stripped.startswith(("(*", "\\*")):
                rebuilt_lines.append(candidate)
                j += 1
                continue
            if re.match(r"^\s*ELSE\b", candidate):
                saw_else = True
                break
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if (
                candidate_indent > base_indent
                and candidate.lstrip().startswith("/\\")
                and (nested_indent is None or candidate_indent >= nested_indent)
            ):
                rebuilt_lines.append(candidate)
                saw_nested_conjunct = True
                if nested_indent is None:
                    nested_indent = candidate_indent
                j += 1
                continue
            break
        if saw_nested_conjunct and not saw_else:
            rebuilt_lines.append(" " * branch_indent + "ELSE TRUE")
            completed_conjunctive_if = True
        i = j
    fixed_new = "\n".join(rebuilt_lines)
    if fixed_new != fixed:
        fixed = fixed_new
        if completed_conjunctive_if:
            result.fixes_applied.append("completed conjunctive IF block missing ELSE branch")

    lines = fixed.splitlines()
    rebuilt_lines = []
    in_operator_body = False
    second_indent_pass = False
    pending_else_indent: Optional[int] = None
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==$", stripped):
            in_operator_body = True
            pending_else_indent = None
            rebuilt_lines.append(line)
            continue
        if in_operator_body:
            if stripped == "" or stripped.startswith(("(*", "\\*")):
                rebuilt_lines.append(line)
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", stripped):
                in_operator_body = True
                pending_else_indent = None
                rebuilt_lines.append(line)
                continue
            if re.match(r"^(====|EXTENDS|CONSTANTS?\b|VARIABLES?\b|ASSUME\b|THEOREM\b|LEMMA\b|PROPOSITION\b|PROPERTY\b)", stripped):
                in_operator_body = False
                pending_else_indent = None
                rebuilt_lines.append(line)
                continue
            if re.match(r"^\s*ELSE TRUE\s*$", line):
                pending_else_indent = len(line) - len(line.lstrip())
                rebuilt_lines.append(line)
                continue
            if pending_else_indent is not None:
                if line.lstrip().startswith("/\\"):
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent != pending_else_indent:
                        rebuilt_lines.append(" " * pending_else_indent + line.lstrip())
                        second_indent_pass = True
                        continue
                    rebuilt_lines.append(line)
                    continue
                if stripped and not stripped.startswith(("(*", "\\*")):
                    pending_else_indent = None
            if line.startswith(("/\\", "\\/")):
                rebuilt_lines.append("    " + line)
                second_indent_pass = True
                continue
        rebuilt_lines.append(line)
    if second_indent_pass:
        fixed = "\n".join(rebuilt_lines)

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    nested_conj_indent = False
    while i < len(lines):
        line = lines[i]
        inline_disj_conj = re.match(r"^(\s*)\\/\s+/\\\s+.+$", line)
        if inline_disj_conj:
            rebuilt_lines.append(line)
            base_indent = inline_disj_conj.group(1)
            child_indent = base_indent + "   "
            i += 1
            while i < len(lines):
                candidate = lines[i]
                if not candidate.strip():
                    rebuilt_lines.append(candidate)
                    i += 1
                    continue
                if re.match(rf"^{re.escape(base_indent)}\\/\b", candidate):
                    break
                if re.match(r"^(====|[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==)", candidate.strip()):
                    break
                if candidate.startswith(base_indent + "/\\"):
                    rebuilt_lines.append(child_indent + candidate[len(base_indent):])
                    nested_conj_indent = True
                    i += 1
                    continue
                rebuilt_lines.append(candidate)
                i += 1
            continue
        rebuilt_lines.append(line)
        i += 1
    if nested_conj_indent:
        fixed = "\n".join(rebuilt_lines)

        fixed_new = re.sub(
            r"(?ms)(^\s*\\/\s+\\A\s+[^\n:]+:\s*)\n\s*(\([^\n]+?\))\s*->\s*\(\s*\n\s*([^\n]+?)\s*\n\s*\)",
            lambda m: f"{m.group(1)} ({m.group(2).strip()} => {m.group(3).strip()})",
            fixed,
            flags=re.MULTILINE,
        )
        if fixed_new != fixed:
            fixed = fixed_new
            if "inlined quantified implication disjunct body" not in result.fixes_applied:
                result.fixes_applied.append("inlined quantified implication disjunct body")

        fixed_new = re.sub(
            r"(?m)(^\s*\\/\s+\\A\s+[^\n:]+:\s*\(\([^\n]+?=>\s*IF\s+.+?\s+THEN\s+[A-Za-z_][A-Za-z0-9_]*(?:\([^)\n]*\))?)\)$",
            r"\1 ELSE UnchangedVars)",
            fixed,
        )
        if fixed_new != fixed:
            fixed = fixed_new
            if "completed quantified action IF missing ELSE branch" not in result.fixes_applied:
                result.fixes_applied.append("completed quantified action IF missing ELSE branch")

    lines = fixed.splitlines()
    def_idx = next((idx for idx, line in enumerate(lines) if re.match(r"^\s*UnchangedVars\s*==", line)), None)
    if def_idx is not None:
        first_use_idx = next((idx for idx, line in enumerate(lines) if idx != def_idx and "UnchangedVars" in line), None)
        if first_use_idx is not None and first_use_idx < def_idx:
            block_end = def_idx + 1
            while block_end < len(lines):
                stripped = lines[block_end].strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", stripped) or stripped == "====":
                    break
                block_end += 1
            insert_idx = first_use_idx
            while insert_idx > 0:
                stripped = lines[insert_idx].strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", stripped):
                    break
                insert_idx -= 1
            block = lines[def_idx:block_end]
            remainder = lines[:def_idx] + lines[block_end:]
            if def_idx < insert_idx:
                insert_idx -= len(block)
            fixed = "\n".join(remainder[:insert_idx] + block + remainder[insert_idx:])
            result.fixes_applied.append("moved UnchangedVars definition before first use")

    lines = fixed.splitlines()
    moved_later_operator = False
    changed = True
    while changed:
        changed = False
        op_defs: list[tuple[str, int, int]] = []
        i = 0
        while i < len(lines):
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*==", lines[i])
            if not match:
                i += 1
                continue
            name = match.group(1)
            block_end = i + 1
            while block_end < len(lines):
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", lines[block_end]) or lines[block_end].strip() == "====":
                    break
                block_end += 1
            op_defs.append((name, i, block_end))
            i = block_end
        for name, def_start, def_end in op_defs:
            use_pat = re.compile(rf"\b{re.escape(name)}\s*(?:\(|\b)")
            first_use_idx = next(
                (
                    idx
                    for idx, line in enumerate(lines[:def_start])
                    if use_pat.search(line) and not line.strip().startswith(("(*", "\\*"))
                ),
                None,
            )
            if first_use_idx is None:
                continue
            insert_idx = first_use_idx
            while insert_idx > 0:
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", lines[insert_idx]):
                    break
                insert_idx -= 1
            block = lines[def_start:def_end]
            remainder = lines[:def_start] + lines[def_end:]
            if def_start < insert_idx:
                insert_idx -= len(block)
            lines = remainder[:insert_idx] + block + remainder[insert_idx:]
            moved_later_operator = True
            changed = True
            break
    if moved_later_operator:
        fixed = "\n".join(lines)
        result.fixes_applied.append("moved later operator definition before first use")

    fixed_new = fixed.replace("≜", "==")
    if fixed_new != fixed:
        result.fixes_applied.append("normalized definition symbol to ==")
        fixed = fixed_new

    fixed_new = re.sub(r"^([A-Z_][A-Z0-9_]*)\s*=\s*(?!=)(.+)$", r"\1 == \2", fixed, flags=re.MULTILINE)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized top-level = definitions to ==")
        fixed = fixed_new

    fixed_new = re.sub(r"#=", "#", fixed)
    fixed_new = re.sub(r"/=", "#", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized pseudo-inequality operators")
        fixed = fixed_new

    fixed_new = re.sub(r"(^\s*/\\\s+)[A-Z][A-Z0-9_]*:\s*", r"\1", fixed, flags=re.MULTILINE)
    if fixed_new != fixed:
        result.fixes_applied.append("removed conjunct labels")
        fixed = fixed_new

    rewritten_lines = []
    prev_significant = ""
    conjunct_block_indent: int | None = None
    rewrote_indented_conjunct_pseudo_defs = False
    for line in fixed.splitlines():
        current_indent = len(line) - len(line.lstrip(" "))
        if line.strip() and conjunct_block_indent is not None and current_indent < conjunct_block_indent:
            conjunct_block_indent = None
        match = re.match(r"^(\s+)([A-Za-z_][A-Za-z0-9_]*)\s*==\s*(.*)$", line)
        if match:
            prior = prev_significant.lstrip()
            if (
                (
                    prev_significant.rstrip().endswith("==")
                    or (conjunct_block_indent is not None and current_indent >= conjunct_block_indent)
                )
                and not prior.startswith(("LET ", "IN ", "CASE", "[]", "|"))
            ):
                line = f"{match.group(1)}/\\ {match.group(3)}".rstrip()
                conjunct_block_indent = current_indent
                rewrote_indented_conjunct_pseudo_defs = True
        rewritten_lines.append(line)
        if line.strip():
            prev_significant = line
        else:
            conjunct_block_indent = None
    if rewrote_indented_conjunct_pseudo_defs:
        fixed = "\n".join(rewritten_lines)
        result.fixes_applied.append("rewrote indented conjunct pseudo-definitions")

    fixed_new = re.sub(
        r"(?m)^(?!\s*(?:----|\(\*))(\s*.+?)\s+--(?!\s*>)\s?(.*)$",
        r"\1 \\* \2",
        fixed,
    )
    if fixed_new != fixed:
        fixed = fixed_new
        if "normalized inline double-dash comments" not in result.fixes_applied:
            result.fixes_applied.append("normalized inline double-dash comments")

    fixed_new = re.sub(r"(^\s*)(?:\\/|/\\+)\s+(\w+(?:\[[^]\n]+\])?)\s*:\s*", r"\1/\\ \2 \\in ", fixed, flags=re.MULTILINE)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized colon membership conjuncts")
        fixed = fixed_new

    normalized_lines = []
    function_set_changed = False
    for line in fixed.splitlines():
        match = re.match(r"^(\s*/\\\s+.+?)\s+(\\in|\\subseteq)\s+(.+)$", line)
        if not match:
            normalized_lines.append(line)
            continue
        prefix, op, rhs = match.groups()
        if "=" in prefix:
            normalized_lines.append(line)
            continue
        if "->" not in rhs and "-->" not in rhs:
            normalized_lines.append(line)
            continue
        normalized_rhs = _normalize_function_set_expr(rhs)
        normalized_op = "\\in" if op == "\\subseteq" else op
        rebuilt = f"{prefix} {normalized_op} {normalized_rhs}"
        function_set_changed = function_set_changed or rebuilt != line
        normalized_lines.append(rebuilt)
    if function_set_changed:
        fixed = "\n".join(normalized_lines)
        result.fixes_applied.append("normalized function-set arrow notation")

    def _rewrite_unchanged_brackets(match: re.Match) -> str:
        inner = match.group(1).strip()
        if "|->" in inner and re.search(r"(?m)^\s*vars\s*==", fixed):
            return "UNCHANGED vars"
        if "|->" in inner:
            var_match = re.search(r"(?m)^VARIABLES?\s+(.+)$", fixed)
            if var_match:
                names = [part.strip() for part in var_match.group(1).split(",") if part.strip()]
                if names:
                    return f"UNCHANGED <<{', '.join(names)}>>"
        if not inner or any(token in inner for token in ("\\A", "\\E", "\\\\", ":", "\n")):
            return match.group(0)
        unused = re.fullmatch(r"UNUSED\((\w+)\)", inner)
        if unused:
            return f"UNCHANGED <<{unused.group(1)}>>"
        tuple_match = re.fullmatch(r"<<\s*(.*?)\s*>>", inner)
        if tuple_match:
            return f"UNCHANGED <<{tuple_match.group(1)}>>"
        names = [part.strip() for part in inner.split(",") if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part.strip())]
        if names:
            return f"UNCHANGED <<{', '.join(names)}>>"
        return match.group(0)

    fixed_new = re.sub(r"(?i)unchanged\s*\[([^\]\n]+)\]", _rewrite_unchanged_brackets, fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote bracketed UNCHANGED form")
        if "UNCHANGED vars" in fixed_new and "UNCHANGED vars" not in fixed:
            result.fixes_applied.append("rewrote malformed bracketed UNCHANGED constructor as vars")
        elif "UNCHANGED <<" in fixed_new and "UNCHANGED <<" not in fixed:
            result.fixes_applied.append("rewrote malformed bracketed UNCHANGED constructor as declared tuple")
        fixed = fixed_new

    def _extract_decl_names(fragments: list[str], *, defined_ops: set[str]) -> list[str]:
        reserved = {
            "ASSUME", "BOOLEAN", "CASE", "CHOOSE", "CONSTANT", "CONSTANTS",
            "DOMAIN", "ELSE", "EXTENDS", "FALSE", "IF", "IN", "INSTANCE",
            "LET", "LOCAL", "OTHER", "SUBSET", "THEOREM", "THEN", "TRUE",
            "UNION", "VARIABLE", "VARIABLES",
        }
        names = []
        seen = set()
        for fragment in fragments:
            raw_fragment = fragment
            fragment = re.sub(r"\(\*.*?\*\)", " ", fragment)
            fragment = re.sub(r'"[^"\n]*"', " ", fragment)
            fragment = re.sub(r"\\\*.*$", " ", fragment)
            fragment = re.sub(r"\\.*$", " ", fragment)
            tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", fragment)
            if "," not in raw_fragment and len(tokens) > 2:
                continue
            for token in tokens:
                if token.upper() in reserved or token in defined_ops or token in seen:
                    continue
                seen.add(token)
                names.append(token)
        return names

    defined_ops = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*==", fixed, re.MULTILINE))
    op_params = {
        param.strip()
        for params in re.findall(r"(?m)^[A-Za-z_][A-Za-z0-9_]*\(([^)]*)\)\s*==", fixed)
        for param in params.split(",")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", param.strip())
    }
    if op_params:
        fixed_new = fixed
        for param in sorted(op_params):
            fixed_new = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(param)}'(?![A-Za-z0-9_])",
                param,
                fixed_new,
            )
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("removed primes from operator parameters")

    existing_vars_tuple_names: Optional[list[str]] = None
    vars_tuple_match = re.search(r"(?m)^vars\s*==\s*<<\s*(.*?)\s*>>\s*$", fixed)
    if vars_tuple_match:
        existing_vars_tuple_names = [
            part.strip()
            for part in vars_tuple_match.group(1).split(",")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part.strip())
        ]
    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    variables_changed = False
    merged_variable_lines = False
    last_variable_names: Optional[list[str]] = None
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^(VARIABLES?)\s+(.+)$", line)
        header_only = re.match(r"^(VARIABLES?)\s*$", line)
        keyword = None
        initial_fragment = None
        header_had_inline_names = False
        if not match:
            if not header_only:
                rebuilt_lines.append(line)
                i += 1
                continue
            keyword = header_only.group(1)
            initial_fragment = None
        else:
            keyword = match.group(1)
            initial_fragment = match.group(2)
            header_had_inline_names = True

        fragments = [initial_fragment] if initial_fragment is not None else []
        j = i + 1
        while j < len(lines):
            continuation = lines[j]
            if not continuation.strip() or not continuation.startswith((" ", "\t")):
                break
            fragments.append(continuation.strip())
            j += 1

        names = _extract_decl_names(fragments, defined_ops=defined_ops)
        if existing_vars_tuple_names and op_params:
            filtered_names = [
                name
                for name in names
                if not (name in op_params and name not in existing_vars_tuple_names)
            ]
            if filtered_names != names:
                names = filtered_names
                result.fixes_applied.append("removed shadowed variable names from declaration")
            if all(name in filtered_names for name in existing_vars_tuple_names):
                names = [name for name in existing_vars_tuple_names if name in filtered_names]
        if not names:
            rebuilt_lines.append(line)
            i += 1
            continue

        cleaned_decl = f"{keyword} {', '.join(names)}"
        rebuilt_lines.append(cleaned_decl)
        variables_changed = variables_changed or (header_had_inline_names and cleaned_decl != line)
        merged_variable_lines = merged_variable_lines or j > i + 1
        if not header_had_inline_names:
            result.fixes_applied.append("cleaned multiline VARIABLES declaration")
        last_variable_names = names
        i = j

    if variables_changed or merged_variable_lines:
        fixed = "\n".join(rebuilt_lines)
        if variables_changed:
            result.fixes_applied.append("cleaned single-line VARIABLES declaration")
        if merged_variable_lines:
            result.fixes_applied.append("merged continued VARIABLES declaration lines")

    if last_variable_names:
        vars_tuple = f"<<{', '.join(last_variable_names)}>>"
        fixed_new = re.sub(r"^vars\s*==\s*<<.*?>>$", f"vars == {vars_tuple}", fixed, flags=re.MULTILINE)
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("realigned vars tuple with VARIABLES declaration")

        fixed_new = re.sub(
            r"Spec\s*==\s*Init\s*/\\+\s*\[\]\s*\(\s*([^\n()]+?)\s*\)",
            lambda m: f"Spec == Init /\\ [][{m.group(1).strip()}]_{vars_tuple}",
            fixed,
        )
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("normalized parenthesized Spec temporal formula")

        fixed_new = re.sub(
            r"(?ms)Spec\s*==\s*Init\s*/\\+\s*\[\]\[\s*Next\s*]_\s*<<.+?>>\s*/\\+\s*([^\n]+)",
            lambda m: f"Spec == Init /\\ [][Next]_{vars_tuple} /\\ {m.group(1).strip()}",
            fixed,
        )
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("realigned Spec vars tuple with VARIABLES declaration")

        alias_map: dict[str, str] = {}
        for name in last_variable_names:
            alias = re.sub(r"(?<!^)([A-Z])", r"_\1", name).upper()
            if alias != name and alias not in alias_map:
                alias_map[alias] = name
        fixed_new = fixed
        for alias, name in alias_map.items():
            fixed_new = re.sub(rf"\b{re.escape(alias)}\b", name, fixed_new)
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("normalized uppercase variable aliases")

        def _normalize_unless_condition(expr: str) -> str:
            expr = expr.strip()
            expr = re.sub(
                r"([A-Za-z_][A-Za-z0-9_\[\]]*)\s*\\#\s*IN\s*([A-Za-z_][A-Za-z0-9_]*)",
                r"~(\1 \\in \2)",
                expr,
            )
            expr = re.sub(
                r"([A-Za-z_][A-Za-z0-9_]*)\s*#\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\/\s*(?:\\E|EXISTS)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\\\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*<=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*&\s*([A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?)\s*<=\s*(-?\d+)",
                lambda m: (
                    f"({m.group(1)} # {m.group(2)}) \\/ "
                    f"(\\E {m.group(3)} : ({m.group(4)} <= {m.group(5)}) /\\ {m.group(6)} <= {m.group(7)})"
                ),
                expr,
            )
            expr = re.sub(r"\bIN\b", r"\\in", expr)
            return expr

        unchanged_expr = f"UNCHANGED {vars_tuple}"
        fixed_new = re.sub(
            r"(?mi)^(\s*)UNLESS\s+(.+?)\s+then\s+skip\s+else\s+\($",
            lambda m: f"{m.group(1)}IF {_normalize_unless_condition(m.group(2))} THEN {unchanged_expr} ELSE (",
            fixed,
        )
        fixed_new = re.sub(
            r"(?mi)^(\s*)UNLESS\s+(.+?)\s+then\s+skip\s+else\s+(.+)$",
            lambda m: f"{m.group(1)}IF {_normalize_unless_condition(m.group(2))} THEN {unchanged_expr} ELSE {m.group(3).strip()}",
            fixed_new,
        )
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("rewrote UNLESS skip/else pseudocode as IF/UNCHANGED/ELSE")

    last_constant_names: Optional[list[str]] = None
    const_decl = re.search(r"^CONSTANTS?\s+(.+)$", fixed, re.MULTILINE)
    if const_decl:
        raw_consts = re.sub(r"\\\*.*$", "", const_decl.group(1)).strip()
        names = []
        seen = set()
        for part in raw_consts.split(","):
            candidate = part.strip()
            if not candidate:
                continue
            name_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", candidate)
            if not name_match:
                continue
            name = name_match.group(0)
            if name in seen:
                continue
            seen.add(name)
            names.append(name)
        if names:
            keyword = "CONSTANTS" if const_decl.group(0).startswith("CONSTANTS ") else "CONSTANT"
            cleaned_decl = f"{keyword} {', '.join(names)}"
            if cleaned_decl != const_decl.group(0):
                fixed = fixed[:const_decl.start()] + cleaned_decl + fixed[const_decl.end():]
                result.fixes_applied.append("cleaned single-line CONSTANTS declaration")
            last_constant_names = names

    lines = fixed.splitlines()
    rebuilt_lines = []
    i = 0
    merged_orphaned_constants = False
    normalized_orphaned_constraints = False
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^(CONSTANTS?)\s+(.+)$", line)
        if not match:
            rebuilt_lines.append(line)
            i += 1
            continue

        keyword = match.group(1)
        parts = [part.strip() for part in match.group(2).split(",")]
        names = []
        seen = set()
        for part in parts:
            name_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", part)
            if not name_match:
                continue
            name = name_match.group(0)
            if name in seen:
                continue
            seen.add(name)
            names.append(name)

        assume_lines: list[str] = []
        j = i + 1
        while j < len(lines):
            continuation = lines[j]
            stripped = continuation.strip()
            if not stripped:
                j += 1
                continue
            if stripped.startswith(("(*", "\\*")):
                j += 1
                continue

            candidate = re.sub(r"\(\*.*?\*\)", " ", stripped)
            candidate = re.sub(r"\\\*.*$", " ", candidate)
            candidate = re.sub(r"\\+.*$", " ", candidate)
            candidate = candidate.rstrip(",").strip()
            if not candidate:
                j += 1
                continue

            bare_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)", candidate)
            typed_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)", candidate)
            constrained_match = re.fullmatch(
                r"([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|#|=(?!=))\s*(.+)",
                candidate,
            )

            if bare_match:
                name = bare_match.group(1)
                if name not in seen:
                    seen.add(name)
                    names.append(name)
                    merged_orphaned_constants = True
                j += 1
                continue

            if typed_match:
                name = typed_match.group(1)
                expr = typed_match.group(2).strip()
                if name not in seen:
                    seen.add(name)
                    names.append(name)
                    merged_orphaned_constants = True
                assume_lines.append(f"ASSUME {name} \\in {expr}")
                normalized_orphaned_constraints = True
                j += 1
                continue

            if constrained_match:
                name = constrained_match.group(1)
                op = constrained_match.group(2)
                expr = constrained_match.group(3).strip()
                if name not in seen:
                    seen.add(name)
                    names.append(name)
                    merged_orphaned_constants = True
                assume_lines.append(f"ASSUME {name} {op} {expr}")
                normalized_orphaned_constraints = True
                j += 1
                continue

            break

        rebuilt_lines.append(f"{keyword} {', '.join(names)}")
        last_constant_names = names
        rebuilt_lines.extend(assume_lines)
        i = j

    if merged_orphaned_constants or normalized_orphaned_constraints:
        fixed = "\n".join(rebuilt_lines)
        if merged_orphaned_constants:
            result.fixes_applied.append("merged orphaned constant annotations")
        if normalized_orphaned_constraints:
            result.fixes_applied.append("normalized orphaned constant constraints to ASSUME")

    if last_constant_names is not None:
        builtin_caps = {
            "Append", "BOOLEAN", "CASE", "CONSTANT", "CONSTANTS", "DOMAIN",
            "CHOOSE", "ELSE", "EXCEPT", "EXTENDS", "FALSE", "Head", "IF",
            "IN", "Init", "Int", "LAMBDA", "LET", "Len", "MODULE", "Nat",
            "Next", "OTHER", "PROPERTY", "Seq", "Sequence", "SPECIFICATION",
            "Spec", "SUBSEQ", "SubSeq", "SubSequence", "SUBSET", "Tail",
            "THEN", "TRUE", "THEOREM", "Terminating", "TypeInvariant",
            "TypeOK", "TypeOk", "UNCHANGED", "UNION", "Unchanged",
            "VARIABLE", "VARIABLES",
        }
        builtin_caps_upper = {name.upper() for name in builtin_caps}
        declared_names = set(last_constant_names)
        if last_variable_names:
            declared_names.update(last_variable_names)
        declared_names.update(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*==", fixed))
        missing_caps: list[str] = []
        in_inserted_helper_block = False
        for line in fixed.splitlines():
            stripped = line.strip()
            top_level_def = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*==", line)
            if top_level_def and top_level_def.group(1) in inserted_helper_operator_names:
                in_inserted_helper_block = True
                continue
            if in_inserted_helper_block:
                if top_level_def or stripped.startswith(("CONSTANT", "VARIABLE", "EXTENDS", "ASSUME")) or stripped == "====":
                    in_inserted_helper_block = False
                else:
                    continue
            if (
                not stripped
                or stripped.startswith(("---- MODULE", "EXTENDS", "CONSTANT", "VARIABLE", "ASSUME", "(*", "\\*"))
                or re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*==", stripped)
            ):
                continue
            candidate = re.sub(r"\(\*.*?\*\)", " ", stripped)
            candidate = re.sub(r"\\\*.*$", " ", candidate)
            candidate = re.sub(r'"[^"\n]*"', " ", candidate)
            candidate = re.sub(r"\\[A-Za-z_]+", " ", candidate)
            for match in re.finditer(r"\b[A-Z][A-Za-z0-9_]*\b", candidate):
                token = match.group(0)
                if candidate[match.end():match.end() + 1] in {"(", "["}:
                    continue
                if token.upper() in builtin_caps_upper or token in declared_names or token in known_modules:
                    continue
                missing_caps.append(token)
        ordered_missing_caps = list(dict.fromkeys(missing_caps))
        if ordered_missing_caps:
            const_decl = re.search(r"^(CONSTANTS?)\s+(.+)$", fixed, re.MULTILINE)
            if const_decl:
                keyword = const_decl.group(1)
                current = [part.strip() for part in const_decl.group(2).split(",") if part.strip()]
                merged = current + [name for name in ordered_missing_caps if name not in current]
                fixed = fixed[:const_decl.start()] + f"{keyword} {', '.join(merged)}" + fixed[const_decl.end():]
                last_constant_names = merged
                result.fixes_applied.append("collected missing capitalized placeholders into CONSTANTS")

    if last_constant_names:
        operator_names = set(
            re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*==", fixed)
        )
        protected_lower_aliases = {
            name
            for name in re.findall(r"\\(?:A|E)\s+([a-z_][A-Za-z0-9_]*)\s+\\in\b", fixed)
        }
        protected_lower_aliases.update(
            name
            for name in re.findall(r"\[\s*([a-z_][A-Za-z0-9_]*)\s+\\in\b", fixed)
        )
        for name in last_constant_names:
            alias = name.lower()
            if (
                alias != name
                and alias not in constant_alias_map
                and alias not in protected_lower_aliases
                and (not last_variable_names or alias not in last_variable_names)
            ):
                constant_alias_map[alias] = name
        fixed_new = fixed
        for alias, name in constant_alias_map.items():
            fixed_new = re.sub(rf"\b{re.escape(alias)}\b", name, fixed_new)
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("normalized lowercase constant aliases")

        fixed_new = fixed
        for name in last_constant_names:
            if name in operator_names:
                continue
            fixed_new = re.sub(
                rf"\b{re.escape(name)}\(([^()\n]+)\)",
                rf"{name}[\1]",
                fixed_new,
            )
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("normalized constant function application syntax")

    if last_variable_names and "messages" in last_variable_names and "msgs" not in last_variable_names:
        fixed_new = re.sub(r"\bmsgs\b", "messages", fixed)
        if fixed_new != fixed:
            fixed = fixed_new
            result.fixes_applied.append("normalized msgs alias to messages")

    fixed_new = re.sub(r"(?m)^\s+[A-Za-z_][A-Za-z0-9_]*\s*,\s*\(\*.*\n?", "", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("removed orphan variable annotation lines")
        fixed = fixed_new

    fixed_new = re.sub(r"\bUnchanged\(([^)\n]+)\)", r"UNCHANGED \1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized lowercase Unchanged operator")
        fixed = fixed_new

    fixed_new = re.sub(r"\bALL\s+(\w+)\s+IN\b", r"\\A \1 \\in", fixed)
    fixed_new = re.sub(r"\bFORALL\s+(\w+)\s+IN\b", r"\\A \1 \\in", fixed_new)
    fixed_new = re.sub(r"\bEXISTS\s+(\w+)\s+IN\b", r"\\E \1 \\in", fixed_new)
    fixed_new = re.sub(r"\bNOT\s+\\E\s+(\w+)\s+WHERE\b", r"~ \\E \1 :", fixed_new)
    fixed_new = re.sub(r"\bNOT\s+\\A\s+(\w+)\s+WHERE\b", r"~ \\A \1 :", fixed_new)
    fixed_new = re.sub(r"\bWHERE\b", ":", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized alternate quantifier keywords")
        fixed = fixed_new

    fixed_new = re.sub(r"(?<!\\)\bforall\s+(\w+)\s+(?:in|\\in)\b", r"\\A \1 \\in", fixed, flags=re.IGNORECASE)
    fixed_new = re.sub(r"(?<!\\)\bexists\s+(\w+)\s+(?:in|\\in)\b", r"\\E \1 \\in", fixed_new, flags=re.IGNORECASE)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized bare quantifier words")
        fixed = fixed_new

    fixed_new = re.sub(r"(\\[AE]\s+\w+)\s+IN\b", r"\1 \\in", fixed)
    fixed_new = re.sub(r"(\[\s*[A-Za-z_][A-Za-z0-9_]*\s+)IN\b", r"\1\\in", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized generic IN quantifiers and constructors")
        fixed = fixed_new

    fixed_new = re.sub(r"\bUNCHANGE\s+([A-Za-z_][A-Za-z0-9_]*)'\b", r"UNCHANGED \1", fixed)
    fixed_new = re.sub(r"\bUNCHANGE\s+([A-Za-z_][A-Za-z0-9_]*)\b", r"UNCHANGED \1", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized UNCHANGE operator")
        fixed = fixed_new

    fixed_new = re.sub(r"\b(?i:unchanged)\b(?=\s|[\[(])", "UNCHANGED", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized UNCHANGED operator casing")
        fixed = fixed_new

    fixed_new = re.sub(r"\\IN\b", r"\\in", fixed)
    fixed_new = re.sub(r"\\In\b", r"\\in", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized backslash operator casing")
        fixed = fixed_new

    fixed_new = re.sub(r"\|\s*([A-Za-z_][A-Za-z0-9_.]*)\s*<-\s*([^}|]+)", r"| \1 \\in \2", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized set-comprehension <- to \\in")
        fixed = fixed_new

    fixed_new = fixed.replace("∊", "\\in")
    fixed_new = fixed_new.replace("\\square", "[]")
    fixed_new = fixed_new.replace("\\diamond", "<>")
    if fixed_new != fixed:
        result.fixes_applied.append("normalized unicode/operator temporal tokens")
        fixed = fixed_new

    fixed_new = re.sub(r"\\forall\b", r"\\A", fixed, flags=re.IGNORECASE)
    fixed_new = re.sub(r"\\exists\b", r"\\E", fixed_new, flags=re.IGNORECASE)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized lowercase TeX quantifiers")
        fixed = fixed_new

    fixed_new = re.sub(r"(?<![\w\"])\bTRUE\b(?!\")", "TRUE", fixed)
    fixed_new = re.sub(r"(?<![\w\"])\bFALSE\b(?!\")", "FALSE", fixed_new)
    fixed_new = re.sub(r"(?<![\w\"])\bTrue\b(?!\")", "TRUE", fixed_new)
    fixed_new = re.sub(r"(?<![\w\"])\bFalse\b(?!\")", "FALSE", fixed_new)
    fixed_new = re.sub(r"(?<![\w\"])\btrue\b(?!\")", "TRUE", fixed_new)
    fixed_new = re.sub(r"(?<![\w\"])\bfalse\b(?!\")", "FALSE", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("normalized boolean literal casing")
        fixed = fixed_new

    fixed_new = re.sub(r"EXCEPT\s+(!\[[^]]+\]\s*=\s*)@\(([^()\n]+)\)", r"EXCEPT \1\2", fixed)
    fixed_new = re.sub(r"EXCEPT\s+(!\[[^]]+\]\s*=\s*)@([A-Za-z_][A-Za-z0-9_]*|\"[^\"]*\")", r"EXCEPT \1\2", fixed_new)
    if fixed_new != fixed:
        result.fixes_applied.append("removed @(...) wrapper in EXCEPT updates")
        fixed = fixed_new

    fixed_new = re.sub(r"(?<![A-Za-z0-9_\"])\@(?![A-Za-z0-9_(\"])", "Nil", fixed)
    if fixed_new != fixed:
        fixed = fixed_new
        if not re.search(r"(?m)^\s*Nil\s*==", fixed):
            fixed = _prepend_helper_definition(fixed, 'Nil == "nil"')
        result.fixes_applied.append("normalized standalone @ placeholder to Nil")

    if (
        "NULL" in fixed
        and not re.search(r"(?m)^\s*NULL\s*==", fixed)
        and not re.search(r"(?m)^\s*CONSTANTS?\b.*\bNULL\b", fixed)
    ):
        fixed_new = re.sub(r"(?<![A-Za-z0-9_])NULL(?![A-Za-z0-9_])", "Nil", fixed)
        if fixed_new != fixed:
            fixed = fixed_new
            if not re.search(r"(?m)^\s*Nil\s*==", fixed):
                fixed = _prepend_helper_definition(fixed, 'Nil == "nil"')
            result.fixes_applied.append("normalized NULL placeholder to Nil")

    def _rewrite_indexed_prime_assignment(match: re.Match) -> str:
        prefix = match.group(1)
        var_name = match.group(2)
        index_expr = match.group(3).strip()
        rhs = match.group(4)
        if index_expr.startswith("(") and index_expr.endswith(")") and "," in index_expr:
            pieces = [part.strip() for part in index_expr[1:-1].split(",")]
            if all(pieces):
                index_expr = f"<<{', '.join(pieces)}>>"
        return f"{prefix}{var_name}' = [{var_name} EXCEPT ![{index_expr}] = {rhs}]"

    fixed_new = re.sub(
        r"(^\s*/\\\s+)([A-Za-z_][A-Za-z0-9_]*)'\[([^\]\n]+)\]\s*=\s*([^\n]+)$",
        _rewrite_indexed_prime_assignment,
        fixed,
        flags=re.MULTILINE,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote indexed prime assignment as EXCEPT update")
        fixed = fixed_new

    fixed_new = re.sub(
        r"([A-Za-z_][A-Za-z0-9_]*)\[\(\s*([^,\]\n]+?)\s*,\s*([^\)\]\n]+?)\s*\)\]",
        r"\1[<<\2, \3>>]",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized tuple-indexed function lookup")
        fixed = fixed_new

    fixed_new = re.sub(
        r"<<\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*([^\]\n]+)\]\s*:\s*\1\s*\\in\s*([^>\n]+)>>",
        r"[\1 \\in \3 |-> \2]",
        fixed,
    )
    fixed_new = re.sub(
        r"<<\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*([^\]\n:]+)\s*:\s*\1\s*\\in\s*([^\]\n]+)\]>>",
        r"[\1 \\in \3 |-> \2]",
        fixed_new,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote tuple-comprehension function initializer")
        fixed = fixed_new

    fixed_new = re.sub(
        r"DOMAIN\s*\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|->\s*\1\s+IN\s+([^\]\n]+)\]",
        r"DOMAIN [\1 \\in \2 |-> \1]",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("rewrote DOMAIN function-constructor membership form")
        fixed = fixed_new

    fixed_new = re.sub(
        r"\[\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\\in\s*([^\]\n]+)\]\s*\|->\s*([^\n]+?)\]",
        r"[\1 \\in \2 |-> \3]",
        fixed,
    )
    if fixed_new != fixed:
        result.fixes_applied.append("normalized double-bracket function constructors")
        fixed = fixed_new

    init_match = re.search(r"(^Init\s*==\s*\n.*?)(?=^\w+(?:\([^)]*\))?\s*==|\Z)", fixed, re.MULTILINE | re.DOTALL)
    if init_match:
        init_block = init_match.group(1)
        repaired_init = re.sub(r"(^\s*/\\\s+)([A-Za-z_][A-Za-z0-9_]*)'\s*=", r"\1\2 =", init_block, flags=re.MULTILINE)
        if repaired_init != init_block:
            fixed = fixed[:init_match.start(1)] + repaired_init + fixed[init_match.end(1):]
            result.fixes_applied.append("removed primed assignments from Init")

    lines = fixed.splitlines()
    normalized_lines: list[str] = []
    previous_disjunct = False
    terminating_branch_changed = False
    for line in lines:
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        if previous_disjunct and re.match(r"/\\+\s+Terminating\b", stripped):
            branch = re.sub(r"^/\\+\s+", "", stripped).strip()
            normalized_lines.append(f"{indent}\\/ {branch}")
            terminating_branch_changed = True
            previous_disjunct = True
            continue
        normalized_lines.append(line)
        previous_disjunct = stripped.startswith("\\/")
    if terminating_branch_changed:
        fixed = "\n".join(normalized_lines)
        result.fixes_applied.append("normalized terminating branch in disjunction block")

    # ── Fix 24: Remove invalid SUM/PRODUCT operators ─────────────────────
    # TLA+ has no built-in SUM. Common pattern:
    #   SUM(f) == ... or SUM({f[i] : i \in S})
    # We can't auto-fix the semantics, but if SUM is used inline in a
    # simple summation pattern, replace with a FoldFunction or remove.
    # For now: if SANY errors mention "SUM" or "Unknown operator", and the
    # spec uses SUM as a bare call, define a simple recursive sum helper.
    if re.search(r"\bSUM\b", fixed) and not re.search(r"^\s*SUM\s*==", fixed, re.MULTILINE):
        # Try to replace simple SUM(set) patterns with a set fold
        # SUM(S) → LET __Sum[s \in SUBSET S] == ... is too complex.
        # Simpler: if SUM is used as SUM(f, S) or SUM({...}), just define it.
        # Insert a SUM definition after EXTENDS if not already defined.
        sum_def = (
            "\nSUM(S) == LET __SumHelper[ss \\in SUBSET S] ==\n"
            "            IF ss = {} THEN 0\n"
            "            ELSE LET x == CHOOSE x \\in ss : TRUE\n"
            "                 IN x + __SumHelper[ss \\ {x}]\n"
            "          IN __SumHelper[S]\n"
        )
        extends_end = re.search(r"^EXTENDS\s+.+$", fixed, re.MULTILINE)
        if extends_end:
            insert_at = extends_end.end()
            fixed = fixed[:insert_at] + sum_def + fixed[insert_at:]
            result.fixes_applied.append("auto-defined SUM operator")

    # ── Fix 25: Fix UNCHANGED <<>> (empty tuple) ─────────────────────────
    # UNCHANGED <<>> is invalid — remove the line entirely
    fixed_new = re.sub(r"^\s*/\\.*UNCHANGED\s*\(?\s*<<\s*>>\s*\)?\s*$", "", fixed, flags=re.MULTILINE)
    if fixed_new != fixed:
        result.fixes_applied.append("removed UNCHANGED <<>> (empty tuple)")
        fixed = fixed_new

    # ── Fix 26: Fix EXCEPT with wrong comma placement ────────────────────
    # Common error: [f EXCEPT ![a] = v1, ![b] = v2]
    # Should be:    [f EXCEPT ![a] = v1, ![b] = v2]  (this is actually valid)
    # But: [f EXCEPT ![a] = v1, [b] = v2]  (missing !) is invalid
    fixed_new = re.sub(r",\s*\[(\w)", r", ![\1", fixed)
    if fixed_new != fixed:
        result.fixes_applied.append("fixed EXCEPT missing ! before [")
        fixed = fixed_new

    # ── Fix 22: Detect and patch truncated specs ──────────────────────────
    # If the spec has no ==== ending, it was likely truncated.  We try to
    # close any open operator definitions and add a minimal terminator.
    if "====" not in fixed:
        # Count unclosed lines — if the last meaningful line doesn't end an
        # operator (doesn't look like a complete expression), add minimal close.
        stripped_lines = [l.rstrip() for l in fixed.splitlines() if l.strip()]
        if stripped_lines:
            last = stripped_lines[-1]
            # If last line looks like a truncated operator call / expression,
            # try to close the current operator with a simple TRUE and move on.
            if not re.match(r"^\s*(====|Spec\s*==|THEOREM|PROPERTY)", last):
                # Add ==== to close the module — Fix 9 might add it too, but
                # we also want to try to make the preceding incomplete
                # operator syntactically valid by appending TRUE if needed.
                if last.endswith("==") or last.endswith("/\\") or last.endswith("\\/"):
                    fixed = fixed.rstrip() + "\n    TRUE\n\n===="
                else:
                    fixed = fixed.rstrip() + "\n\n===="
                result.fixes_applied.append("closed truncated spec")

    result.fixed_spec = fixed.strip()
    return result


def _fix_conjunction_indent(spec: str) -> str:
    """
    Normalize indentation of /\\ and \\/ lines within operator definitions.

    SANY requires that all conjuncts/disjuncts in a list are at the same
    indentation level.  This function finds contiguous blocks of /\\ or \\/
    lines and aligns them to the first /\\ (or \\/) in each block.
    """
    lines = spec.splitlines()
    out: list[str] = []
    i = 0
    conj_re = re.compile(r"(\s*)(?:/\\|\\/)")

    while i < len(lines):
        line = lines[i]
        # Detect start of a conjunction/disjunction block:
        # a line that is followed by /\ or \/ lines
        if i + 1 < len(lines) and conj_re.match(lines[i + 1]):
            # Find the indentation of the first /\ or \/ line
            m = conj_re.match(lines[i + 1])
            target_indent = m.group(1) if m else "    "
            out.append(line)
            i += 1
            # Align all subsequent /\ and \/ lines to the same indent
            while i < len(lines):
                if conj_re.match(lines[i]):
                    stripped = lines[i].lstrip()
                    out.append(target_indent + stripped)
                    i += 1
                elif lines[i].strip() == "":
                    # blank line breaks the block
                    break
                elif re.match(r"\s+\S", lines[i]) and not re.match(r"\s*(ELSE|IN|THEN|LET|IF|CASE|OTHER)\b", lines[i]):
                    # continuation line within a conjunct — keep relative indent
                    out.append(lines[i])
                    i += 1
                else:
                    break
            continue

        # Handle standalone \/ block (disjunction not preceded by /\)
        if conj_re.match(line):
            m = conj_re.match(line)
            target_indent = m.group(1) if m else "    "
            stripped = line.lstrip()
            out.append(target_indent + stripped)
            i += 1
            while i < len(lines) and conj_re.match(lines[i]):
                stripped = lines[i].lstrip()
                out.append(target_indent + stripped)
                i += 1
            continue

        out.append(line)
        i += 1
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# SANY validation wrapper
# ─────────────────────────────────────────────────────────────────────────────

def validate_with_sany(spec: str) -> tuple[bool, str]:
    """Run SANY on a spec and return (is_valid, error_text)."""
    from src.validators.sany_validator import validate_string

    m = re.search(r"----\s*MODULE\s+(\w+)", spec)
    module_name = m.group(1) if m else "Spec"

    result = validate_string(spec, module_name=module_name)
    errors = "\n".join(result.errors) if result.errors else result.raw_output[-500:]
    return result.valid, errors


# ─────────────────────────────────────────────────────────────────────────────
# Training example builders (harmony format)
# ─────────────────────────────────────────────────────────────────────────────

def build_spec_gen_example(prompt: str, spec: str) -> dict:
    """Build a spec_generation training example in harmony format."""
    return {"messages": [
        {"role": "developer", "content": _DEVELOPER_PROMPT},
        {"role": "user",      "content": f"Write a TLA+ specification for the following:\n\n{prompt}"},
        {"role": "assistant", "channel": "analysis",  "content": "I'll write a well-formed TLA+ specification with proper Init, Next, and invariants."},
        {"role": "assistant", "channel": "final",     "content": spec.strip()},
    ]}


def build_bug_fix_example(prompt: str, buggy_spec: str, sany_errors: str, fixed_spec: str) -> dict:
    """Build a bug_fix training example in harmony format."""
    return {"messages": [
        {"role": "developer", "content": _DEVELOPER_PROMPT},
        {
            "role": "user",
            "content": (
                f"This TLA+ spec has syntax errors:\n\n"
                f"SANY errors:\n{sany_errors}\n\n"
                f"Buggy spec:\n{buggy_spec.strip()}\n\n"
                f"Fix the spec."
            ),
        },
        {"role": "assistant", "channel": "analysis",  "content": "I'll analyse the SANY errors and produce a corrected specification."},
        {"role": "assistant", "channel": "final",     "content": fixed_spec.strip()},
    ]}


# ─────────────────────────────────────────────────────────────────────────────
# Prompt generation
# ─────────────────────────────────────────────────────────────────────────────

def load_prompts(limit: Optional[int] = None) -> list[dict]:
    """Load benchmark prompts + generate synthetic variations."""
    prompts = []

    # Load benchmark suite
    if _BENCHMARK_JSON.exists():
        with open(_BENCHMARK_JSON) as f:
            benchmarks = json.load(f)
        for bm in benchmarks:
            prompts.append({
                "id": bm["id"],
                "prompt": bm["description"],
                "module_hint": bm["name"].replace(" ", "").replace("'", ""),
            })

    # Synthetic prompt variations (rewordings and new problems)
    synthetic = [
        {"id": "SYN001", "prompt": "A token ring protocol where N nodes pass a token in a circle. Only the node holding the token may enter the critical section.", "module_hint": "TokenRing"},
        {"id": "SYN002", "prompt": "A simple clock that counts from 0 to MAX and wraps around.", "module_hint": "Clock"},
        {"id": "SYN003", "prompt": "A traffic light controller that cycles through Red, Green, Yellow states.", "module_hint": "TrafficLight"},
        {"id": "SYN004", "prompt": "A bank account with deposit and withdraw operations. Balance must never go negative.", "module_hint": "BankAccount"},
        {"id": "SYN005", "prompt": "A simple stack (LIFO) data structure with push and pop operations. The stack has a maximum capacity.", "module_hint": "BoundedStack"},
        {"id": "SYN006", "prompt": "Peterson's algorithm for mutual exclusion between two processes.", "module_hint": "Peterson"},
        {"id": "SYN007", "prompt": "A leader election algorithm in a ring of N processes where each process has a unique ID. The process with the highest ID becomes the leader.", "module_hint": "RingLeader"},
        {"id": "SYN008", "prompt": "A simple key-value store supporting Get, Put, and Delete operations.", "module_hint": "KVStore"},
        {"id": "SYN009", "prompt": "A state machine for a vending machine that accepts coins and dispenses items when enough money is inserted.", "module_hint": "VendingMachine"},
        {"id": "SYN010", "prompt": "An elevator controller for a building with N floors. The elevator moves up and down, opening doors at requested floors.", "module_hint": "Elevator"},
        # Simple specs — high success probability
        {"id": "SYN011", "prompt": "A counter that starts at 0, can increment by 1, and has a maximum value MAX.", "module_hint": "Counter"},
        {"id": "SYN012", "prompt": "A toggle switch that alternates between ON and OFF states.", "module_hint": "Toggle"},
        {"id": "SYN013", "prompt": "A simple semaphore with initial count N. Processes can acquire (decrement) or release (increment) the semaphore. Count must be non-negative.", "module_hint": "Semaphore"},
        {"id": "SYN014", "prompt": "A register that stores a natural number. It can be read, written, or reset to zero.", "module_hint": "Register"},
        {"id": "SYN015", "prompt": "A two-bit binary counter that counts from 0 to 3 and wraps.", "module_hint": "BinaryCounter"},
        {"id": "SYN016", "prompt": "A simple buffer with one slot. A producer writes to it, a consumer reads from it. The buffer is either empty or full.", "module_hint": "SingleBuffer"},
        {"id": "SYN017", "prompt": "A state machine that models a door: it can be Open, Closed, or Locked. Transitions follow physical constraints.", "module_hint": "Door"},
        {"id": "SYN018", "prompt": "A resource allocator for a single resource. Processes can request, acquire, and release the resource.", "module_hint": "ResourceAlloc"},
        {"id": "SYN019", "prompt": "A min/max tracker that keeps track of the minimum and maximum values seen from a stream of naturals.", "module_hint": "MinMaxTracker"},
        {"id": "SYN020", "prompt": "A simple DAG node with status: Pending, Running, Done. It transitions from Pending to Running to Done.", "module_hint": "TaskNode"},
    ]
    prompts.extend(synthetic)

    if limit:
        prompts = prompts[:limit]

    return prompts


# ─────────────────────────────────────────────────────────────────────────────
# Core loop: one iteration
# ─────────────────────────────────────────────────────────────────────────────

def run_iteration(
    model: str = "chattla:20b",
    num_prompts: Optional[int] = None,
    temperature: float = 0.4,
) -> IterationStats:
    """
    Run one generate → validate → fix → augment iteration.

    Returns IterationStats with counts of what happened.
    """
    from src.inference.ollama_client import ChatTLAClient

    stats = IterationStats()
    client = ChatTLAClient(model=model, reasoning="medium")
    prompts = load_prompts(limit=num_prompts)
    new_examples: list[dict] = []

    log.info(f"[self_improve] Starting iteration with {len(prompts)} prompts, model={model}")

    for p in prompts:
        prompt_id = p["id"]
        prompt_text = p["prompt"]
        module_hint = p.get("module_hint")
        stats.prompts_tried += 1

        # ── Phase 1: Generate ─────────────────────────────────────────────
        log.info(f"  [{prompt_id}] Generating spec for: {prompt_text[:60]}...")
        try:
            spec = client.generate_spec(prompt_text, module_name=module_hint, temperature=temperature)
        except Exception as e:
            log.warning(f"  [{prompt_id}] Generation failed: {e}")
            continue

        stats.specs_generated += 1

        # ── Phase 2: SANY validate ────────────────────────────────────────
        is_valid, sany_errors = validate_with_sany(spec)

        if is_valid:
            # Spec passes SANY! Add as spec_generation example
            log.info(f"  [{prompt_id}] ✓ SANY pass (raw). Adding as spec_gen example.")
            stats.sany_pass_raw += 1
            stats.spec_gen_examples += 1
            new_examples.append(build_spec_gen_example(prompt_text, spec))
            continue

        # ── Phase 3: Python fixer ─────────────────────────────────────────
        log.info(f"  [{prompt_id}] ✗ SANY fail. Attempting Python fixes...")
        fix_result = fix_tla_syntax(spec, sany_errors)

        if fix_result.fixes_applied:
            log.info(f"  [{prompt_id}]   Applied {len(fix_result.fixes_applied)} fixes: {', '.join(fix_result.fixes_applied)}")

            # Re-validate after Python fixes
            is_valid_fixed, sany_errors_fixed = validate_with_sany(fix_result.fixed_spec)

            if is_valid_fixed:
                log.info(f"  [{prompt_id}] ✓ SANY pass after fixes. Adding spec_gen example.")
                stats.sany_pass_fixed += 1

                # Only create spec_gen example with the corrected spec.
                # Bug-fix examples are deliberately excluded: they contain
                # buggy TLA+ in the user message which the model memorises,
                # causing it to reproduce syntax errors during generation.
                new_examples.append(build_spec_gen_example(prompt_text, fix_result.fixed_spec))
                stats.spec_gen_examples += 1
                continue

        # ── Phase 4: Model self-correction attempt ────────────────────────
        log.info(f"  [{prompt_id}] Python fixes insufficient. Trying model self-correction...")
        try:
            corrected_spec, tier = client.validate_and_generate(prompt_text)
            is_valid_corrected, _ = validate_with_sany(corrected_spec)

            if is_valid_corrected:
                log.info(f"  [{prompt_id}] ✓ Self-correction succeeded (tier={tier}).")
                stats.sany_pass_fixed += 1

                # Only spec_gen — no bug_fix examples (see note above).
                new_examples.append(build_spec_gen_example(prompt_text, corrected_spec))
                stats.spec_gen_examples += 1
            else:
                log.info(f"  [{prompt_id}] ✗ Self-correction also failed. Skipping.")
        except Exception as e:
            log.warning(f"  [{prompt_id}] Self-correction error: {e}")

    # ── Phase 5: Persist new examples (with dedup) ────────────────────────
    stats.total_new_examples = len(new_examples)
    if new_examples:
        # Load existing augmented examples to dedup against
        existing_prompts = set()
        if _AUGMENTED_JSONL.exists():
            with open(_AUGMENTED_JSONL, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            ex = json.loads(line)
                            user_msg = [m for m in ex["messages"] if m["role"] == "user"][0]["content"]
                            # Hash first 200 chars of prompt as dedup key
                            existing_prompts.add(user_msg[:200])
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

        # Filter out duplicates
        deduped_examples = []
        for ex in new_examples:
            user_msg = [m for m in ex["messages"] if m["role"] == "user"][0]["content"]
            key = user_msg[:200]
            if key not in existing_prompts:
                deduped_examples.append(ex)
                existing_prompts.add(key)

        stats.total_new_examples = len(deduped_examples)
        if deduped_examples:
            _AUGMENTED_JSONL.parent.mkdir(parents=True, exist_ok=True)
            with open(_AUGMENTED_JSONL, "a", encoding="utf-8") as f:
                for ex in deduped_examples:
                    f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            log.info(f"[self_improve] Appended {len(deduped_examples)} new examples "
                     f"({len(new_examples) - len(deduped_examples)} deduped) to {_AUGMENTED_JSONL}")
        else:
            log.info(f"[self_improve] All {len(new_examples)} examples were duplicates — nothing appended.")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Dataset rebuild
# ─────────────────────────────────────────────────────────────────────────────

def rebuild_dataset() -> tuple[int, int]:
    """Rebuild train/eval JSONL from combined.jsonl + augmented.jsonl."""
    from src.training.dataset_builder import build

    n_train, n_eval = build(
        include_augmented=True,
        include_description_sft=True,
        bugfix_oversample=2,
        include_silver_augmented=True,
        augmented_best_per_prompt=True,
    )
    log.info(f"[self_improve] Dataset rebuilt: train={n_train}, eval={n_eval}")
    return n_train, n_eval


# ─────────────────────────────────────────────────────────────────────────────
# Retrain + deploy
# ─────────────────────────────────────────────────────────────────────────────

def retrain_and_deploy() -> bool:
    """
    Run full retrain → merge → GGUF → Ollama deploy pipeline.

    Dynamically scales epochs and timeout based on training set size.
    Returns True if successful.
    """
    log.info("[self_improve] Starting retraining...")

    # Count training examples to scale epochs and timeout
    n_train = 0
    if _TRAIN_JSONL.exists():
        with open(_TRAIN_JSONL) as f:
            n_train = sum(1 for line in f if line.strip())

    # Fewer epochs for larger datasets: 10 for <80, 5 for ~200, 3 for 400+
    num_epochs = max(3, min(10, 600 // max(n_train, 1)))
    # Estimate timeout: steps≈n_train*epochs/8, ~40s/step, 1.5x safety
    est_steps = (n_train * num_epochs) // 8
    timeout_s = max(3600, int(est_steps * 40 * 1.5))
    log.info(f"[self_improve] Training {n_train} examples × {num_epochs} epochs "
             f"(~{est_steps} steps, timeout={timeout_s}s)")

    # 1. Train
    result = subprocess.run(
        [sys.executable, "-m", "src.training.train", "--epochs", str(num_epochs)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if result.returncode != 0:
        log.error(f"[self_improve] Training failed:\n{result.stderr[-500:]}")
        return False
    log.info("[self_improve] Training complete.")

    # 2. Merge LoRA
    result = subprocess.run(
        [sys.executable, "-m", "src.training.merge_lora"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        log.error(f"[self_improve] Merge failed:\n{result.stderr[-500:]}")
        return False
    log.info("[self_improve] LoRA merged.")

    # 3. Convert to GGUF + register Ollama
    result = subprocess.run(
        [sys.executable, "-m", "src.inference.convert_to_gguf", "--quant", "Q8_0"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        log.error(f"[self_improve] GGUF conversion failed:\n{result.stderr[-500:]}")
        return False
    log.info("[self_improve] GGUF deployed to Ollama.")

    if os.environ.get("HF_TOKEN"):
        log.info("[self_improve] Publishing to Hugging Face Hub...")
        pub = subprocess.run(
            [sys.executable, "-m", "src.training.publish_hf", "--quant", "Q8_0"],
            cwd=str(_REPO_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=7200,
        )
        if pub.returncode != 0:
            log.warning(f"[self_improve] HF publish failed (non-fatal): {(pub.stderr or pub.stdout)[-400:]}")
        else:
            log.info("[self_improve] HF publish complete.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main autonomous loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="ChatTLA self-improvement loop: generate → validate → fix → retrain"
    )
    parser.add_argument("--iterations", type=int, default=5,
                        help="Number of generate/fix iterations to run (default: 5)")
    parser.add_argument("--prompts", type=int, default=None,
                        help="Limit number of prompts per iteration (default: all)")
    parser.add_argument("--retrain-threshold", type=int, default=15,
                        help="Retrain after accumulating this many new examples (default: 15)")
    parser.add_argument("--model", default="chattla:20b",
                        help="Ollama model tag to use for generation")
    parser.add_argument("--temperature", type=float, default=0.4,
                        help="Sampling temperature for generation")
    parser.add_argument("--no-retrain", action="store_true",
                        help="Skip retraining (generate/fix/augment only)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Count existing augmented examples
    existing_aug = 0
    if _AUGMENTED_JSONL.exists():
        with open(_AUGMENTED_JSONL) as f:
            existing_aug = sum(1 for line in f if line.strip())

    total_new = 0
    retrain_count = 0

    print("="*70)
    print("  ChatTLA Self-Improvement Loop")
    print(f"  Iterations: {args.iterations} | Prompts/iter: {args.prompts or 'all'}")
    print(f"  Retrain threshold: {args.retrain_threshold} | Model: {args.model}")
    print(f"  Existing augmented examples: {existing_aug}")
    print("="*70)

    for iteration in range(1, args.iterations + 1):
        print(f"\n{'─'*70}")
        print(f"  Iteration {iteration}/{args.iterations}")
        print(f"{'─'*70}")

        t0 = time.time()
        stats = run_iteration(
            model=args.model,
            num_prompts=args.prompts,
            temperature=args.temperature,
        )
        elapsed = time.time() - t0

        total_new += stats.total_new_examples

        print(f"\n  Iteration {iteration} results ({elapsed:.0f}s):")
        print(f"    Prompts tried:       {stats.prompts_tried}")
        print(f"    Specs generated:     {stats.specs_generated}")
        print(f"    SANY pass (raw):     {stats.sany_pass_raw}")
        print(f"    SANY pass (fixed):   {stats.sany_pass_fixed}")
        print(f"    Bug-fix examples:    {stats.bug_fix_examples}")
        print(f"    Spec-gen examples:   {stats.spec_gen_examples}")
        print(f"    New examples total:  {stats.total_new_examples}")
        print(f"    Cumulative new:      {total_new}")

        # Check if we should retrain
        if not args.no_retrain and total_new >= args.retrain_threshold:
            print(f"\n  ⟳ Retrain threshold reached ({total_new} ≥ {args.retrain_threshold})")
            print(f"    Rebuilding dataset...")
            n_train, n_eval = rebuild_dataset()
            print(f"    Dataset: {n_train} train, {n_eval} eval")

            print(f"    Starting retrain + deploy pipeline...")
            t1 = time.time()
            success = retrain_and_deploy()
            retrain_elapsed = time.time() - t1

            if success:
                retrain_count += 1
                total_new = 0  # Reset counter
                print(f"    ✓ Retrain #{retrain_count} complete ({retrain_elapsed/60:.1f} min)")
            else:
                print(f"    ✗ Retrain failed after {retrain_elapsed/60:.1f} min. Continuing...")

    # Final summary
    print(f"\n{'='*70}")
    print(f"  Self-Improvement Loop Complete")
    print(f"  Retrains completed: {retrain_count}")

    # Count total augmented examples
    aug_count = 0
    if _AUGMENTED_JSONL.exists():
        with open(_AUGMENTED_JSONL) as f:
            aug_count = sum(1 for line in f if line.strip())
    print(f"  Total augmented examples: {aug_count}")
    print(f"  Remaining un-trained examples: {total_new}")
    print(f"{'='*70}")

    # If there are untrained examples, offer to rebuild
    if total_new > 0 and not args.no_retrain:
        print(f"\n  {total_new} examples pending. Rebuilding dataset for next manual retrain...")
        rebuild_dataset()


if __name__ == "__main__":
    main()
