import json
from pathlib import Path

from src.rlvr_canary.repair_dataset import (
    format_repair_prompt,
    load_repair_prompts,
    resolve_repair_pair_paths,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


class _FakeTokenizer:
    eos_token = "</s>"
    eos_token_id = 0
    pad_token = None
    padding_side = "left"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        rendered = "\n".join(f"{item['role']}: {item['content']}" for item in messages)
        if add_generation_prompt:
            rendered += "\nassistant:"
        return rendered

    def encode(self, text: str) -> list[int]:
        return list(range(len(text.split())))


class _TemplateLessTokenizer(_FakeTokenizer):
    chat_template = None

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        raise ValueError(
            "Cannot use chat template functions because tokenizer.chat_template is not set "
            "and no template argument was passed!"
        )


def _row(repair_id: str, *, before_score: float, suffix: str) -> dict:
    return {
        "repair_id": repair_id,
        "nl": f"Write a TLA+ spec for {suffix}",
        "broken_spec": f"---- MODULE Broken{suffix} ----\nVARIABLE x\n====",
        "errors_rendered": f"missing Init in {suffix}",
        "verify_summary": f"struct={before_score:.2f}",
        "before_score": before_score,
    }


def test_resolve_repair_pair_paths_supports_multiple_inputs(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    paths = resolve_repair_pair_paths([first, second])
    assert paths == [first, second]


def test_load_repair_prompts_merges_multiple_files_and_dedupes(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(
        first,
        [
            _row("shared", before_score=0.15, suffix="alpha"),
            _row("first-only", before_score=0.45, suffix="beta"),
        ],
    )
    _write_jsonl(
        second,
        [
            _row("shared", before_score=0.15, suffix="alpha-duplicate"),
            _row("second-only", before_score=0.05, suffix="gamma"),
        ],
    )

    examples, before_scores = load_repair_prompts(
        trajectory_file=[first, second],
        difficulty="all",
        min_before_score=0.02,
        max_before_score=0.80,
    )

    assert [example.repair_id for example in examples] == ["second-only", "shared", "first-only"]
    assert before_scores == {
        "shared": 0.15,
        "first-only": 0.45,
        "second-only": 0.05,
    }
    assert examples[0].source_file.endswith("second.jsonl")
    assert examples[1].source_file.endswith("first.jsonl")


def test_load_repair_prompts_applies_length_filter_across_sources(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_jsonl(first, [_row("short", before_score=0.12, suffix="short")])
    _write_jsonl(
        second,
        [
            {
                **_row("long", before_score=0.14, suffix="long"),
                "errors_rendered": " ".join(["diagnostic"] * 200),
            }
        ],
    )

    tokenizer = _FakeTokenizer()
    examples, _ = load_repair_prompts(
        trajectory_file=[first, second],
        max_prompt_tokens=200,
        tokenizer=tokenizer,
    )

    assert [example.repair_id for example in examples] == ["short"]
    prompt = format_repair_prompt(examples[0], tokenizer)
    assert "<!-- repair:short -->" in prompt


def test_load_repair_prompts_preserves_repair_metadata(tmp_path: Path) -> None:
    source = tmp_path / "validated.jsonl"
    _write_jsonl(
        source,
        [
            {
                **_row("proof-1", before_score=0.45, suffix="proof"),
                "repair_bucket": "proof_repair",
                "module": "AtomicRegister",
                "validated_tier": "gold",
                "gold_source_kind": "diamond_eval_holdout",
            }
        ],
    )

    examples, before_scores = load_repair_prompts(
        trajectory_file=[source],
        difficulty="all",
        min_before_score=0.02,
        max_before_score=0.80,
    )

    assert before_scores == {"proof-1": 0.45}
    assert examples[0].repair_bucket == "proof_repair"
    assert examples[0].module == "AtomicRegister"
    assert examples[0].validated_tier == "gold"
    assert examples[0].gold_source_kind == "diamond_eval_holdout"


def test_load_repair_prompts_can_filter_allowed_repair_buckets(tmp_path: Path) -> None:
    source = tmp_path / "mixed.jsonl"
    _write_jsonl(
        source,
        [
            {
                **_row("proof-1", before_score=0.45, suffix="proof"),
                "repair_bucket": "proof_repair",
            },
            {
                **_row("tlc-1", before_score=0.25, suffix="tlc"),
                "repair_bucket": "tlc_repair",
            },
            _row("benchmark-1", before_score=0.15, suffix="benchmark"),
        ],
    )

    examples, before_scores = load_repair_prompts(
        trajectory_file=[source],
        difficulty="all",
        min_before_score=0.02,
        max_before_score=0.80,
        allowed_repair_buckets=["proof_repair"],
    )

    assert [example.repair_id for example in examples] == ["proof-1"]
    assert before_scores == {"proof-1": 0.45}


def test_format_repair_prompt_falls_back_when_tokenizer_has_no_chat_template() -> None:
    tokenizer = _TemplateLessTokenizer()
    ex = type("RepairExampleStub", (), {
        "repair_id": "proof-1",
        "nl": "Write a TLA+ spec",
        "broken_spec": "---- MODULE Broken ----\n====",
        "errors_rendered": "diagnostic",
        "verify_summary": "summary",
    })()

    prompt = format_repair_prompt(ex, tokenizer)

    assert prompt.startswith("<!-- repair:proof-1 -->")
    assert "developer:" in prompt
    assert "user: Original request:" in prompt
    assert prompt.endswith("<|channel|>final<|message|>")
