#!/usr/bin/env python3
"""Evaluate full-spec adapters on natural-language-to-TLA+ holdout prompts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MODULE_RE = re.compile(r"----\s*MODULE\s+(\w+)")


def _load_holdout(path: Path, max_examples: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            desc = row.get("topic_desc") or row.get("desc") or ""
            module = row.get("module") or "Spec"
            if not desc:
                continue
            rows.append({
                "module": module,
                "batch": row.get("batch", ""),
                "topic_desc": desc,
            })
            if max_examples and len(rows) >= max_examples:
                break
    return rows


def _module_name(text: str) -> str:
    m = MODULE_RE.search(text or "")
    return m.group(1) if m else "Temp"


def _score_spec(text: str, timeout: int) -> dict[str, Any]:
    from src.postprocess.normalize import normalize_spec
    from src.validators.tlc_validator import _autogenerate_cfg, validate_string
    from src.rlvr_canary.fullspec_reward import _structural_floor, _syntax_hygiene_issues

    out: dict[str, Any] = {
        "tier": "exception",
        "sany_pass": False,
        "tlc_pass": False,
        "tlc_depth1_ok": False,
        "partial_credit": 0.0,
        "structural_floor": _structural_floor(text),
        "syntax_issues": _syntax_hygiene_issues(text),
        "error": "",
    }
    try:
        normalized, report = normalize_spec(text)
        module = _module_name(normalized)
        cfg = _autogenerate_cfg(normalized)
        result = validate_string(
            normalized,
            cfg_content=cfg,
            module_name=module,
            timeout=timeout,
        )
        semantic = result.semantic
        out.update({
            "tier": result.tier,
            "sany_pass": result.tier != "bronze",
            "tlc_pass": result.tier == "gold",
            "tlc_depth1_ok": bool(semantic.tlc_depth1_ok),
            "partial_credit": float(semantic.partial_credit),
            "module_name": module,
            "normalized_clean": report.clean,
            "normalization_fixes": report.fixes,
            "init_present": bool(semantic.init_present),
            "next_present": bool(semantic.next_present),
            "init_level_ok": bool(semantic.init_level_ok),
            "next_level_ok": bool(semantic.next_level_ok),
            "invariants_declared": bool(semantic.invariants_declared),
            "raw_validator_output": result.raw_output[-2000:],
        })
    except Exception as exc:
        out["error"] = str(exc)
    return out


def _summary(label: str, adapter: str | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    denom = max(n, 1)
    return {
        "label": label,
        "adapter": adapter,
        "n": n,
        "sany_pass": sum(1 for r in rows if r["score"].get("sany_pass")),
        "tlc_pass": sum(1 for r in rows if r["score"].get("tlc_pass")),
        "depth1_pass": sum(1 for r in rows if r["score"].get("tlc_depth1_ok")),
        "mean_reward": round(sum(float(r["score"].get("partial_credit") or 0.0) for r in rows) / denom, 6),
        "mean_structural_floor": round(sum(float(r["score"].get("structural_floor") or 0.0) for r in rows) / denom, 6),
        "starts_module": sum(1 for r in rows if r.get("starts_module")),
        "has_terminator": sum(1 for r in rows if r.get("has_terminator")),
        "module_match": sum(1 for r in rows if r.get("module_match")),
        "syntax_issue_count": sum(len(r["score"].get("syntax_issues") or []) for r in rows),
        "syntax_issue_rows": sum(1 for r in rows if r["score"].get("syntax_issues")),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--label", default=None)
    ap.add_argument("--holdout", default=str(REPO / "data" / "processed" / "diamond_eval_holdout.jsonl"))
    ap.add_argument("--max-examples", type=int, default=10)
    ap.add_argument("--max-new-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--chat-template-reasoning-effort", default=None)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument(
        "--load-in-8bit",
        action="store_true",
        help="Load the base model with bitsandbytes int8 quantization for triage evals.",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from src.rlvr_canary.fullspec_dataset import _DEVELOPER_PROMPT

    label = args.label or (Path(args.adapter).name if args.adapter else "base")
    holdout = _load_holdout(Path(args.holdout), args.max_examples)
    if not holdout:
        raise SystemExit(f"no holdout rows loaded from {args.holdout}")

    print(f"[eval-fullspec] loading model {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    load_kwargs: dict[str, Any] = {
        "device_map": "auto",
    }
    if args.load_in_8bit:
        from transformers import BitsAndBytesConfig

        load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        load_kwargs["dtype"] = torch.bfloat16

    base = AutoModelForCausalLM.from_pretrained(args.model, **load_kwargs)
    if args.adapter:
        print(f"[eval-fullspec] loading adapter {args.adapter}")
        model = PeftModel.from_pretrained(base, args.adapter)
    else:
        model = base
    model.eval()

    channel_suffix = "<|channel|>final<|message|>"
    template_kwargs = {"add_generation_prompt": True}
    if args.chat_template_reasoning_effort:
        template_kwargs["reasoning_effort"] = args.chat_template_reasoning_effort
    rows: list[dict[str, Any]] = []
    for i, ex in enumerate(holdout, 1):
        messages = [
            {"role": "developer", "content": _DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Write a TLA+ specification with module name exactly {ex['module']} "
                    f"for the following:\n\n{ex['topic_desc']}"
                ),
            },
        ]
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            **template_kwargs,
        ) + channel_suffix
        input_device = None
        for param in model.parameters():
            if param.device.type == "cuda":
                input_device = param.device
                break
        if input_device is None:
            input_device = getattr(model, "device", torch.device("cpu"))
        inputs = tokenizer(prompt, return_tensors="pt").to(input_device)

        print(f"[eval-fullspec] {i}/{len(holdout)} {ex['module']}")
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=args.temperature > 0,
                temperature=args.temperature if args.temperature > 0 else None,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=[tokenizer.eos_token_id, 904],
            )
        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(new_tokens, skip_special_tokens=False)
        starts_module = raw.lstrip().startswith("---- MODULE")
        has_terminator = "====" in raw
        produced_module = _module_name(raw)
        score = _score_spec(raw, timeout=args.timeout)
        rows.append({
            "target_module": ex["module"],
            "batch": ex["batch"],
            "produced_module": produced_module,
            "module_match": produced_module == ex["module"],
            "starts_module": starts_module,
            "has_terminator": has_terminator,
            "raw_chars": len(raw),
            "raw_generation": raw,
            "score": score,
        })
        print(
            "  tier={tier} reward={reward:.4f} depth1={depth1} tlc={tlc} module={mod}".format(
                tier=score["tier"],
                reward=float(score.get("partial_credit") or 0.0),
                depth1=score.get("tlc_depth1_ok"),
                tlc=score.get("tlc_pass"),
                mod=produced_module,
            )
        )

    result = _summary(label, args.adapter, rows)
    result["quantization"] = "int8" if args.load_in_8bit else "bf16"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        "[eval-fullspec] summary",
        "sany", f"{result['sany_pass']}/{result['n']}",
        "depth1", f"{result['depth1_pass']}/{result['n']}",
        "tlc", f"{result['tlc_pass']}/{result['n']}",
        "mean_reward", result["mean_reward"],
    )
    print(f"[eval-fullspec] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
