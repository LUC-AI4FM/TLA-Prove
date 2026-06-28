#!/usr/bin/env python3
"""Quantized action-contract probe for a GRPO adapter.

This is not a training run. It is a small inference + reward pass designed to
answer the question that was blocking the next GRPO phase: under short decode
caps, does the adapter emit compact `Next == ...` actions or does it continue
full-spec/commentary habits?
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _completion_text(comp: Any) -> str:
    if isinstance(comp, list):
        return "".join(m.get("content", "") for m in comp if isinstance(m, dict))
    return str(comp or "")


def _first_device(model: Any) -> str:
    if hasattr(model, "hf_device_map"):
        devices = [str(v) for v in model.hf_device_map.values() if str(v) != "cpu"]
        if devices:
            return devices[0]
    return "cuda:0"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Base model path or HF ID")
    parser.add_argument("--adapter", required=True, help="PEFT adapter checkpoint")
    parser.add_argument("--corpus", default="data/processed/diamond_sft_v3_action_tok1200.jsonl")
    parser.add_argument("--out", required=True, help="JSONL sample output")
    parser.add_argument("--summary", required=True, help="JSON summary output")
    parser.add_argument("--num-prompts", type=int, default=8)
    parser.add_argument("--num-generations", type=int, default=2)
    parser.add_argument("--caps", type=int, nargs="+", default=[96, 128])
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260409)
    parser.add_argument(
        "--device-map",
        choices=["cuda0", "auto"],
        default="cuda0",
        help="Use cuda0 for one-GPU 4-bit probes; auto can reject CPU/disk offload.",
    )
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    from src.rlvr_canary.tla_dataset import load_tla_action_prompts
    from src.rlvr_canary.tla_reward import _extract_next_body, per_action_tlc_reward

    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    examples = load_tla_action_prompts(args.corpus)[: args.num_prompts]
    if not examples:
        raise SystemExit(f"No usable examples in {args.corpus}")

    print(f"[probe] examples={len(examples)} corpus={args.corpus}")
    print(f"[probe] loading tokenizer {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    print(f"[probe] loading base model 4-bit {args.model}")
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    device_map: Any = {"": 0} if args.device_map == "cuda0" else "auto"
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=quant_config,
        device_map=device_map,
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = True

    print(f"[probe] loading adapter {args.adapter}")
    model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False)
    model.eval()
    device = _first_device(model)
    print(f"[probe] generation device={device}")

    out_path = Path(args.out)
    summary_path = Path(args.summary)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    eos_ids = [tokenizer.eos_token_id, 9051, 904]
    with out_path.open("w", encoding="utf-8") as f:
        for cap in args.caps:
            print(f"[probe] cap={cap}")
            for prompt_index, ex in enumerate(examples):
                prompt = tokenizer.apply_chat_template(
                    ex.prompt,
                    tokenize=False,
                    add_generation_prompt=True,
                )
                inputs = tokenizer(prompt, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}
                for gen_index in range(args.num_generations):
                    with torch.no_grad():
                        output = model.generate(
                            **inputs,
                            max_new_tokens=cap,
                            do_sample=True,
                            temperature=args.temperature,
                            pad_token_id=tokenizer.pad_token_id,
                            eos_token_id=eos_ids,
                        )
                    new_tokens = output[0][inputs["input_ids"].shape[1]:]
                    raw = tokenizer.decode(new_tokens, skip_special_tokens=True)
                    rewards = per_action_tlc_reward(
                        completions=[raw],
                        prompt_id=[ex.prompt_id],
                        harness_prefix=[ex.harness.prefix],
                        harness_suffix=[ex.harness.suffix],
                        harness_module=[ex.harness.module_name],
                    )
                    extracted = _extract_next_body(raw)
                    row = {
                        "cap": cap,
                        "prompt_index": prompt_index,
                        "generation_index": gen_index,
                        "prompt_id": ex.prompt_id,
                        "harness_module": ex.harness.module_name,
                        "reward": rewards[0] if rewards else 0.0,
                        "raw_chars": len(raw),
                        "extracted_next_chars": len(extracted or ""),
                        "raw_completion": raw,
                        "extracted_next": extracted,
                    }
                    rows.append(row)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    print(
                        "[probe] "
                        f"cap={cap} prompt={prompt_index} gen={gen_index} "
                        f"reward={row['reward']} raw_chars={row['raw_chars']} "
                        f"next_chars={row['extracted_next_chars']}"
                    )

    by_cap: dict[int, dict[str, Any]] = {}
    for cap in args.caps:
        cap_rows = [r for r in rows if r["cap"] == cap]
        rewards = [float(r["reward"]) for r in cap_rows]
        raw_chars = [int(r["raw_chars"]) for r in cap_rows]
        next_chars = [int(r["extracted_next_chars"]) for r in cap_rows]
        by_cap[cap] = {
            "samples": len(cap_rows),
            "reward_mean": mean(rewards) if rewards else 0.0,
            "reward_max": max(rewards) if rewards else 0.0,
            "reward_nonzero": sum(r > 0 for r in rewards),
            "empty_extracted_next": sum(v == 0 for v in next_chars),
            "raw_chars_mean": mean(raw_chars) if raw_chars else 0.0,
            "extracted_next_chars_mean": mean(next_chars) if next_chars else 0.0,
        }

    summary = {
        "model": args.model,
        "adapter": args.adapter,
        "corpus": args.corpus,
        "num_prompts": len(examples),
        "num_generations": args.num_generations,
        "caps": args.caps,
        "by_cap": by_cap,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
