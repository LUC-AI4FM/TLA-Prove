#!/usr/bin/env python3
"""GRPO training on gpt-oss-20b with repair prompts + improvement reward.

Instead of training the model to one-shot perfect specs (which gives
zero reward variance), this trains the model to REPAIR broken specs
given line-annotated verifier diagnostics.

Why this works:
  1. Dense reward — improvement delta gives variance even with 4 gens
  2. Easier task — fixing errors is simpler than generating from scratch
  3. Unlimited data — Ralph trajectories provide many repair pairs
  4. Curriculum — easy (SANY fixes) → medium → hard (TLC/semantic)

Architecture:
  - Base model: post-DPO checkpoint (same as train_rl_fullspec.py)
  - LoRA adapter: fresh r=8/alpha=16
  - Reward: repair_reward (improvement-based shaped reward)
  - Dataset: Ralph repair pairs from collect_ralph_trajectories.py
  - Trainer: TRL GRPOTrainer

Memory budget (2x RTX 8000, 49 GB each):
  - 20B bf16 ≈ 40 GB via device_map="auto"
  - 4 completions × 1024 tokens: similar to fullspec
  - Repair prompts longer (~1200 tokens) but completions shorter (1024)
  - Total: ~54-58 GB / 98 GB available

Run:
    python -m scripts.train_rl_repair --smoke           # 2-step sanity check
    python -m scripts.train_rl_repair --max-steps 300   # full run (~16h)
    python -m scripts.train_rl_repair --difficulty easy  # SANY-only curriculum
    python -m scripts.train_rl_repair --trajectory-file data/processed/tla_prover_repair_train_v1.jsonl

Default input behavior:
    Prefer data/processed/tla_prover_repair_train_v1.jsonl when present.
    Otherwise fall back to the available component repair corpora.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MERGED_REPAIR_PAIRS = "data/processed/tla_prover_repair_train_v1.jsonl"
DEFAULT_MERGED_REPAIR_SUMMARY = "data/processed/tla_prover_repair_train_v1.summary.json"
DEFAULT_REPAIR_PAIRS = "data/processed/ralph_repair_pairs.jsonl"
DEFAULT_BENCHMARK_REPAIR_PAIRS = "data/processed/benchmark_repair_pairs_fc128best.jsonl"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _resolve_repo_path(path_str: str, repo_root: Path = _REPO_ROOT) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _path_exists(path_str: str) -> bool:
    return _resolve_repo_path(path_str).is_file()


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _count_repair_rows(path: Path) -> tuple[int, set[str]]:
    rows = 0
    repair_ids: set[str] = set()
    if not path.is_file():
        return rows, repair_ids
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            rows += 1
            repair_id = json.loads(line).get("repair_id")
            if repair_id is not None:
                repair_ids.add(str(repair_id))
    return rows, repair_ids


def _resolve_base_model() -> str:
    """Pick the best available MERGED base model in priority order."""
    env_base = os.environ.get("CHATTLA_BASE_MODEL")
    if env_base:
        return env_base
    candidates = [
        _REPO_ROOT / "outputs" / "merged_model_dpo_piecewise",
        _REPO_ROOT / "outputs" / "merged_model_repair",
        _REPO_ROOT / "outputs" / "merged_model_v20",
        _REPO_ROOT / "outputs" / "merged_model_v14",
        _REPO_ROOT / "outputs" / "merged_model_v13",
        _REPO_ROOT / "outputs" / "merged_model",
    ]
    for c in candidates:
        if c.is_dir() and (c / "config.json").is_file():
            return str(c)
    return "EricSpencer00/chattla-20b"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default=None,
                        help="Base model path (auto-detected if omitted)")
    parser.add_argument("--output-dir", default="outputs/checkpoints_rl_repair")
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=3e-6,
                        help="Slightly lower than fullspec for stability")
    parser.add_argument("--num-generations", type=int, default=4,
                        help="4 gens with repair prompts fits when Ollama is unloaded. "
                        "Use --num-generations 2 if sharing GPU with Ollama.")
    parser.add_argument("--per-device-batch-size", type=int, default=1)
    parser.add_argument("--max-completion-length", type=int, default=1024,
                        help="Repairs are shorter than from-scratch specs (1024 vs 1536). "
                        "Use 768 if sharing GPU with Ollama.")
    parser.add_argument("--beta", type=float, default=0.02,
                        help="Lower KL penalty — allow more deviation for repair task")
    parser.add_argument("--temperature", type=float, default=0.5,
                        help="Lower than fullspec — repairs need focus")
    parser.add_argument("--logging-steps", type=int, default=1)
    parser.add_argument("--save-steps", type=int, default=50)
    parser.add_argument("--difficulty", default="all",
                        choices=["easy", "medium", "hard", "all"],
                        help="Filter repair pairs by difficulty")
    parser.add_argument("--min-before-score", type=float, default=0.02,
                        help="Drop pairs with before_score below this — "
                        "unparseable specs leave the model with no improvement signal")
    parser.add_argument("--max-before-score", type=float, default=0.80,
                        help="Drop already-good pairs that leave no headroom")
    parser.add_argument("--max-prompt-tokens", type=int, default=1600,
                        help="Hard prompt-length filter — drops the long-tail "
                        "that blows up eager-attention memory (this version of "
                        "TRL has no GRPOConfig.max_prompt_length, so the only "
                        "defense is dataset-level filtering)")
    parser.add_argument("--trajectory-file", action="append", default=None,
                        help="Path to a repair-pairs JSONL. Repeat to mix multiple corpora. "
                        f"Defaults to `{DEFAULT_MERGED_REPAIR_PAIRS}` when present, otherwise the available component corpora.")
    parser.add_argument("--include-benchmark-repair-pairs", action="store_true",
                        help="Also load the benchmark-derived repair corpus at "
                        f"`{DEFAULT_BENCHMARK_REPAIR_PAIRS}`.")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Print a cheap local repair-corpus report and exit before loading tokenizer/model deps.")
    parser.add_argument("--smoke", action="store_true",
                        help="2 steps, no checkpoint, sanity-check the wiring")
    return parser


def resolve_trajectory_files(args: argparse.Namespace, repo_root: Path = _REPO_ROOT) -> list[str]:
    path_exists = _path_exists if repo_root == _REPO_ROOT else lambda path: _resolve_repo_path(path, repo_root).is_file()
    if args.trajectory_file:
        files = list(args.trajectory_file)
        if args.include_benchmark_repair_pairs and DEFAULT_BENCHMARK_REPAIR_PAIRS not in files:
            files.append(DEFAULT_BENCHMARK_REPAIR_PAIRS)
        return files

    if path_exists(DEFAULT_MERGED_REPAIR_PAIRS):
        return [DEFAULT_MERGED_REPAIR_PAIRS]

    files = [path for path in [DEFAULT_REPAIR_PAIRS, DEFAULT_BENCHMARK_REPAIR_PAIRS] if path_exists(path)]
    if not files:
        files = [DEFAULT_REPAIR_PAIRS]
    if args.include_benchmark_repair_pairs and DEFAULT_BENCHMARK_REPAIR_PAIRS not in files:
        files.append(DEFAULT_BENCHMARK_REPAIR_PAIRS)
    return files


def build_preflight_report(args: argparse.Namespace, repo_root: Path = _REPO_ROOT) -> dict[str, Any]:
    trajectory_files = resolve_trajectory_files(args, repo_root=repo_root)
    raw_rows = 0
    unique_repair_ids: set[str] = set()
    file_reports: list[dict[str, Any]] = []
    missing_files: list[str] = []

    for path_str in trajectory_files:
        path = _resolve_repo_path(path_str, repo_root)
        exists = path.is_file()
        rows, ids = _count_repair_rows(path)
        raw_rows += rows
        unique_repair_ids.update(ids)
        if not exists:
            missing_files.append(path_str)
        file_reports.append(
            {
                "path": path_str,
                "exists": exists,
                "rows": rows,
                "unique_repair_ids": len(ids),
            }
        )

    using_merged_default = trajectory_files == [DEFAULT_MERGED_REPAIR_PAIRS]
    merged_summary_path = _resolve_repo_path(DEFAULT_MERGED_REPAIR_SUMMARY, repo_root)
    merged_summary = _read_optional_json(merged_summary_path) if using_merged_default else None
    ok = not missing_files and raw_rows > 0
    if merged_summary is not None:
        ok = ok and bool(dict(merged_summary.get("health") or {}).get("ok"))

    return {
        "schema": "chattla_tla_prover_repair_preflight_v1",
        "ok": ok,
        "trajectory_files": trajectory_files,
        "missing_files": missing_files,
        "raw_rows": raw_rows,
        "unique_repair_ids": len(unique_repair_ids),
        "using_merged_default": using_merged_default,
        "files": file_reports,
        "merged_summary_path": DEFAULT_MERGED_REPAIR_SUMMARY if using_merged_default else None,
        "merged_summary": {
            "rows": merged_summary.get("rows"),
            "health": merged_summary.get("health"),
            "kept_rows_by_source": merged_summary.get("kept_rows_by_source"),
            "missing_sources": merged_summary.get("missing_sources"),
        } if merged_summary is not None else None,
    }


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.model is None:
        args.model = _resolve_base_model()

    if args.preflight_only:
        report = build_preflight_report(args)
        report["model"] = args.model
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 2

    import torch
    import yaml
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    from src.rlvr_canary.repair_dataset import (
        format_repair_prompt,
        load_repair_prompts,
    )
    from src.rlvr_canary.repair_reward import register_before_scores, repair_reward

    if args.smoke:
        args.max_steps = 2
        args.save_steps = 1000
        args.logging_steps = 1

    # -- Tokenizer (needed for length-filter before dataset load) -----
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    # -- Dataset --------------------------------------------------------
    trajectory_files = resolve_trajectory_files(args)
    print(f"[rl-repair] loading repair prompts from {trajectory_files} ...")
    examples, before_scores = load_repair_prompts(
        trajectory_file=trajectory_files,
        difficulty=args.difficulty,
        max_examples=10 if args.smoke else None,
        min_before_score=args.min_before_score,
        max_before_score=args.max_before_score,
        max_prompt_tokens=args.max_prompt_tokens,
        tokenizer=tokenizer,
    )
    if not examples:
        sys.exit(
            "No repair pairs found. Check filters or rebuild the selected corpora "
            "(for example collect_ralph_trajectories.py or build_benchmark_repair_pairs.py)."
        )
    print(f"[rl-repair] loaded {len(examples)} repair pairs "
          f"(difficulty={args.difficulty}, "
          f"score=[{args.min_before_score},{args.max_before_score}], "
          f"max_toks={args.max_prompt_tokens})")

    # Register before_scores with the reward function
    register_before_scores(before_scores)

    # -- LoRA config ----------------------------------------------------
    lora_cfg_path = _REPO_ROOT / "src" / "training" / "lora_config.yaml"
    with open(lora_cfg_path) as f:
        lora_cfg = yaml.safe_load(f)
    print(f"[rl-repair] LoRA: r={lora_cfg['r']}, alpha={lora_cfg['lora_alpha']}")

    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg.get("lora_dropout", 0.0),
        bias=lora_cfg.get("bias", "none"),
        target_modules=lora_cfg["target_modules"],
        task_type="CAUSAL_LM",
    )

    # -- Model ----------------------------------------------------------
    print(f"[rl-repair] loading base model {args.model} ...")

    # Pre-format repair prompts (same pattern as train_rl_fullspec.py)
    formatted_prompts: list[str] = []
    for ex in examples:
        formatted_prompts.append(format_repair_prompt(ex, tokenizer))

    # Dataset is pre-sorted by difficulty (easy first) for curriculum.
    # Disable shuffling in GRPOConfig to preserve ordering.
    train_ds = Dataset.from_list([
        {"prompt": p} for p in formatted_prompts
    ])
    print(f"[rl-repair] prompts pre-formatted: "
          f"avg {sum(len(p) for p in formatted_prompts) // len(formatted_prompts)} chars")

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        dtype=torch.bfloat16,
        device_map="auto",
    )
    model.config.use_cache = False

    # -- GRPO config ----------------------------------------------------
    gen_batch_size = args.per_device_batch_size * args.num_generations

    config = GRPOConfig(
        output_dir=args.output_dir,
        per_device_train_batch_size=gen_batch_size,
        generation_batch_size=gen_batch_size,
        gradient_accumulation_steps=1,
        learning_rate=args.learning_rate,
        max_steps=args.max_steps,
        num_generations=args.num_generations,
        max_completion_length=args.max_completion_length,
        beta=args.beta,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        bf16=True,
        report_to=["none"],
        remove_unused_columns=False,
        seed=20260410,
        temperature=args.temperature,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        generation_kwargs={
            "eos_token_id": [tokenizer.eos_token_id, 904],  # 904 = "===="
        },
    )

    # -- Trainer --------------------------------------------------------
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        args=config,
        train_dataset=train_ds,
        reward_funcs=[repair_reward],
        peft_config=peft_config,
    )

    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[rl-repair] params: {total_params / 1e9:.1f}B total, "
          f"{trainable / 1e6:.1f}M trainable ({100 * trainable / total_params:.2f}%)")
    print(f"[rl-repair] starting GRPO: {args.max_steps} steps, "
          f"{args.num_generations} gens/prompt, lr={args.learning_rate}, "
          f"beta={args.beta}, temp={args.temperature}")

    trainer.train()

    # Save final checkpoint
    trainer.save_model(args.output_dir + "/final")
    print(f"[rl-repair] done -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
