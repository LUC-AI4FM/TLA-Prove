"""Production invariant proposer for the CEGIS loop.

Turns a counterexample-to-induction (CTI) into a single strengthening TLA+
predicate by asking the teacher model. The network call is injected as
``chat_fn`` so the deterministic parts (prompt construction, response parsing)
are unit-testable offline; ``default_cloud_chat_fn`` wires the Ollama Cloud
teacher (qwen3-coder:480b) used elsewhere in the repo.
"""
from __future__ import annotations

import os
import re
from typing import Callable, Optional

ChatFn = Callable[[str], str]

_PROMPT = """\
You are strengthening a TLA+ inductive invariant.

Module:
{module}

Candidate invariant (it is NOT inductive — TLC found a counterexample-to-induction):
    {candidate}

Counterexample-to-induction (a state satisfying the candidate that steps to one that does not):
    {cti}

Output a SINGLE additional TLA+ state predicate to conjoin with the candidate so
that this counterexample is excluded. It must reference only the module's
variables. Output ONLY the predicate expression — no name, no `==`, no prose,
no markdown.
"""

_REFUSALS = ("i cannot", "i can't", "unable to", "cannot determine", "no valid")
# A usable predicate contains at least one relational/logical operator.
_PREDICATE_OP = re.compile(r"[=<>#]|\\in|\\notin|\\subseteq|/\\|\\/|=>|~|\bENABLED\b")


def build_strengthen_prompt(module_src: str, candidate: str, cti: str) -> str:
    return _PROMPT.format(module=module_src, candidate=candidate, cti=cti)


def parse_invariant(text: Optional[str]) -> Optional[str]:
    """Extract a single TLA+ predicate from a teacher response, or None."""
    if not text:
        return None
    t = text.strip()
    fence = re.search(r"```(?:tla)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    if any(r in t.lower() for r in _REFUSALS):
        return None
    line = next((ln.strip() for ln in t.splitlines() if ln.strip()), "")
    if not line:
        return None
    if "==" in line:  # strip a definition LHS like "Inv2 == ..."
        line = line.split("==", 1)[1].strip()
    if not _PREDICATE_OP.search(line):
        return None
    return line


def make_invariant_proposer(chat_fn: ChatFn) -> Callable[[str, str, str], Optional[str]]:
    """Build a CEGIS-compatible proposer from a chat function."""

    def propose(module_src: str, candidate: str, cti: str) -> Optional[str]:
        prompt = build_strengthen_prompt(module_src, candidate, cti)
        try:
            response = chat_fn(prompt)
        except Exception:
            return None
        return parse_invariant(response)

    return propose


def default_cloud_chat_fn(model: Optional[str] = None) -> ChatFn:
    """Ollama Cloud teacher chat fn (qwen3-coder:480b by default).

    Requires OLLAMA_API_KEY in the environment (the cloud-only launch convention
    used by long-Ralph). NOT exercised by the offline test suite — verify live
    before relying on it.
    """
    model = model or os.getenv("OLLAMA_CLOUD_MODEL", "qwen3-coder:480b")

    def chat_fn(prompt: str) -> str:
        import ollama  # deferred import; only needed for live calls

        client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
            headers={"Authorization": f"Bearer {os.environ['OLLAMA_API_KEY']}"},
        )
        resp = client.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return resp["message"]["content"]

    return chat_fn
