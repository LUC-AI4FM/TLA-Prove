"""A small curated library of standard TLAPS facts/lemmas/backends plus a
deterministic retriever that suggests which ``BY`` facts to try.

Given an obligation's text or a TLAPS error message, :func:`suggest_facts`
ranks the curated catalog by case-insensitive keyword overlap — no LLM, no
external tools, pure substring matching. The intent is to turn a raw failure
(e.g. ``could not prove ENABLED <<DetectTermination>>_vars``) into a short,
ordered shortlist of facts/backends to splice into a ``BY`` clause.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    """A standard-library fact, lemma, or backend usable in a ``BY`` clause.

    ``module`` is the TLAPS module to ``EXTENDS``/reference (e.g.
    ``FiniteSetTheorems``); for backends it is ``TLAPS``. ``keywords`` are the
    case-insensitive substrings that should attract this fact during retrieval.
    """

    name: str
    module: str
    keywords: tuple[str, ...]
    note: str = ""


# The curated catalog. Order is significant: it is the tie-breaker for equal
# scores in :func:`suggest_facts`, so the more generally-useful facts come
# first within each topical cluster.
FACTS: list[Fact] = [
    # --- Finite set cardinality (FiniteSetTheorems) ---------------------------
    Fact(
        name="FS_EmptySet",
        module="FiniteSetTheorems",
        keywords=("cardinality", "finite", "isfiniteset", "set size", "finitesets", "empty set"),
        note="Cardinality({}) = 0 and {} is a finite set.",
    ),
    Fact(
        name="FS_Singleton",
        module="FiniteSetTheorems",
        keywords=("cardinality", "finite", "isfiniteset", "set size", "finitesets", "singleton"),
        note="Cardinality({x}) = 1; a singleton is finite.",
    ),
    Fact(
        name="FS_AddElement",
        module="FiniteSetTheorems",
        keywords=("cardinality", "finite", "isfiniteset", "set size", "finitesets", "union", "add element"),
        note="Cardinality of S \\cup {x} in terms of Cardinality(S).",
    ),
    Fact(
        name="FS_Subset",
        module="FiniteSetTheorems",
        keywords=("cardinality", "finite", "isfiniteset", "set size", "finitesets", "subset"),
        note="A subset of a finite set is finite with no greater cardinality.",
    ),
    Fact(
        name="FS_CardinalityType",
        module="FiniteSetTheorems",
        keywords=("cardinality", "finite", "isfiniteset", "set size", "finitesets", "nat", "type"),
        note="Cardinality(S) \\in Nat for a finite set S.",
    ),
    # --- ENABLED / action enabledness (TLAPS) --------------------------------
    Fact(
        name="ENABLEDrules",
        module="TLAPS",
        keywords=("enabled", "action enabled", "enabledness"),
        note="Proof rules for reasoning about ENABLED A.",
    ),
    Fact(
        name="ExpandENABLED",
        module="TLAPS",
        keywords=("enabled", "action enabled", "enabledness", "expand"),
        note="Expand ENABLED into its existential over primed variables.",
    ),
    # --- Temporal logic (TLAPS) ----------------------------------------------
    Fact(
        name="PTL",
        module="TLAPS",
        keywords=(
            "temporal",
            "box",
            "diamond",
            "[]",
            "<>",
            "liveness",
            "fairness",
            "leads-to",
            "qed temporal",
        ),
        note="Propositional temporal logic backend (LS4) for [] / <> reasoning.",
    ),
    # --- Backends (TLAPS) ----------------------------------------------------
    Fact(
        name="Zenon",
        module="TLAPS",
        keywords=("first-order", "set theory", "default", "tableau"),
        note="Zenon first-order tableau backend.",
    ),
    Fact(
        name="SMT",
        module="TLAPS",
        keywords=("arithmetic", "first-order", "set theory", "default", "linear"),
        note="SMT backend; strong on arithmetic and quantifier-free goals.",
    ),
    Fact(
        name="Isa",
        module="TLAPS",
        keywords=("first-order", "set theory", "default", "isabelle"),
        note="Isabelle backend; robust default for set theory.",
    ),
    # --- Natural-number induction (NaturalsInduction) ------------------------
    Fact(
        name="NatInductionThm",
        module="NaturalsInduction",
        keywords=("induction", "nat", "natural number", "recursive", "measure"),
        note="Induction principle over Nat (P(0) and step => forall).",
    ),
    Fact(
        name="GeneralNatInduction",
        module="NaturalsInduction",
        keywords=("induction", "nat", "natural number", "recursive", "measure", "strong"),
        note="Strong (course-of-values) induction over Nat.",
    ),
]


def suggest_facts(obligation_or_error: str, k: int = 5) -> list[Fact]:
    """Suggest up to ``k`` facts ranked by keyword overlap with the input.

    Both the input and every catalog keyword are lowercased; the score is the
    number of a fact's keywords that appear as substrings in the input, plus a
    small bonus when the fact's own name appears verbatim. Facts with a zero
    score are dropped. Ties are broken by catalog order (stable sort).
    """
    if k <= 0:
        return []

    text = obligation_or_error.lower()

    scored: list[tuple[int, int, Fact]] = []
    for index, fact in enumerate(FACTS):
        score = sum(1 for kw in fact.keywords if kw.lower() in text)
        if fact.name.lower() in text:
            score += 1
        if score > 0:
            scored.append((score, index, fact))

    # Highest score first; ties resolved by ascending catalog index.
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [fact for _, _, fact in scored[:k]]
