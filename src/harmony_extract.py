"""Channel-aware extraction of the TLAPS proof from a harmony generation.

Replaces the fragile ``text.index("final")`` heuristic that split on the
literal word "final" (which appears in analysis prose like "the *final*
theorem"), leaking reasoning into the proof and causing SANY ``parse_error``.

Preferred input: the assistant continuation decoded with
``skip_special_tokens=False`` so the harmony channel delimiters
(``<|channel|>``, ``<|message|>``, ``<|end|>``/``<|return|>``) are present.
A degraded fallback handles legacy ``skip_special_tokens=True`` text by keying
on the TLAPS proof anchor ``^<n>`` rather than the word "final".
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ProofExtraction:
    proof: str
    status: str  # "ok" | "no_final"


_HAS_MARKERS_RE = re.compile(r"<\|channel\|>")
_CHANNEL_RE = re.compile(
    r"<\|channel\|>\s*(?P<name>\w+)[^<]*?<\|message\|>(?P<content>.*?)"
    r"(?=<\|(?:end|return|call|start)\|>|$)",
    re.DOTALL,
)
# The channel word "final" glued directly to the first proof bullet, e.g.
# "...final<1>a..." — the shape skip_special_tokens=True produces.
_FINAL_GLUED_RE = re.compile(r"final\s*(<\d+>)")
# TLAPS hierarchical step bullet at the start of a line: <1>, <2>1., <1>a ...
_PROOF_ANCHOR_RE = re.compile(r"(?m)^[ \t]*<\d+>")


def extract_final_channel(raw: str) -> ProofExtraction:
    """Return the ``final`` channel content (the proof) and a status.

    ``status="no_final"`` means the model never emitted a usable ``final``
    channel (typically truncated mid-``analysis``) — callers should treat this
    as a distinct failure category, NOT feed the analysis prose to SANY.
    """
    if _HAS_MARKERS_RE.search(raw):
        final_content: str | None = None
        for m in _CHANNEL_RE.finditer(raw):
            if m.group("name") == "final":
                final_content = m.group("content")  # keep the last final channel
        if final_content is not None and final_content.strip():
            return ProofExtraction(proof=final_content.strip(), status="ok")
        return ProofExtraction(proof="", status="no_final")

    # Degraded form (legacy skip_special_tokens=True): channel markers are gone.
    # Anchor on the proof structure, never on the bare word "final".
    glued = _FINAL_GLUED_RE.search(raw)
    if glued:
        return ProofExtraction(proof=raw[glued.start(1):].strip(), status="ok")
    anchor = _PROOF_ANCHOR_RE.search(raw)
    if anchor:
        return ProofExtraction(proof=raw[anchor.start():].strip(), status="ok")
    return ProofExtraction(proof="", status="no_final")
