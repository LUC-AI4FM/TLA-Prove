"""Evaluate a repair-GRPO adapter on the held-out repair pairs.

Loads base + LoRA adapter, generates repairs for every row of the held-out
eval set (rows the adapter never trained on — see
scripts/build_tla_prover_repair_holdout.py), grades each completion with the
same SANY/TLC reward used in training, and writes a JSON report. This is the
only legitimate (non-coverage) number for a checkpoint trained on the full
proof_repair_primary corpus.

Usage:
    python3 scripts/eval_repair_adapter_holdout.py \
        --adapter outputs/checkpoints_rl_repair_proof_primary/final \
        [--holdout data/processed/tla_prover_repair_eval_holdout_v1.jsonl] \
        [--samples 4] [--out outputs/repair_holdout_eval.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DEFAULT_HOLDOUT = REPO / "data" / "processed" / "tla_prover_repair_eval_holdout_v1.jsonl"
DEFAULT_OUT = REPO / "outputs" / "repair_holdout_eval.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--base-model", default="EricSpencer00/chattla-20b")
    parser.add_argument("--holdout", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    import torch
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer

    from src.rlvr_canary.repair_dataset import format_repair_prompt, load_repair_prompts
    from src.rlvr_canary.repair_reward import _grade_one

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    examples, before_scores = load_repair_prompts(
        [str(args.holdout)],
        tokenizer=tokenizer,
        max_prompt_tokens=100_000,   # no length filtering in eval
        min_before_score=-1.0,       # keep every holdout row
        max_before_score=2.0,
    )
    print(f"[holdout-eval] rows: {len(examples)}")

    # AutoPeftModelForCausalLM loads base + adapter together — the loader
    # diagnose_prover.py adopted because the peft/accelerate balanced-memory
    # path misbehaves on gpt-oss. Explicit max_memory leaves headroom for the
    # cuBLAS workspace: jobs 161597/161603/161606 died with ALLOC_FAILED at
    # the first forward because device_map=auto packed the cards full.
    model = AutoPeftModelForCausalLM.from_pretrained(
        args.adapter,
        attn_implementation="eager",
        use_cache=True,
        device_map="auto",
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        max_memory={0: "34GiB", 1: "34GiB"},
    )
    model.eval()

    rows = []
    for ex in examples:
        prompt = format_repair_prompt(ex, tokenizer)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        best_after = 0.0
        best_head = ""
        for _ in range(args.samples):
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=True,
                    temperature=args.temperature,
                    pad_token_id=tokenizer.pad_token_id,
                )
            completion = tokenizer.decode(
                out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=False
            )
            after = _grade_one(completion)
            if after >= best_after:
                best_after = after
                best_head = completion[:1200]
        before = float(ex.before_score)
        rows.append({
            "repair_id": ex.repair_id,
            "before": before,
            "best_after": best_after,
            "improved": best_after > before,
            "parsed": best_after > 0.0,
            "best_completion_head": best_head,
        })
        print(f"[holdout-eval] {ex.repair_id}: before={before:.2f} best_after={best_after:.2f}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adapter": str(args.adapter),
        "base_model": args.base_model,
        "holdout": str(args.holdout.name),
        "samples_per_row": args.samples,
        "rows": len(rows),
        "parsed_rows": sum(1 for r in rows if r["parsed"]),
        "improved_rows": sum(1 for r in rows if r["improved"]),
        "results": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("rows", "parsed_rows", "improved_rows")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
