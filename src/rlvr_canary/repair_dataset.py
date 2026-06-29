"""Repair prompt dataset for GRPO training.

Loads flattened repair pairs from ralph_repair_pairs.jsonl and formats
them as GRPO-ready prompts. Each prompt contains:
  - Original NL description
  - The broken spec
  - Line-annotated verifier diagnostics
  - Instructions to fix

The model generates a repaired spec; the repair_reward function scores
it based on improvement over the broken input.

Difficulty buckets (by before_score):
  easy:   < 0.10   (SANY failures — most fixable)
  medium: 0.10–0.40 (structural issues — missing components)
  hard:   >= 0.40   (semantic/TLC failures)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPAIR_PAIRS = "data/processed/ralph_repair_pairs.jsonl"
DEFAULT_BENCHMARK_REPAIR_PAIRS = "data/processed/benchmark_repair_pairs_fc128best.jsonl"

_REPAIR_DEVELOPER = """\
You are ChatTLA, an expert at repairing TLA+ specifications.
Fix every verifier diagnostic below. Keep the same module name.
Output only the corrected TLA+ module (---- MODULE ... ====).

TLC runtime rules (your repaired spec MUST pass the TLC model checker):
1. CONSTANTS must be finite and enumerable. Never use \\in Nat or \\in Int unbounded.
2. Every disjunct in Next must specify ALL variables: either prime them or use UNCHANGED.
3. Init must assign every variable a concrete finite value.
4. TypeOK must constrain every variable to a finite set.
Reasoning: none\
"""


@dataclass
class RepairExample:
    repair_id: str
    nl: str
    broken_spec: str
    errors_rendered: str
    verify_summary: str
    before_score: float
    source_file: str


def resolve_repair_pair_paths(
    trajectory_file: str | Path | Sequence[str | Path] = DEFAULT_REPAIR_PAIRS,
) -> list[Path]:
    """Resolve one or more repair-pair JSONL paths against the repo root."""
    raw_items: list[str | Path]
    if isinstance(trajectory_file, (str, Path)):
        raw_items = [trajectory_file]
    else:
        raw_items = list(trajectory_file)

    if not raw_items:
        raise ValueError("At least one repair-pair path is required")

    paths: list[Path] = []
    for item in raw_items:
        path = Path(item)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        paths.append(path)
    return paths


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def load_repair_prompts(
    trajectory_file: str | Path | Sequence[str | Path] = DEFAULT_REPAIR_PAIRS,
    difficulty: str = "all",
    max_examples: int | None = None,
    min_before_score: float = 0.02,
    max_before_score: float = 0.80,
    max_prompt_tokens: int | None = None,
    tokenizer=None,
) -> tuple[list[RepairExample], dict[str, float]]:
    """Load repair examples and their before_scores.

    Parameters
    ----------
    trajectory_file : path or paths to repair-pair JSONL files
    difficulty : "easy" | "medium" | "hard" | "all"
    max_examples : cap for smoke tests
    min_before_score : drop unparseable / hopeless pairs (default 0.02 keeps
        anything that at least produced a non-zero component score)
    max_before_score : drop already-good pairs that leave no headroom
    max_prompt_tokens : if set with `tokenizer`, drop pairs whose formatted
        prompt exceeds this many tokens (avoids OOM on huge attention matrices)
    tokenizer : required when max_prompt_tokens is set

    Returns
    -------
    examples : list of RepairExample
    before_scores : {repair_id: float} for repair_reward registration
    """
    paths = resolve_repair_pair_paths(trajectory_file)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_rendered = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Repair pairs not found: {missing_rendered}")

    examples: list[RepairExample] = []
    before_scores: dict[str, float] = {}
    n_score_drop = 0
    n_len_drop = 0
    n_diff_drop = 0
    seen_repair_ids: set[str] = set()

    for path in paths:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                repair_id = row["repair_id"]
                if repair_id in seen_repair_ids:
                    continue
                score = row["before_score"]

                # Filter by difficulty
                if difficulty == "easy" and score >= 0.10:
                    n_diff_drop += 1
                    continue
                if difficulty == "medium" and (score < 0.10 or score >= 0.40):
                    n_diff_drop += 1
                    continue
                if difficulty == "hard" and score < 0.40:
                    n_diff_drop += 1
                    continue

                # Filter by gradable range — both sides need headroom
                if score < min_before_score or score > max_before_score:
                    n_score_drop += 1
                    continue

                ex = RepairExample(
                    repair_id=repair_id,
                    nl=row["nl"],
                    broken_spec=row["broken_spec"],
                    errors_rendered=row["errors_rendered"],
                    verify_summary=row["verify_summary"],
                    before_score=score,
                    source_file=_display_path(path),
                )

                # Length filter (requires tokenizer)
                if max_prompt_tokens is not None and tokenizer is not None:
                    prompt = format_repair_prompt(ex, tokenizer)
                    if len(tokenizer.encode(prompt)) > max_prompt_tokens:
                        n_len_drop += 1
                        continue

                examples.append(ex)
                before_scores[ex.repair_id] = score
                seen_repair_ids.add(repair_id)

                if max_examples and len(examples) >= max_examples:
                    break
        if max_examples and len(examples) >= max_examples:
            break

    print(f"[repair_dataset] kept {len(examples)} | dropped: "
          f"score={n_score_drop} len={n_len_drop} difficulty={n_diff_drop}")

    # Sort by before_score ascending (easy first) for curriculum
    examples.sort(key=lambda x: x.before_score)

    return examples, before_scores


def format_repair_prompt(ex: RepairExample, tokenizer) -> str:
    """Build a GRPO-ready repair prompt string.

    Mirrors train_rl_fullspec.py lines 154-166: pre-format as a string
    ending with <|channel|>final<|message|> so the model writes directly
    into the spec channel.

    The repair_id is embedded as <!-- repair:ID --> at the start so the
    reward function can look up the before_score.
    """
    user_content = (
        f"Original request:\n{ex.nl}\n\n"
        f"Previous spec failed verification. Tier summary: {ex.verify_summary}.\n\n"
        f"=== Previous spec ===\n{ex.broken_spec}\n=== End spec ===\n\n"
        f"=== Diagnostics ===\n{ex.errors_rendered}\n=== End diagnostics ===\n\n"
        f"Fix every diagnostic. Emit ONLY the corrected TLA+ module "
        f"(starting with ---- MODULE)."
    )
    messages = [
        {"role": "developer", "content": _REPAIR_DEVELOPER},
        {"role": "user", "content": user_content},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    # Embed repair_id for reward lookup + force final channel
    return f"<!-- repair:{ex.repair_id} -->{text}<|channel|>final<|message|>"
